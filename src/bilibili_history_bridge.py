"""Pinned writers for real Bilibili interactions; transport delivery remains separate."""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .bilibili_connector import BilibiliConnectorError
from .bilibili_memory import open_pinned_history


class BilibiliHistoryWriter:
    def __init__(self, binding, config, *, root=None, home=None):
        self.binding = binding
        self.config = config
        self.store, self.scope, _ = open_pinned_history(binding, config, root=root, home=home)

    def record_owner_message(self, *, sender_mid: str, message_id: str, text: str,
                             sent_at: str | None, round_key: str | None = None,
                             bvid: str = "", video_title: str = "") -> int:
        if str(sender_mid) != self.binding.owner_mid:
            raise BilibiliConnectorError("非绑定主人消息不能进入 B 站私聊记忆")
        if not message_id.strip():
            raise ValueError("A platform message identity is required")
        return self.store.record_message(
            self.scope, message_key="in:" + message_id, round_key=round_key or "owner:" + message_id,
            role="user", content=text, occurred_at=sent_at,
            time_kind="platform_sent" if sent_at else "recorded_only", bvid=bvid, video_title=video_title,
        )

    def record_sent_reply(self, *, receiver_mid: str, message_id: str, round_key: str,
                          text: str, confirmed_at: str, bvid: str = "", video_title: str = "") -> int:
        if str(receiver_mid) != self.binding.owner_mid:
            raise BilibiliConnectorError("非绑定主人会话不能进入 B 站私聊记忆")
        if not message_id.strip():
            raise ValueError("A transport message identity is required")
        return self.store.record_message(
            self.scope, message_key="out:" + message_id, round_key=round_key,
            role="assistant", content=text, occurred_at=confirmed_at, time_kind="send_confirmed",
            bvid=bvid, video_title=video_title,
        )

    def record_share(self, binding, *, request_id: str, text: str, bvid: str, video_title: str) -> dict:
        if binding != self.binding:
            raise BilibiliConnectorError("分享与记忆的账号绑定不一致")
        self.record_sent_reply(
            receiver_mid=binding.owner_mid, message_id=request_id, round_key="share:" + request_id,
            text=text, confirmed_at=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            bvid=bvid, video_title=video_title,
        )
        # Archive first. Embedding failures can never undo a delivered message.
        try:
            from .plugins.ai_chat.rag.providers import build_embedding_provider
            indexed = self.store.index_pending(self.scope, build_embedding_provider(self.config), limit=16)
        except Exception:
            indexed = {"indexed": 0, "failed": 1}
        return {"status": "saved", "index": indexed}


def import_sent_reports(writer: BilibiliHistoryWriter, directory: Path, ledger: Path) -> dict:
    """Recover original sent text from reports with a matching, successful local receipt.

    No generation, report rewriting, credential reads or platform requests.
    Ledger timestamps precede POST and must not be called delivery timestamps.
    """
    counts = {"imported": 0, "already_saved": 0, "skipped": 0}
    if not ledger.is_file() or not directory.is_dir():
        return counts
    binding = writer.binding
    with closing(sqlite3.connect(ledger.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as c:
        c.execute("PRAGMA query_only=ON")
        for path in sorted(directory.glob("*.json")):
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(report, dict):
                    raise ValueError("Invalid report object")
                delivery = report.get("delivery", {})
                if not isinstance(delivery, dict):
                    raise ValueError("Invalid delivery object")
                if (report.get("withdrawal_reason") or report.get("status") not in {"ok", "partial"}
                        or delivery.get("status") != "sent" or delivery.get("platform_accepted") is not True
                        or delivery.get("business_code") != 0):
                    counts["skipped"] += 1
                    continue
                bvid, request_id = delivery["bvid"], delivery["request_id"]
                if (not isinstance(bvid, str) or not re.fullmatch(r"BV[0-9A-Za-z]{10}", bvid)
                        or not isinstance(request_id, str) or not request_id.strip()):
                    raise ValueError("Invalid delivery reference")
                key = hashlib.sha256(json.dumps([binding.aike_mid, binding.owner_mid, "explicit", "video-share-v1:" + bvid],
                                               ensure_ascii=False).encode()).hexdigest()
                receipt = c.execute("SELECT created_at FROM deliveries WHERE request_id=? AND delivery_key=? AND state='sent' AND code=0",
                                    (request_id, key)).fetchone()
                if receipt is None:
                    raise ValueError("No matching successful receipt")
                result = next(r for r in report["results"] if r["bvid"] == bvid)
                draft = result["draft"]
                if not isinstance(draft, str) or not draft.strip() or len(draft) > 300:
                    raise ValueError("Invalid archived message")
                previous = writer.store.get_message(writer.scope, "out:" + request_id)
                if previous is not None:
                    if previous.content != draft or previous.bvid != bvid:
                        raise ValueError("Conflicting original message")
                    counts["already_saved"] += 1
                    continue
                attempted = datetime.fromtimestamp(receipt[0], timezone.utc).isoformat(timespec="microseconds")
                writer.store.record_message(
                    writer.scope, message_key="out:" + request_id, round_key="share:" + request_id,
                    role="assistant", content=draft, occurred_at=attempted, time_kind="send_attempt",
                    bvid=bvid, video_title=str(result.get("title", "")),
                )
                counts["imported"] += 1
            except (KeyError, TypeError, ValueError, StopIteration, OSError, OverflowError):
                counts["skipped"] += 1
    return counts
