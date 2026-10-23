"""Durable Bilibili messages and their own index; never opens a QQ database."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3


MAPPING_KEYS = (
    "version", "persona_id", "role_card_key", "bilibili_aike_uid", "bilibili_owner_uid",
    "qq_aike_uid", "qq_owner_uid", "qq_session", "storage_mode",
)


def _stamp(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Message time must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class HistoryScope:
    key: str = field(repr=False)

    @classmethod
    def from_mapping(cls, mapping: dict):
        if mapping.get("version") != 1 or any(not str(mapping.get(k, "")).strip() for k in MAPPING_KEYS):
            raise ValueError("Incomplete cross-platform identity")
        encoded = json.dumps({k: mapping[k] for k in MAPPING_KEYS}, sort_keys=True, separators=(",", ":"))
        return cls(hashlib.sha256(encoded.encode("utf-8")).hexdigest())


@dataclass(frozen=True)
class BilibiliMessage:
    id: int
    message_key: str = field(repr=False)
    round_key: str = field(repr=False)
    role: str
    content: str = field(repr=False)
    occurred_at: str | None
    recorded_at: str
    time_kind: str
    bvid: str = ""
    video_title: str = field(default="", repr=False)

    def index_text(self) -> str:
        # Titles give a shared video reference, not evidence of its contents.
        return "\n".join(filter(None, (self.video_title, self.bvid, self.role + ": " + self.content)))

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.index_text().encode("utf-8")).hexdigest()


@dataclass
class HistorySnapshot:
    recent: list[BilibiliMessage] = field(default_factory=list, repr=False)
    candidates: list[tuple[BilibiliMessage, list[float]]] = field(default_factory=list, repr=False)
    status: str = "missing"
    unindexed_messages: int = 0


def _message(row) -> BilibiliMessage:
    return BilibiliMessage(**{k: row[k] for k in BilibiliMessage.__dataclass_fields__})


def _vector(value) -> list[float]:
    if not isinstance(value, list) or not value or any(isinstance(v, bool) for v in value):
        raise ValueError("Invalid embedding")
    result = [float(v) for v in value]
    if not all(math.isfinite(v) for v in result) or not any(result):
        raise ValueError("Invalid embedding")
    return result


class BilibiliHistoryStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _write_connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=3)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS bili_messages (
                id INTEGER PRIMARY KEY, scope TEXT NOT NULL, message_key TEXT NOT NULL,
                round_key TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL, occurred_at TEXT, recorded_at TEXT NOT NULL,
                time_kind TEXT NOT NULL, bvid TEXT NOT NULL, video_title TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1, UNIQUE(scope,message_key)
            );
            CREATE INDEX IF NOT EXISTS bili_messages_scope_round ON bili_messages(scope,round_key,id);
            CREATE TABLE IF NOT EXISTS bili_embeddings (
                message_id INTEGER NOT NULL REFERENCES bili_messages(id) ON DELETE CASCADE,
                provider TEXT NOT NULL, model TEXT NOT NULL, content_hash TEXT NOT NULL,
                vector TEXT NOT NULL, PRIMARY KEY(message_id,provider,model)
            );
        """)
        return connection

    def record_message(self, scope: HistoryScope, *, message_key: str, round_key: str,
                       role: str, content: str, occurred_at: str | None = None,
                       time_kind: str = "recorded_only", bvid: str = "", video_title: str = "") -> int:
        """Call only for received owner messages or transport-accepted replies.

        A stable platform key makes reprocessing idempotent. Outbound-only
        shares are real rounds; they never synthesize a message from the owner.
        """
        if not message_key.strip() or not round_key.strip() or role not in {"user", "assistant"} or not content.strip():
            raise ValueError("Invalid Bilibili message")
        if time_kind not in {"platform_sent", "send_confirmed", "send_attempt", "recorded_only"}:
            raise ValueError("Invalid message time source")
        occurred_at = _stamp(occurred_at)
        if time_kind != "recorded_only" and occurred_at is None:
            raise ValueError("Confirmed message time is required")
        if time_kind == "recorded_only" and occurred_at is not None:
            raise ValueError("Unconfirmed records cannot claim a sent time")
        values = (scope.key, message_key, round_key, role, content, occurred_at, time_kind, bvid, video_title)
        with closing(self._write_connection()) as c, c:
            previous = c.execute("SELECT * FROM bili_messages WHERE scope=? AND message_key=?", values[:2]).fetchone()
            if previous is not None:
                keys = ("scope", "message_key", "round_key", "role", "content", "occurred_at", "time_kind", "bvid", "video_title")
                if tuple(previous[k] for k in keys) != values or not previous["active"]:
                    raise ValueError("Conflicting or retracted Bilibili message")
                return int(previous["id"])
            cursor = c.execute("""INSERT INTO bili_messages
                (scope,message_key,round_key,role,content,occurred_at,time_kind,bvid,video_title,recorded_at)
                VALUES(?,?,?,?,?,?,?,?,?,?)""", (*values, _now()))
            return int(cursor.lastrowid)

    def get_message(self, scope: HistoryScope, message_key: str) -> BilibiliMessage | None:
        if not self.path.is_file():
            return None
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as c:
            c.row_factory = sqlite3.Row
            row = c.execute("SELECT * FROM bili_messages WHERE scope=? AND message_key=? AND active=1",
                            (scope.key, message_key)).fetchone()
            return _message(row) if row is not None else None

    def snapshot(self, scope: HistoryScope, *, provider: str, model: str, recent_rounds: int = 3) -> HistorySnapshot:
        if not self.path.is_file():
            return HistorySnapshot()
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as c:
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA query_only=ON")
            c.execute("BEGIN")
            rounds = [r[0] for r in c.execute("""SELECT round_key FROM bili_messages
                WHERE scope=? AND active=1 GROUP BY round_key
                ORDER BY MAX(COALESCE(occurred_at,recorded_at)) DESC, MAX(id) DESC LIMIT ?""",
                (scope.key, max(0, recent_rounds)))]
            recent = []
            if rounds:
                placeholders = ",".join("?" for _ in rounds)
                recent = [_message(r) for r in c.execute(f"""SELECT * FROM bili_messages
                    WHERE scope=? AND active=1 AND round_key IN ({placeholders})
                    ORDER BY COALESCE(occurred_at,recorded_at),id""", (scope.key, *rounds))]
            candidates = []
            indexed_ids = set()
            for row in c.execute("""SELECT m.*,e.vector,e.content_hash FROM bili_messages m
                JOIN bili_embeddings e ON e.message_id=m.id
                WHERE m.scope=? AND m.active=1 AND e.provider=? AND e.model=?""", (scope.key, provider, model)):
                message = _message(row)
                if message.content_hash != row["content_hash"]:
                    continue
                try:
                    vector = _vector(json.loads(row["vector"]))
                except (TypeError, ValueError, OverflowError):
                    continue
                candidates.append((message, vector))
                indexed_ids.add(message.id)
            total = c.execute("SELECT COUNT(*) FROM bili_messages WHERE scope=? AND active=1", (scope.key,)).fetchone()[0]
        return HistorySnapshot(recent, candidates, "ready" if total else "empty", total - len(indexed_ids))

    def index_pending(self, scope: HistoryScope, embedder, *, limit: int = 64) -> dict:
        """Index only this Bilibili store. Never index missing documents in a QQ request."""
        snapshot = self.snapshot(scope, provider=embedder.provider, model=embedder.model, recent_rounds=0)
        if snapshot.status == "missing":
            return {"indexed": 0, "failed": 0}
        known = {m.id for m, _ in snapshot.candidates}
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as c:
            c.row_factory = sqlite3.Row
            pending = [_message(r) for r in c.execute("SELECT * FROM bili_messages WHERE scope=? AND active=1 ORDER BY id", (scope.key,))
                       if r["id"] not in known][:max(0, limit)]
        indexed = failed = 0
        for message in pending:
            try:
                embed = getattr(embedder, "embed_once", None) or embedder.embed
                vector = _vector(embed(message.index_text()))
                with closing(self._write_connection()) as c, c:
                    row = c.execute("SELECT * FROM bili_messages WHERE id=? AND scope=? AND active=1", (message.id, scope.key)).fetchone()
                    if row is None or _message(row).content_hash != message.content_hash:
                        continue
                    c.execute("INSERT OR REPLACE INTO bili_embeddings VALUES(?,?,?,?,?)",
                              (message.id, embedder.provider, embedder.model, message.content_hash, json.dumps(vector)))
                indexed += 1
            except Exception:
                # Retain the full original message, and never print provider payloads.
                failed += 1
                break
        return {"indexed": indexed, "failed": failed}

    def retract(self, scope: HistoryScope, message_key: str) -> None:
        if not self.path.is_file():
            return
        with closing(self._write_connection()) as c, c:
            c.execute("DELETE FROM bili_embeddings WHERE message_id IN (SELECT id FROM bili_messages WHERE scope=? AND message_key=?)",
                      (scope.key, message_key))
            c.execute("UPDATE bili_messages SET active=0 WHERE scope=? AND message_key=?", (scope.key, message_key))
