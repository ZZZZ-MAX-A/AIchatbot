"""Persistent, dedicated Edge profile with manual login and read-only identity checks."""
from __future__ import annotations

import base64
from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from .bilibili_connector import BilibiliBinding, BilibiliConnectorError, _atomic_write, connector_home
from .bilibili_diagnostics import DiagnosticLog, response_facts

LOGIN_URL = "https://passport.bilibili.com/login"
NAV_URL = "https://api.bilibili.com/x/web-interface/nav"
MAX_BYTES = 2 * 1024 * 1024
REPO_ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"browser_open", "browser_closed", "login_required", "logged_in", "account_mismatch",
            "account_request_blocked", "account_response_invalid", "browser_unreachable"}


class BrowserControllerBusy(BilibiliConnectorError):
    pass


@contextmanager
def profile_lock(path: Path):
    """OS releases the lock if a controller crashes; no stale-PID deletion."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise BrowserControllerBusy("专用浏览器正在被另一条命令使用，请稍后再试") from None
        try:
            yield
        finally:
            stream.seek(0)
            if sys.platform == "win32":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def edge_executable() -> Path:
    for root in (os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"),
                 os.environ.get("PROGRAMFILES", "C:/Program Files"), os.environ.get("LOCALAPPDATA", "")):
        candidate = Path(root) / "Microsoft/Edge/Application/msedge.exe"
        if candidate.is_file():
            return candidate
    raise BilibiliConnectorError("未找到 Microsoft Edge，请先安装后再打开专用会话")


@contextmanager
def controller_lock(path: Path, *, timeout: float = 30):
    """Wait only for local ownership; never retry an HTTP request or a send."""
    deadline = time.monotonic() + timeout
    with ExitStack() as stack:
        while True:
            try:
                stack.enter_context(profile_lock(path))
                break
            except BrowserControllerBusy:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        yield


def debugger_url(profile: Path) -> str:
    try:
        content = (profile / "DevToolsActivePort").read_text(encoding="utf-8")
        if len(content) > 512:
            raise ValueError()
        port, path = content.splitlines()[:2]
        if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError()
        if not re.fullmatch(r"/devtools/browser/[0-9a-fA-F-]{36}", path):
            raise ValueError()
        return f"ws://127.0.0.1:{port}{path}"
    except (OSError, ValueError):
        raise BilibiliConnectorError("专用浏览器尚未启动或本机连接信息无效，请先运行 open") from None


class BrowserCDP:
    """Only loopback, with bounded messages and no raw protocol errors in output."""

    def __init__(self, profile: Path):
        from websockets.sync.client import connect
        self.socket = None
        try:
            self.socket = connect(debugger_url(profile), open_timeout=3, close_timeout=2,
                                  max_size=6 * MAX_BYTES, proxy=None)
        except BilibiliConnectorError:
            raise
        except Exception:
            raise BilibiliConnectorError("无法连接专用 Edge，请重新打开该会话") from None
        self.sequence = 0
        self.events: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass

    def receive(self, timeout: float = 0.5):
        try:
            row = json.loads(self.socket.recv(timeout=timeout))
            if not isinstance(row, dict):
                raise ValueError()
            return row
        except TimeoutError:
            return None
        except Exception:
            raise BilibiliConnectorError("专用浏览器连接中断，请检查窗口是否已关闭") from None

    def send_command(self, method: str, params: dict | None = None, session: str | None = None) -> int:
        self.sequence += 1
        identifier = self.sequence
        message = {"id": identifier, "method": method, "params": params or {}}
        if session:
            message["sessionId"] = session
        try:
            self.socket.send(json.dumps(message))
        except Exception:
            raise BilibiliConnectorError("无法向专用浏览器发送控制命令") from None
        return identifier

    def call(self, method: str, params: dict | None = None, session: str | None = None, *, timeout: float = 12):
        identifier = self.send_command(method, params, session)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            row = self.receive(min(0.5, max(0.01, deadline - time.monotonic())))
            if not row:
                continue
            if row.get("id") == identifier:
                if "error" in row:
                    raise BilibiliConnectorError("专用浏览器未完成控制命令")
                result = row.get("result", {})
                if not isinstance(result, dict):
                    raise BilibiliConnectorError("专用浏览器返回了无效的控制响应")
                return result
            if "method" in row:
                self.events.append(row)
                self.events[:] = self.events[-500:]
        raise BilibiliConnectorError("专用浏览器控制超时，请稍后再试")

    def account_response(self) -> tuple[int, dict, bytes]:
        target = self.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        try:
            # Omit browserContextId: use the persistent profile, not an incognito context.
            session = self.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
            self.call("Network.enable", {"maxResourceBufferSize": MAX_BYTES, "maxTotalBufferSize": 4 * MAX_BYTES}, session)
            self.call("Page.enable", session=session)
            self.call("Page.navigate", {"url": NAV_URL}, session)
            deadline = time.monotonic() + 20
            responses, finished = {}, set()
            while time.monotonic() < deadline:
                events, self.events = self.events, []
                for event in events:
                    if event.get("sessionId") != session:
                        continue
                    params = event.get("params", {})
                    if event.get("method") == "Network.responseReceived" and params.get("response", {}).get("url") == NAV_URL:
                        responses[params["requestId"]] = params["response"]
                    elif event.get("method") == "Network.loadingFinished":
                        finished.add(params["requestId"])
                for request_id, response in responses.items():
                    if request_id not in finished:
                        continue
                    result = self.call("Network.getResponseBody", {"requestId": request_id}, session)
                    value = result.get("body", "")
                    if not isinstance(value, str) or len(value) > 2 * MAX_BYTES:
                        raise BilibiliConnectorError("账号检查响应超过读取上限")
                    try:
                        raw = base64.b64decode(value, validate=True) if result.get("base64Encoded") else value.encode("utf-8")
                    except ValueError:
                        raise BilibiliConnectorError("账号检查响应编码异常") from None
                    if len(raw) > MAX_BYTES:
                        raise BilibiliConnectorError("账号检查响应超过读取上限")
                    return int(response["status"]), response.get("headers", {}), raw
                row = self.receive()
                if row and "method" in row:
                    self.events.append(row)
            raise BilibiliConnectorError("账号检查超时；未重试，也未读取视频或字幕")
        finally:
            try:
                self.call("Target.closeTarget", {"targetId": target}, timeout=3)
            except BilibiliConnectorError:
                pass


def account_status(http_status: int, raw: bytes, binding: BilibiliBinding) -> tuple[str, int | None]:
    """Classify locally without exposing account identifiers, names or server messages."""
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        return ("account_request_blocked" if http_status != 200 else "account_response_invalid"), None
    if not isinstance(payload, dict):
        return ("account_request_blocked" if http_status != 200 else "account_response_invalid"), None
    code = payload.get("code")
    code = code if type(code) is int and abs(code) < 10**9 else None
    if http_status != 200:
        return "account_request_blocked", code
    if code == -101:
        return "login_required", code
    if code != 0:
        return "account_request_blocked" if code in {-412, -352} else "account_response_invalid", code
    data = payload.get("data")
    if not isinstance(data, dict):
        return "account_response_invalid", code
    if data.get("isLogin") is False:
        return "login_required", code
    if data.get("isLogin") is not True or not re.fullmatch(r"[1-9][0-9]{0,18}", str(data.get("mid", ""))):
        return "account_response_invalid", code
    return ("logged_in" if str(data["mid"]) == binding.aike_mid else "account_mismatch"), code


class PersistentBrowser:
    def __init__(self, binding: BilibiliBinding, *, home: Path | None = None):
        binding.validate()
        self.binding = binding
        self.home = (home if home is not None else connector_home()).resolve()
        if self.home.is_relative_to(REPO_ROOT):
            raise BilibiliConnectorError("浏览器资料须保存在仓库外，请调整 AIKE_BILIBILI_HOME")
        self.profile = self.home / "browser-profile"
        self.marker = self.home / "browser-profile-binding.json"
        self.state = self.home / "browser-session.json"
        self.lock = self.home / "browser-controller.lock"
        identity = [binding.persona_id, binding.role_card_key, binding.aike_mid, binding.owner_mid]
        self.binding_hash = hashlib.sha256(json.dumps(identity, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()

    def prepare(self):
        if self.profile.resolve() != self.profile:
            raise BilibiliConnectorError("专用浏览器资料目录不能重定向到其他位置")
        if self.marker.exists():
            try:
                payload = json.loads(self.marker.read_text(encoding="utf-8"))
                valid = payload.get("version") == 1 and payload.get("binding_sha256") == self.binding_hash
            except (OSError, ValueError, AttributeError):
                valid = False
            if not valid:
                raise BilibiliConnectorError("浏览器资料与当前绑定不匹配，未复用或覆盖已有会话")
        else:
            if self.profile.exists() and any(self.profile.iterdir()):
                raise BilibiliConnectorError("发现未绑定的非空浏览器资料，停止自动接管")
            _atomic_write(self.marker, json.dumps({"version": 1, "binding_sha256": self.binding_hash}))
        self.profile.mkdir(parents=True, exist_ok=True)

    def save_status(self, status: str, **numbers):
        if status not in STATUSES:
            raise ValueError("Unsupported browser status")
        result = {"schema_version": 1, "status": status, "profile": str(self.profile),
                  "updated_at": datetime.now(timezone.utc).isoformat(), "persistent_profile": True,
                  "account_verified": status == "logged_in", "model_calls": 0, "messages_sent": 0}
        for key in ("http_status", "business_code"):
            value = numbers.get(key)
            if type(value) is int and abs(value) < 10**9:
                result[key] = value
        _atomic_write(self.state, json.dumps(result, ensure_ascii=False, indent=2))
        return result

    def open(self, *, wait_for_controller=False):
        with controller_lock(self.lock) if wait_for_controller else profile_lock(self.lock):
            self.prepare()
            try:
                with BrowserCDP(self.profile) as browser:
                    browser.call("Browser.getVersion", timeout=3)
                return {**self.save_status("browser_open"), "reused_process": True}
            except BilibiliConnectorError:
                pass
            if sys.platform != "win32":
                raise BilibiliConnectorError("专用 Edge 会话目前仅支持 Windows")
            executable = edge_executable()
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 1  # Interactive window is required for the user's QR login.
            try:
                process = subprocess.Popen([str(executable), "--user-data-dir=" + str(self.profile), "--profile-directory=Default",
                                            "--remote-debugging-port=0", "--remote-debugging-address=127.0.0.1",
                                            "--no-first-run", "--no-default-browser-check",
                                            "--autoplay-policy=user-gesture-required", LOGIN_URL],
                                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           startupinfo=startup, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            except OSError:
                raise BilibiliConnectorError("专用 Edge 启动失败，请检查安装与目录权限") from None
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    with BrowserCDP(self.profile) as browser:
                        browser.call("Browser.getVersion", timeout=3)
                    return {**self.save_status("browser_open"), "reused_process": False}
                except BilibiliConnectorError:
                    if process.poll() is not None:
                        break
                    time.sleep(0.25)
            self.save_status("browser_unreachable")
            raise BilibiliConnectorError("专用 Edge 尚未开放连接；若窗口已打开请关闭该专用窗口后重试")

    def check(self):
        import httpx
        with profile_lock(self.lock):
            self.prepare()
            diagnostics = DiagnosticLog(self.home / "logs")
            diagnostics.record("run_start", "runtime")
            try:
                with BrowserCDP(self.profile) as browser:
                    status_code, headers, raw = browser.account_response()
                diagnostics.record("http_response", "nav", **response_facts(httpx.Response(status_code, headers=headers), raw,
                                                                            truncated=False, elapsed_ms=0))
                status, code = account_status(status_code, raw, self.binding)
                diagnostics.record("check", "nav", check="account_binding", ok=status == "logged_in")
                result = self.save_status(status, http_status=status_code, business_code=code)
                diagnostics.record("run_end", "diagnose", outcome="ok" if status == "logged_in" else "source_error")
            except BilibiliConnectorError:
                self.save_status("browser_unreachable")
                diagnostics.record("run_end", "diagnose", outcome="source_error")
                raise
            return {**result, "diagnostics": diagnostics.public_status()}

    def status(self):
        with profile_lock(self.lock):
            self.prepare()
            try:
                result = json.loads(self.state.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                result = {}
            previous = result.get("status") if isinstance(result, dict) else None
            running = False
            try:
                with BrowserCDP(self.profile) as browser:
                    browser.call("Browser.getVersion", timeout=3)
                running = True
            except BilibiliConnectorError:
                pass
            return {"profile": str(self.profile), "persistent_profile": True, "browser_running": running,
                    "last_check_status": previous if isinstance(previous, str) and previous in STATUSES else "not_checked",
                    "live_account_check": False, "model_calls": 0, "messages_sent": 0}

    def close(self):
        with profile_lock(self.lock):
            self.prepare()
            with BrowserCDP(self.profile) as browser:
                browser.call("Browser.getVersion", timeout=3)
                # Closing a browser can close the socket before a reply is delivered.
                try:
                    browser.socket.send(json.dumps({"id": browser.sequence + 1, "method": "Browser.close"}))
                except Exception:
                    raise BilibiliConnectorError("未能关闭专用浏览器，请在专用窗口中手动关闭") from None
            return self.save_status("browser_closed")
