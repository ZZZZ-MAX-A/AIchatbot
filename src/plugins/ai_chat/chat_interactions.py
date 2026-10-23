"""Successful owner interactions, independent of message/memory databases.

Only identity, timestamps and delivery metadata are stored. Reads never create
or migrate a database; history cleanup and persona DB scopes do not affect it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


INTERACTION_DATABASE_PATH = Path(__file__).resolve().parents[3] / "data" / "chat-interactions.db"


@dataclass(frozen=True)
class InteractionKey:
    bot_self_id: str
    persona_id: str
    owner_id: str

    def values(self) -> tuple[str, str, str]:
        values = (self.bot_self_id.strip(), self.persona_id.strip(), self.owner_id.strip())
        if not all(values):
            raise ValueError("interaction identity must be complete")
        return values


@dataclass(frozen=True)
class SuccessfulInteraction:
    succeeded_at: str
    source: str


class InteractionStore:
    def __init__(self, path: Path = INTERACTION_DATABASE_PATH):
        self.path = Path(path)

    def latest(self, key: InteractionKey) -> SuccessfulInteraction | None:
        values = key.values()
        if not self.path.is_file():
            return None
        connection = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            row = connection.execute(
                "SELECT succeeded_at, source FROM owner_interactions "
                "WHERE bot_self_id = ? AND persona_id = ? AND owner_id = ?", values,
            ).fetchone()
        finally:
            connection.close()
        return SuccessfulInteraction(*row) if row else None

    def record_success(
        self, key: InteractionKey, *, source: str, succeeded_at: datetime | None = None,
    ) -> None:
        values = key.values()
        if source not in {"private", "group"}:
            raise ValueError("interaction source must be private or group")
        now = succeeded_at if succeeded_at is not None else datetime.now(timezone.utc)
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("interaction time must be timezone aware")
        timestamp = now.astimezone(timezone.utc).isoformat(timespec="microseconds")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS owner_interactions ("
                    "bot_self_id TEXT NOT NULL, persona_id TEXT NOT NULL, owner_id TEXT NOT NULL, "
                    "succeeded_at TEXT NOT NULL, source TEXT NOT NULL, "
                    "PRIMARY KEY (bot_self_id, persona_id, owner_id))"
                )
                # A delayed completion must never move the shared clock backwards.
                connection.execute(
                    "INSERT INTO owner_interactions VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(bot_self_id, persona_id, owner_id) DO UPDATE SET "
                    "succeeded_at = excluded.succeeded_at, source = excluded.source "
                    "WHERE excluded.succeeded_at > owner_interactions.succeeded_at",
                    (*values, timestamp, source),
                )
        finally:
            connection.close()
