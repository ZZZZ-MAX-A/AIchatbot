"""Owner-only browser inbox, durable receive cursor and conservative reply delivery."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import sqlite3
import time
import uuid

from .bilibili_autobrowse import AutoBrowseStore, BEIJING
from .bilibili_browser import PersistentBrowser, BrowserControllerBusy, profile_lock
from .bilibili_browser_browse import browser_browse_client
from .bilibili_browser_transport import INBOX_PATH
from .bilibili_connector import BindingStore, BilibiliConnectorError, _atomic_write


@dataclass(frozen=True)
class InboxPolicy:
    min_poll_seconds: int = 30
    max_poll_seconds: int = 60
    debounce_seconds: int = 4
    max_merge_seconds: int = 15
    max_batch_messages: int = 10
    max_batch_characters: int = 8000
    error_backoff_seconds: int = 900

    def validate(self):
        if (any(type(v) is not int for v in asdict(self).values())
                or not 15 <= self.min_poll_seconds <= self.max_poll_seconds <= 600
                or not 3 <= self.debounce_seconds <= self.max_merge_seconds <= 30
                or not 1 <= self.max_batch_messages <= 20
                or not 1000 <= self.max_batch_characters <= 16000
                or not 300 <= self.error_backoff_seconds <= 14400):
            raise ValueError("Invalid inbox policy")

    @classmethod
    def load(cls, path):
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise ValueError("Invalid inbox configuration")
        policy = cls(**data)
        policy.validate()
        return policy


class InboxStore(AutoBrowseStore):
    def __init__(self, home: Path, scope: str):
        super().__init__(home, scope)
        self.path = home / "inbox.sqlite3"
        self.session_path = home / "inbox-session.json"
        self.lock_path = home / "inbox.lock"
        self.stop_path = home / "inbox-stop.json"

    @contextmanager
    def connect(self, *, write=False):
        if write:
            self.home.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path, timeout=3)
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS job_state(scope TEXT PRIMARY KEY,payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS inbox_messages(
                    scope TEXT NOT NULL,seq INTEGER NOT NULL,message_id TEXT NOT NULL,payload TEXT NOT NULL,
                    received REAL NOT NULL,batch_id TEXT,PRIMARY KEY(scope,seq),UNIQUE(scope,message_id));
                CREATE TABLE IF NOT EXISTS inbox_batches(
                    scope TEXT NOT NULL,id TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL,
                    draft TEXT NOT NULL DEFAULT '',request_id TEXT NOT NULL DEFAULT '',confirmed_at TEXT NOT NULL DEFAULT '',
                    archived INTEGER NOT NULL DEFAULT 0,usage TEXT NOT NULL DEFAULT '[]',
                    confirmation_kind TEXT NOT NULL DEFAULT 'send_confirmed',PRIMARY KEY(scope,id));
            """)
        else:
            connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self, cursor: int):
        with self.connect(write=True) as c, c:
            self._update(c, {"initialized": True, "cursor": cursor, "initialized_at": time.time()})

    def ingest(self, messages: list[dict], cursor: int, now: float) -> int:
        count = 0
        with self.connect(write=True) as c, c:
            c.execute("BEGIN IMMEDIATE")
            previous = int(self.state().get("cursor", 0))
            for message in sorted(messages, key=lambda m: m["seq"]):
                if message["seq"] <= previous or message["role"] != "user":
                    continue
                encoded = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
                old = c.execute("SELECT payload FROM inbox_messages WHERE scope=? AND (seq=? OR message_id=?)",
                                (self.scope, message["seq"], message["message_id"])).fetchone()
                if old is not None:
                    if old[0] != encoded:
                        raise ValueError("Conflicting platform message")
                    continue
                c.execute("INSERT INTO inbox_messages VALUES(?,?,?,?,?,NULL)",
                          (self.scope, message["seq"], message["message_id"], encoded, now))
                count += 1
            self._update(c, {"cursor": max(previous, cursor), "last_poll_at": now})
        return count

    def pending_window(self):
        if not self.path.is_file():
            return None
        with self.connect() as c:
            row = c.execute("SELECT MIN(received),MAX(received) FROM inbox_messages WHERE scope=? AND batch_id IS NULL",
                            (self.scope,)).fetchone()
        return tuple(row) if row[0] is not None else None

    def create_batch(self, now: float, policy: InboxPolicy):
        with self.connect(write=True) as c, c:
            c.execute("BEGIN IMMEDIATE")
            rows = c.execute("SELECT * FROM inbox_messages WHERE scope=? AND batch_id IS NULL ORDER BY seq LIMIT ?",
                             (self.scope, policy.max_batch_messages)).fetchall()
            if not rows:
                return None
            selected, characters = [], 0
            for row in rows:
                size = len(json.loads(row["payload"])["text"])
                if selected and characters + size > policy.max_batch_characters:
                    break
                characters += size
                selected.append(row)
            key = hashlib.sha256((self.scope + ":" + ",".join(str(r["seq"]) for r in selected)).encode()).hexdigest()
            c.execute("INSERT INTO inbox_batches(scope,id,status,created) VALUES(?,?,'generating',?)", (self.scope, key, now))
            for row in selected:
                c.execute("UPDATE inbox_messages SET batch_id=? WHERE scope=? AND seq=?", (key, self.scope, row["seq"]))
        return key

    def batch(self, key: str):
        with self.connect() as c:
            row = c.execute("SELECT * FROM inbox_batches WHERE scope=? AND id=?", (self.scope, key)).fetchone()
            if row is None:
                raise ValueError("Missing inbox batch")
            messages = [json.loads(r[0]) for r in c.execute(
                "SELECT payload FROM inbox_messages WHERE scope=? AND batch_id=? ORDER BY seq", (self.scope, key))]
        return {**dict(row), "messages": messages}

    def finish(self, key, status, **fields):
        if set(fields) - {"draft", "request_id", "confirmed_at", "archived", "usage", "confirmation_kind"}:
            raise ValueError("Invalid inbox batch patch")
        values = {"status": status, **fields}
        with self.connect(write=True) as c, c:
            c.execute("UPDATE inbox_batches SET " + ",".join(k + "=?" for k in values) + " WHERE scope=? AND id=?",
                      (*values.values(), self.scope, key))

    def recover(self):
        with self.connect(write=True) as c, c:
            c.execute("UPDATE inbox_batches SET status='interrupted' WHERE scope=? AND status='generating'", (self.scope,))

    def unfinished(self):
        if not self.path.is_file():
            return []
        with self.connect() as c:
            return [(r[0], r[1]) for r in c.execute(
                "SELECT id,status FROM inbox_batches WHERE scope=? AND (status IN ('ready','sending') OR (status='sent' AND archived=0)) ORDER BY created",
                (self.scope,))]

    def counts(self):
        if not self.path.is_file():
            return {}
        with self.connect() as c:
            counts = {r[0]: r[1] for r in c.execute("SELECT status,COUNT(*) FROM inbox_batches WHERE scope=? GROUP BY status", (self.scope,))}
            counts["pending_messages"] = c.execute("SELECT COUNT(*) FROM inbox_messages WHERE scope=? AND batch_id IS NULL", (self.scope,)).fetchone()[0]
        return counts


def platform_integer(value, *, positive=False):
    if type(value) is int:
        number = value
    elif isinstance(value, str) and re.fullmatch(r"[0-9]{1,19}", value):
        number = int(value)
    else:
        raise ValueError("Invalid platform integer")
    if not int(positive) <= number <= 2**63 - 1:
        raise ValueError("Platform integer outside range")
    return number


def normalize_message(raw: dict, binding) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Invalid inbox message")
    sender, receiver = str(raw.get("sender_uid")), str(raw.get("receiver_id"))
    pair = (sender, receiver)
    if pair not in {(binding.owner_mid, binding.aike_mid), (binding.aike_mid, binding.owner_mid)} or platform_integer(raw.get("receiver_type")) != 1:
        raise ValueError("Message outside bound owner conversation")
    seq = platform_integer(raw.get("msg_seqno"), positive=True)
    message_id = str(platform_integer(raw.get("msg_key"), positive=True))
    timestamp = platform_integer(raw.get("timestamp"), positive=True)
    if timestamp > time.time() + 300 or timestamp < 946684800:
        raise ValueError("Invalid message timestamp")
    stamp = datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="seconds")
    kind = platform_integer(raw.get("msg_type"))
    status = platform_integer(raw.get("msg_status", 0))
    content = raw.get("content")
    if not isinstance(content, str) or len(content) > 64000:
        raise ValueError("Invalid message content")
    content = json.loads(content)
    if not isinstance(content, dict):
        raise ValueError("Invalid message body")
    body = content.get("content", "") if kind == 1 else ""
    if kind == 1 and (not isinstance(body, str) or not body.strip() or len(body) > 8000):
        raise ValueError("Invalid text message")
    if status != 0 or kind == 5:
        body = "[消息已撤回或当前不可用，不能回应其内容]"
    elif kind != 1:
        body = "[主人发来非文字消息，当前尚未解析此消息的内容]"
    return {"seq": seq, "message_id": message_id, "role": "user" if sender == binding.owner_mid else "assistant",
            "text": body.strip(), "sent_at": stamp, "type": kind, "unavailable": status != 0 or kind == 5}


def fetch_messages(client, binding, *, cursor=None, should_stop=lambda: False, max_pages=20):
    """Page backwards until the saved cursor; never advance over an unread gap."""
    gathered, seen_pages, end = {}, set(), None
    for _ in range(max_pages):
        if should_stop():
            raise BilibiliConnectorError("收件已停止")
        params = {"talker_id": binding.owner_mid, "session_type": 1, "size": 50, "build": 0, "mobi_app": "web"}
        if end is not None:
            params["end_seqno"] = end
        response = client._client.get("https://api.vc.bilibili.com" + INBOX_PATH, params=params, follow_redirects=False)
        if response.status_code in {412, 429}:
            raise InboxBlocked()
        payload = client._json(response)
        if payload.get("code") in {-412, -352}:
            raise InboxBlocked()
        data = payload.get("data")
        if type(payload.get("code")) is not int or payload["code"] != 0 or not isinstance(data, dict):
            raise BilibiliConnectorError("私信读取状态异常")
        rows = data.get("messages")
        if rows is None:
            rows = []
        if not isinstance(rows, list) or len(rows) > 50 or data.get("has_more") not in (0, 1, False, True):
            raise ValueError("Invalid inbox page")
        normalized = [normalize_message(row, binding) for row in rows]
        if not normalized and data["has_more"]:
            raise ValueError("Empty inbox page claims more messages")
        # Use the returned message boundary, not a possibly global max_seqno.
        for message in normalized:
            previous = gathered.get(message["seq"])
            if previous is not None and previous != message:
                raise ValueError("Conflicting message pagination")
            gathered[message["seq"]] = message
        if cursor is None:
            return sorted(gathered.values(), key=lambda m: m["seq"]), max(gathered, default=0)
        if not normalized or min(m["seq"] for m in normalized) <= cursor or not data["has_more"]:
            return [m for _, m in sorted(gathered.items()) if m["seq"] > cursor], max([cursor, *gathered])
        boundary = min(m["seq"] for m in normalized)
        if boundary in seen_pages or end is not None and boundary >= end:
            raise ValueError("Inbox pagination did not advance")
        seen_pages.add(boundary)
        end = boundary
    raise BilibiliConnectorError("未完成私信增量同步，保留原游标")


class InboxBlocked(BilibiliConnectorError):
    pass


@contextmanager
def inbox_browser(binding, home):
    manager = PersistentBrowser(binding, home=home)
    manager.open(wait_for_controller=True)
    with browser_browse_client(None, binding, manager=manager, short_locks=True) as browser:
        yield browser


def poll_inbox(store, binding, *, should_stop=lambda: False):
    if BindingStore(store.home / "binding.json").load() != binding:
        raise BilibiliConnectorError("私信绑定发生变化")
    state = store.state()
    with inbox_browser(binding, store.home) as browser:
        messages, cursor = fetch_messages(browser.account_client, binding,
            cursor=state.get("cursor") if state.get("initialized") else None, should_stop=should_stop)
    if should_stop():
        return {"status": "cancelled", "received": 0}
    if not state.get("initialized"):
        store.initialize(cursor)
        return {"status": "initialized", "received": 0}
    count = store.ingest(messages, cursor, time.time())
    return {"status": "ok", "received": count}


def reply_delivery(binding, key: str, home: Path):
    path = home / "deliveries.sqlite3"
    if not path.is_file():
        return None
    delivery_key = hashlib.sha256(json.dumps([binding.aike_mid, binding.owner_mid, "explicit", "inbox-reply-v1:" + key], ensure_ascii=False).encode()).hexdigest()
    c = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3)
    try:
        row = c.execute("SELECT request_id,state,created_at FROM deliveries WHERE delivery_key=?", (delivery_key,)).fetchone()
        return {"request_id": row[0], "state": row[1], "created_at": row[2]} if row else None
    finally:
        c.close()


def archive_reply(store, key, writer):
    batch = store.batch(key)
    if batch["status"] != "sent" or not batch["request_id"]:
        return
    if batch["confirmation_kind"] == "send_attempt":
        writer.store.record_message(writer.scope, message_key="out:" + batch["request_id"],
            round_key="inbox:" + key, role="assistant", content=batch["draft"],
            occurred_at=batch["confirmed_at"], time_kind="send_attempt")
    else:
        writer.record_sent_reply(receiver_mid=writer.binding.owner_mid, message_id=batch["request_id"],
            round_key="inbox:" + key, text=batch["draft"], confirmed_at=batch["confirmed_at"])
    store.finish(key, "sent", archived=1)
    try:
        from .plugins.ai_chat.rag.providers import build_embedding_provider
        writer.store.index_pending(writer.scope, build_embedding_provider(writer.config), limit=16)
    except Exception:
        pass


def deliver_reply(store, binding, key, writer, *, should_stop=lambda: False):
    if BindingStore(store.home / "binding.json").load() != binding:
        raise BilibiliConnectorError("私信绑定发生变化")
    batch = store.batch(key)
    receipt = reply_delivery(binding, key, store.home)
    if receipt:
        if receipt["state"] == "sent":
            stamp = batch["confirmed_at"] or datetime.fromtimestamp(receipt["created_at"], timezone.utc).isoformat(timespec="microseconds")
            kind = batch["confirmation_kind"] if batch["confirmed_at"] else "send_attempt"
            store.finish(key, "sent", request_id=receipt["request_id"], confirmed_at=stamp, confirmation_kind=kind)
            archive_reply(store, key, writer)
            return "sent"
        store.finish(key, "failed" if receipt["state"] == "failed" else "unknown", request_id=receipt["request_id"])
        return "failed_or_unknown"
    if should_stop():
        return "cancelled"
    with inbox_browser(binding, store.home) as browser:
        if should_stop():
            return "cancelled"
        store.finish(key, "sending")
        try:
            result = browser.account_client.send_private_message(binding, batch["draft"], dry_run=False,
                                                                 delivery_key="inbox-reply-v1:" + key)
        except Exception:
            receipt = reply_delivery(binding, key, store.home)
            store.finish(key, "failed" if receipt is None or receipt["state"] == "failed" else "unknown",
                         request_id=receipt["request_id"] if receipt else "")
            return "failed_or_unknown"
    if not result.sent or result.dry_run or result.code != 0 or not result.request_id:
        store.finish(key, "failed")
        return "failed_or_unknown"
    stamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    store.finish(key, "sent", request_id=result.request_id, confirmed_at=stamp)
    archive_reply(store, key, writer)
    return "sent"


def generate_reply(store, binding, config, key, *, should_stop=lambda: False):
    from .bilibili_history_bridge import BilibiliHistoryWriter
    from .bilibili_memory import load_owner_memory
    from .bilibili_persona import PersonaModel, persona_settings
    if BindingStore(store.home / "binding.json").load() != binding:
        raise BilibiliConnectorError("私信绑定发生变化")
    batch = store.batch(key)
    writer = BilibiliHistoryWriter(binding, config, home=store.home)
    for message in batch["messages"]:
        writer.record_owner_message(sender_mid=binding.owner_mid, message_id=message["message_id"],
            text=message["text"], sent_at=message["sent_at"], round_key="inbox:" + key)
    if all(m["unavailable"] for m in batch["messages"]):
        store.finish(key, "ignored")
        return "ignored"
    if should_stop():
        store.finish(key, "interrupted")
        return "cancelled"
    current_ids = {"in:" + m["message_id"] for m in batch["messages"]}
    snapshot = writer.store.snapshot(writer.scope, provider=getattr(config, "memory_rag_embedding_provider", ""),
        model=getattr(config, "memory_rag_embedding_model", ""), recent_rounds=3)
    recent = snapshot.recent
    background = [{"role": m.role, "text": m.content[:1500], "sent_at": m.occurred_at}
                  for m in recent if m.message_key not in current_ids][-12:]
    model = PersonaModel(*persona_settings(binding, config=config), memory=load_owner_memory(binding, config))
    try:
        text = "\n".join(m["text"] for m in batch["messages"])
        recalled = []
        recent_ids = {m.id for m in recent}
        candidates = [(m, vector) for m, vector in snapshot.candidates if m.id not in recent_ids and m.message_key not in current_ids]
        if candidates and getattr(config, "bilibili_history_rag_enabled", True):
            try:
                from .plugins.ai_chat.rag.providers import build_embedding_provider
                from .plugins.ai_chat.rag.search import cosine_similarity
                embedder = build_embedding_provider(config)
                vector = (getattr(embedder, "embed_once", None) or embedder.embed)(text)
                ranked = []
                for message, embedding in candidates:
                    if len(vector) != len(embedding):
                        continue
                    score = cosine_similarity(vector, embedding)
                    if math.isfinite(score) and score >= float(getattr(config, "memory_rag_min_score", 0.5)):
                        ranked.append((score, message.id, message))
                recalled = [{"role": m.role, "text": m.content[:600], "sent_at": m.occurred_at}
                            for _, _, m in sorted(ranked, key=lambda row: row[:2], reverse=True)[:5]]
            except Exception:
                pass
        daily_note = None
        if any(word in text for word in ("今天", "视频", "看了", "刷了")):
            try:
                from .bilibili_daily_note import BilibiliDailyNoteStore
                note = BilibiliDailyNoteStore(store.home / "daily-note.sqlite3").read_today(writer.scope)
                if note:
                    daily_note = {"day": note["day"], "text": note["text"][:2000]}
            except Exception:
                pass
        current = [{k: m[k] for k in ("text", "sent_at", "type", "unavailable")} for m in batch["messages"]]
        payload = model.ask("reply", {"query": text, "owner_current_messages": current,
            "bilibili_recent": background, "bilibili_recalled": recalled, "daily_note": daily_note,
            "current_time": datetime.now(BEIJING).isoformat(timespec="seconds"), "video_content_available": False})
        draft = payload.get("reply")
        if not isinstance(draft, str) or not 1 <= len(draft.strip()) <= 300:
            raise ValueError("Invalid reply draft")
        store.finish(key, "ready", draft=draft.strip(), usage=json.dumps(model.usage, ensure_ascii=False))
    except Exception:
        store.finish(key, "generation_failed", usage=json.dumps(model.usage, ensure_ascii=False))
        return "generation_failed"
    finally:
        model.close()
    return deliver_reply(store, binding, key, writer, should_stop=should_stop)


def run_inbox(store, binding, config, policy, *, once=False, emit=None, clock=time.time, sleep=time.sleep, rng=None):
    emit = emit or (lambda row: None)
    rng = rng or random.SystemRandom()
    policy.validate()
    with profile_lock(store.lock_path):
        run_id = uuid.uuid4().hex
        store.recover()
        previous = store.state()
        store.update_state(run_id=run_id, pid=os.getpid(), phase="waiting", started_at=clock(),
                           next_poll=max(clock(), previous.get("next_poll", 0)))
        _atomic_write(store.session_path, json.dumps({"scope": store.scope, "run_id": run_id, "pid": os.getpid()}))
        should_stop = lambda: store.should_stop(run_id)
        emit({"event": "inbox_started"})
        try:
            while not should_stop():
                now = clock()
                state = store.state()
                if now < state.get("retry_not_before", 0):
                    if state.get("phase") != "backoff":
                        store.update_state(phase="backoff")
                    if once:
                        return {"status": "waiting"}
                    sleep(1)
                    continue
                window = store.pending_window()
                merging = bool(window and (now - window[1] >= policy.debounce_seconds or now - window[0] >= policy.max_merge_seconds))
                if now >= state.get("next_poll", 0) or (merging and now - state.get("last_poll_at", 0) >= policy.debounce_seconds):
                    try:
                        result = poll_inbox(store, binding, should_stop=should_stop)
                        store.update_state(phase="waiting", last_result=result["status"], last_poll_at=clock(),
                                           next_poll=clock() + rng.randint(policy.min_poll_seconds, policy.max_poll_seconds))
                        emit({"event": "inbox_polled", **result})
                    except Exception as error:
                        delay = (policy.min_poll_seconds if isinstance(error, BrowserControllerBusy) else
                                 max(14400 if isinstance(error, InboxBlocked) else 0, policy.error_backoff_seconds))
                        store.update_state(phase="backoff", last_result="blocked" if isinstance(error, InboxBlocked) else "poll_failed",
                                           last_error_kind=type(error).__name__, next_poll=clock() + delay, retry_not_before=clock() + delay)
                        emit({"event": "inbox_poll_failed", "retry_after_seconds": delay})
                        if once:
                            return {"status": "poll_failed"}
                        continue
                if should_stop():
                    break
                try:
                    from .bilibili_history_bridge import BilibiliHistoryWriter
                    if clock() >= store.state().get("next_recovery", 0):
                        store.update_state(next_recovery=clock() + policy.min_poll_seconds)
                        for key, _ in store.unfinished():
                            if should_stop():
                                break
                            writer = BilibiliHistoryWriter(binding, config, home=store.home)
                            deliver_reply(store, binding, key, writer, should_stop=should_stop)
                    window = store.pending_window()
                    if window and (clock() - window[1] >= policy.debounce_seconds or clock() - window[0] >= policy.max_merge_seconds):
                        key = store.create_batch(clock(), policy)
                        if key:
                            store.update_state(phase="replying")
                            result = generate_reply(store, binding, config, key, should_stop=should_stop)
                            store.update_state(phase="waiting", last_reply=result, last_reply_at=clock())
                            if result == "failed_or_unknown":
                                store.update_state(retry_not_before=clock() + policy.error_backoff_seconds,
                                                   next_poll=clock() + policy.error_backoff_seconds)
                            emit({"event": "inbox_reply", "status": result})
                except Exception:
                    store.update_state(phase="waiting", last_reply="reply_failed", next_recovery=clock() + policy.error_backoff_seconds)
                    emit({"event": "inbox_reply_failed"})
                if once:
                    return {"status": "checked"}
                sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            store.update_state(phase="stopped", stopped_at=clock())
            emit({"event": "inbox_stopped"})
    return {"status": "stopped"}
