"""Small, side-effect aware Bilibili account and owner connector.

This module deliberately contains only the account boundary used by the first
integration step.  Video discovery, video understanding and persona memory are
separate concerns.  Credentials are kept outside the repository and are never
included in status output.
"""

from __future__ import annotations

import base64
import ctypes
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import tempfile
import time
from typing import Any, Mapping
import uuid

import httpx


class BilibiliConnectorError(RuntimeError):
    """A safe, user-facing connector error without cookie values."""


class BilibiliShareLimit(BilibiliConnectorError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__("今日主动分享已达上限" if reason == "daily_limit" else "主动分享间隔不足两小时")


class BilibiliDuplicateDelivery(BilibiliConnectorError):
    pass


DAILY_VIDEO_SHARE_LIMIT = 3
VIDEO_SHARE_INTERVAL_SECONDS = 2 * 60 * 60


def video_share_scope(binding) -> str:
    binding.validate()
    return hashlib.sha256(json.dumps([binding.aike_mid, binding.owner_mid]).encode()).hexdigest()


def video_delivery_key(binding, bvid: str) -> str:
    return hashlib.sha256(json.dumps([binding.aike_mid, binding.owner_mid, "explicit", "video-share-v1:" + bvid],
                                    ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class BilibiliCredentials:
    sessdata: str = field(repr=False)
    bili_jct: str = field(repr=False)
    buvid3: str = field(default="", repr=False)

    def validate(self) -> None:
        for name, value, required in (("SESSDATA", self.sessdata, True), ("bili_jct", self.bili_jct, True), ("buvid3", self.buvid3, False)):
            if not isinstance(value, str) or (required and not value.strip()):
                raise BilibiliConnectorError(f"缺少或无效的 {name}")
            if len(value) > 4096 or any(ord(c) < 32 or ord(c) > 126 or c == ";" for c in value):
                raise BilibiliConnectorError(f"{name} 包含无效字符，请只复制对应 Cookie 的值")
        if not re.fullmatch(r"[0-9a-fA-F]{32}", self.bili_jct.strip()):
            raise BilibiliConnectorError("bili_jct 应为 32 位十六进制值")

    def cookie_header(self) -> str:
        self.validate()
        pairs = [f"SESSDATA={self.sessdata.strip()}", f"bili_jct={self.bili_jct.strip()}"]
        if self.buvid3.strip():
            pairs.append(f"buvid3={self.buvid3.strip()}")
        return "; ".join(pairs)


@dataclass(frozen=True)
class BilibiliAccount:
    mid: str
    uname: str
    is_login: bool


@dataclass(frozen=True)
class BilibiliBinding:
    persona_id: str
    role_card_key: str
    aike_mid: str
    owner_mid: str
    owner_name: str = ""

    def validate(self) -> None:
        if not self.persona_id.strip():
            raise BilibiliConnectorError("persona_id 不能为空")
        if not self.role_card_key.strip():
            raise BilibiliConnectorError("role_card_key 不能为空")
        _validate_uid(self.aike_mid)
        _validate_uid(self.owner_mid)
        if self.aike_mid == self.owner_mid:
            raise BilibiliConnectorError("爱可账号和主人账号不能是同一个 UID")


@dataclass(frozen=True)
class RelationStatus:
    attribute: int
    be_attribute: int | None

    @property
    def mutual(self) -> bool:
        return self.attribute == 6


@dataclass(frozen=True)
class PrivateMessageResult:
    sent: bool
    dry_run: bool
    http_status: int | None = None
    code: int | None = None
    message: str = ""
    request_id: str = ""


def connector_home() -> Path:
    override = os.environ.get("AIKE_BILIBILI_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        root = os.environ.get("LOCALAPPDATA", "") or str(Path.home() / "AppData" / "Local")
        return Path(root) / "AIchatbot" / "bilibili"
    return Path.home() / ".local" / "share" / "aichatbot" / "bilibili"


def _json_path(name: str) -> Path:
    return connector_home() / name


def _validate_uid(value: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,18}", value):
        raise BilibiliConnectorError("B 站 UID 必须是正整数，不含前导零")


def _atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, filename = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(payload)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _dpapi(value: bytes, *, decrypt: bool) -> bytes:
    if sys.platform != "win32":
        raise OSError("DPAPI is only available on Windows")

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(DATA_BLOB)]
    function.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    source = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
    input_blob = DATA_BLOB(len(value), source)
    output_blob = DATA_BLOB()
    if not function(ctypes.byref(input_blob), None, None, None, None, 1, ctypes.byref(output_blob)):
        raise BilibiliConnectorError("Windows 凭据解密失败，请在原 Windows 用户下运行或重新登录" if decrypt else "Windows 凭据加密失败")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


class CredentialStore:
    """Persist credentials outside the repository, encrypted on Windows."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _json_path("credentials.json")

    def save(self, credentials: BilibiliCredentials) -> None:
        credentials.validate()
        raw = json.dumps({"sessdata": credentials.sessdata.strip(), "bili_jct": credentials.bili_jct.strip(), "buvid3": credentials.buvid3.strip()}, separators=(",", ":")).encode()
        if sys.platform != "win32":
            raise BilibiliConnectorError("当前凭据存储仅支持 Windows DPAPI")
        payload = {"format": "dpapi-v1", "blob": base64.b64encode(_dpapi(raw, decrypt=False)).decode("ascii")}
        _atomic_write(self.path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def load(self) -> BilibiliCredentials:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise BilibiliConnectorError(f"未找到 B 站凭据文件：{self.path}") from exc
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise BilibiliConnectorError("B 站凭据文件无法读取") from exc
        try:
            if payload.get("format") == "dpapi-v1":
                raw = _dpapi(base64.b64decode(payload["blob"], validate=True), decrypt=True)
                values = json.loads(raw.decode("utf-8"))
            else:
                raise ValueError("unknown credential format")
            credentials = BilibiliCredentials(values.get("sessdata", ""), values.get("bili_jct", ""), values.get("buvid3", ""))
            credentials.validate()
            return credentials
        except BilibiliConnectorError:
            raise
        except Exception as exc:
            raise BilibiliConnectorError("B 站凭据格式无效或无法解密") from exc


class BindingStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _json_path("binding.json")

    def save(self, binding: BilibiliBinding) -> None:
        binding.validate()
        _atomic_write(self.path, json.dumps(binding.__dict__, ensure_ascii=False, indent=2) + "\n")

    def load(self) -> BilibiliBinding:
        try:
            values = json.loads(self.path.read_text(encoding="utf-8"))
            binding = BilibiliBinding(**{key: str(values.get(key, "")) for key in ("persona_id", "role_card_key", "aike_mid", "owner_mid", "owner_name")})
            binding.validate()
            return binding
        except FileNotFoundError as exc:
            raise BilibiliConnectorError(f"未找到 B 站身份绑定文件：{self.path}") from exc
        except BilibiliConnectorError:
            raise
        except Exception as exc:
            raise BilibiliConnectorError("B 站身份绑定文件无效") from exc


class DeliveryStore:
    """Local send ledger. A committed reservation precedes every POST.

    This prevents this connector from replaying an attempt after a timeout or
    process crash. It cannot provide platform-side exactly-once delivery.
    Message text and credentials are never stored in this ledger.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or connector_home() / "deliveries.sqlite3"

    @contextmanager
    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS deliveries (delivery_key TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, state TEXT NOT NULL, created_at INTEGER NOT NULL, code INTEGER)")
            connection.execute("CREATE TABLE IF NOT EXISTS delivery_meta (request_id TEXT PRIMARY KEY, share_scope TEXT, bvid TEXT)")
            connection.commit()
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _quota(connection, scope: str, now: int) -> dict:
        beijing = timezone(timedelta(hours=8))
        start = int(datetime.fromtimestamp(now, beijing).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='delivery_meta'").fetchone():
            rows = connection.execute("""SELECT d.state,d.created_at,m.request_id FROM deliveries d
                LEFT JOIN delivery_meta m ON m.request_id=d.request_id
                WHERE d.state IN ('pending','sent','unknown') AND (m.share_scope=? OR m.request_id IS NULL)""", (scope,)).fetchall()
        else:
            rows = connection.execute("SELECT state,created_at,NULL FROM deliveries WHERE state IN ('pending','sent','unknown')").fetchall()
        today = [row for row in rows if row[1] >= start]
        latest = max((row[1] for row in rows), default=0)
        return {"daily_limit": DAILY_VIDEO_SHARE_LIMIT, "used_today": len(today),
                "remaining_today": max(0, DAILY_VIDEO_SHARE_LIMIT - len(today)),
                "legacy_uncertain_today": sum(row[2] is None for row in today),
                "cooldown_remaining_seconds": max(0, latest + VIDEO_SHARE_INTERVAL_SECONDS - now) if rows else 0}

    def quota_status(self, binding, *, now: int | None = None) -> dict:
        now = int(time.time()) if now is None else now
        scope = video_share_scope(binding)
        if not self.path.is_file():
            return {"daily_limit": DAILY_VIDEO_SHARE_LIMIT, "used_today": 0, "remaining_today": DAILY_VIDEO_SHARE_LIMIT,
                    "legacy_uncertain_today": 0, "cooldown_remaining_seconds": 0}
        connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
        try:
            connection.execute("PRAGMA query_only=ON")
            return self._quota(connection, scope, now)
        finally:
            connection.close()

    def register_reported_shares(self, binding, directory: Path | None = None) -> None:
        """Classify matching old receipts without trusting report delivery claims alone."""
        directory = directory or connector_home() / "previews"
        if not self.path.is_file() or not directory.is_dir():
            return
        scope = video_share_scope(binding)
        with self._connect() as connection:
            for path in directory.glob("*.json"):
                try:
                    if path.stat().st_size > 2 * 1024 * 1024:
                        continue
                    delivery = json.loads(path.read_text(encoding="utf-8")).get("delivery", {})
                    bvid, request_id = delivery["bvid"], delivery["request_id"]
                    if not isinstance(bvid, str) or not re.fullmatch(r"BV[0-9A-Za-z]{10}", bvid):
                        continue
                    receipt = connection.execute("SELECT request_id FROM deliveries WHERE request_id=? AND delivery_key=?",
                                                 (request_id, video_delivery_key(binding, bvid))).fetchone()
                    if receipt:
                        connection.execute("INSERT OR IGNORE INTO delivery_meta VALUES(?,?,?)", (request_id, scope, bvid))
                except (OSError, ValueError, TypeError, KeyError, AttributeError):
                    continue

    def reserve(self, key: str, *, share_scope: str | None = None, bvid: str | None = None) -> str:
        request_id = uuid.uuid4().hex
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT request_id,state FROM deliveries WHERE delivery_key=?", (key,)).fetchone()
            if row:
                raise BilibiliDuplicateDelivery(f"已阻止重复发送：request_id={row[0]}, state={row[1]}；请先检查 B 站会话及发送记录")
            now = int(time.time())
            if share_scope is not None:
                quota = self._quota(connection, share_scope, now)
                if not quota["remaining_today"]:
                    raise BilibiliShareLimit("daily_limit")
                if quota["cooldown_remaining_seconds"]:
                    raise BilibiliShareLimit("cooldown")
            try:
                connection.execute("INSERT INTO deliveries VALUES (?, ?, 'pending', ?, NULL)", (key, request_id, now))
                connection.execute("INSERT INTO delivery_meta VALUES(?,?,?)", (request_id, share_scope, bvid))
            except sqlite3.IntegrityError as exc:
                row = connection.execute("SELECT request_id, state FROM deliveries WHERE delivery_key = ?", (key,)).fetchone()
                raise BilibiliDuplicateDelivery(f"已阻止重复发送：request_id={row[0]}, state={row[1]}；请先检查 B 站会话及发送记录") from exc
        return request_id

    def finish(self, request_id: str, state: str, code: int | None = None) -> None:
        if state not in {"sent", "failed", "unknown"}:
            raise ValueError("invalid delivery state")
        with self._connect() as connection:
            connection.execute("UPDATE deliveries SET state = ?, code = ? WHERE request_id = ?", (state, code, request_id))

    def recent(self) -> list[tuple[str, str, int, int | None]]:
        with self._connect() as connection:
            return connection.execute("SELECT request_id, state, created_at, code FROM deliveries ORDER BY created_at DESC, rowid DESC LIMIT 20").fetchall()


class BilibiliClient:
    API_BASE = "https://api.bilibili.com"
    DM_ENDPOINT = "https://api.vc.bilibili.com/web_im/v1/web_im/send_msg"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36"

    def __init__(self, credentials: BilibiliCredentials, *, client: httpx.Client | None = None, deliveries: DeliveryStore | None = None) -> None:
        credentials.validate()
        self.credentials = credentials
        self._client = client or httpx.Client(timeout=httpx.Timeout(20.0, connect=10.0), follow_redirects=False)
        self._owns_client = client is None
        self.deliveries = deliveries or DeliveryStore()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "BilibiliClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def headers(self) -> dict[str, str]:
        return {"User-Agent": self.USER_AGENT, "Referer": "https://www.bilibili.com/", "Cookie": self.credentials.cookie_header()}

    def _json(self, response: httpx.Response) -> Mapping[str, Any]:
        if response.status_code != 200:
            raise BilibiliConnectorError(f"B 站请求失败：HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise BilibiliConnectorError("B 站返回了非 JSON 响应，可能触发风控") from exc
        if not isinstance(payload, dict):
            raise BilibiliConnectorError("B 站响应格式异常")
        return payload

    def account(self) -> BilibiliAccount:
        try:
            payload = self._json(self._client.get(f"{self.API_BASE}/x/web-interface/nav", headers=self.headers, follow_redirects=False))
        except httpx.HTTPError as exc:
            raise BilibiliConnectorError("B 站账号检查失败：网络请求错误") from exc
        if payload.get("code") == -101:
            raise BilibiliConnectorError("B 站登录态已失效，请重新运行 login")
        data = payload.get("data")
        if type(payload.get("code")) is not int or payload["code"] != 0 or not isinstance(data, dict):
            raise BilibiliConnectorError("B 站账号检查失败：响应格式或业务状态异常")
        if data.get("isLogin") is not True:
            raise BilibiliConnectorError("B 站登录态已失效，请重新运行 login")
        mid = str(data.get("mid") or "")
        _validate_uid(mid)
        return BilibiliAccount(mid, str(data.get("uname") or ""), True)

    def relation(self, owner_mid: str) -> RelationStatus:
        _validate_uid(owner_mid)
        try:
            payload = self._json(self._client.get(f"{self.API_BASE}/x/relation", params={"fid": owner_mid}, headers=self.headers, follow_redirects=False))
        except httpx.HTTPError as exc:
            raise BilibiliConnectorError("B 站关系检查失败：网络请求错误") from exc
        data = payload.get("data")
        if type(payload.get("code")) is not int or payload["code"] != 0 or not isinstance(data, dict) or type(data.get("attribute")) is not int:
            raise BilibiliConnectorError("B 站关系检查失败：响应格式或业务状态异常")
        be = data.get("be_relation")
        be_attribute = be.get("attribute") if isinstance(be, dict) else None
        return RelationStatus(data["attribute"], be_attribute if type(be_attribute) is int else None)

    def send_private_message(self, binding: BilibiliBinding, text: str, *, dry_run: bool = True, delivery_key: str | None = None) -> PrivateMessageResult:
        binding.validate()
        text = text.strip()
        if not text:
            raise BilibiliConnectorError("私信内容不能为空")
        if len(text) > 300:
            raise BilibiliConnectorError("私信内容不能超过 300 字")
        account = self.account()
        if not account.is_login or account.mid != binding.aike_mid:
            raise BilibiliConnectorError("当前登录账号与绑定的爱可 B 站 UID 不一致")
        relation = self.relation(binding.owner_mid)
        if not relation.mutual:
            raise BilibiliConnectorError("爱可与主人尚未互相关注，已停止发送")
        if dry_run:
            return PrivateMessageResult(False, True)
        device_id = _device_id()
        form = {
            "msg[sender_uid]": account.mid,
            "msg[receiver_id]": binding.owner_mid,
            "msg[receiver_type]": "1",
            "msg[msg_type]": "1",
            "msg[msg_status]": "0",
            "msg[timestamp]": str(int(time.time())),
            "msg[dev_id]": device_id,
            "msg[content]": json.dumps({"content": text}, ensure_ascii=False),
        }
        # Hash identities and either the text or an explicit caller job ID.
        # Default identical messages cannot be resent by rerunning the command.
        if delivery_key is not None and (not delivery_key.strip() or len(delivery_key) > 200):
            raise BilibiliConnectorError("delivery_key 必须为 1–200 字符")
        key = hashlib.sha256(json.dumps([account.mid, binding.owner_mid, "explicit" if delivery_key is not None else "content", delivery_key if delivery_key is not None else text], ensure_ascii=False).encode()).hexdigest()
        if delivery_key and re.fullmatch(r"video-share-v1:BV[0-9A-Za-z]{10}", delivery_key):
            self.deliveries.register_reported_shares(binding)
            request_id = self.deliveries.reserve(key, share_scope=video_share_scope(binding), bvid=delivery_key.split(":", 1)[1])
        else:
            request_id = self.deliveries.reserve(key)
        try:
            response = self._post_private_form(form)
            payload = self._json(response)
            code = payload.get("code")
            if type(code) is not int:
                raise BilibiliConnectorError("私信响应缺少有效业务状态")
        except (httpx.HTTPError, BilibiliConnectorError) as exc:
            # Do not retry: a timeout can mean the platform accepted the message.
            self.deliveries.finish(request_id, "unknown")
            raise BilibiliConnectorError(f"私信发送结果不确定（request_id={request_id}）；已记录且阻止重复发送，请先检查 B 站会话") from exc
        self.deliveries.finish(request_id, "sent" if code == 0 else "failed", code)
        if code != 0:
            raise BilibiliConnectorError(f"私信发送失败：code={code}（request_id={request_id}）")
        return PrivateMessageResult(True, False, response.status_code, code, "平台接口返回成功，实际送达请在 B 站确认", request_id)

    def _post_private_form(self, form: dict) -> httpx.Response:
        return self._client.post(self.DM_ENDPOINT, data={**form, "csrf": self.credentials.bili_jct.strip()},
                                 headers=self.headers, follow_redirects=False)


def _device_id() -> str:
    path = _json_path("device-id")
    try:
        value = path.read_text(encoding="ascii").strip()
        if value.startswith("WEB-") and len(value) > 20:
            return value
    except (OSError, UnicodeError):
        pass
    value = "WEB-" + secrets.token_hex(16).upper()
    _atomic_write(path, value + "\n")
    return value


def redact_uid(value: str) -> str:
    value = str(value)
    return value if len(value) <= 4 else value[:2] + "…" + value[-2:]


__all__ = [
    "BilibiliAccount", "BilibiliBinding", "BilibiliClient", "BilibiliConnectorError",
    "BilibiliCredentials", "BindingStore", "CredentialStore", "DeliveryStore", "PrivateMessageResult",
    "RelationStatus", "connector_home", "redact_uid",
]
