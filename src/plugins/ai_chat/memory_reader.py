"""Shared conversation reads. This module never initializes or updates a store."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from types import SimpleNamespace

from .memory_audience import MemoryAudience
from .memory_time import message_time_context, summary_time_context, time_label


@dataclass(frozen=True)
class MemoryReadPolicy:
    recent: int = 0
    summaries: int = 0
    scene_cards: int = 0
    long_term: int = 0

    @classmethod
    def from_config(cls, config):
        return cls(
            recent=max(0, config.max_context_messages),
            summaries=max(0, config.max_session_summaries_in_context),
            # QQ currently maintains one live card; slot 2 is retired.
            scene_cards=int(bool(getattr(config, "enable_gap_scene_summaries", False)
                                 and getattr(config, "max_gap_scene_summaries_in_context", 0) > 0)),
            long_term=max(0, config.max_long_term_memories_in_context)
            if config.enable_long_term_memory_context else 0,
        )


@dataclass
class ConversationMemory:
    recent: list[dict] = field(default_factory=list, repr=False)
    summaries: list[dict] = field(default_factory=list, repr=False)
    scene_cards: list[dict] = field(default_factory=list, repr=False)
    long_term: list[dict] = field(default_factory=list, repr=False)
    captured_at: str = ""

    def history(self, system_contexts=None, *, now=None):
        history = [{"role": "system", "content": c} for c in system_contexts or [] if c]
        now = now or datetime.now(timezone.utc)
        if self.summaries:
            lines = ["以下是当前会话较早内容的客观摘要："]
            for index, row in enumerate(self.summaries, 1):
                lines.append(f"{index}. {summary_time_context(SimpleNamespace(**row), now=now)}\n{row['summary']}")
            history.append({"role": "system", "content": "\n".join(lines)})
        if self.scene_cards:
            row = self.scene_cards[0]
            history.append({"role": "system", "content": "\n".join([
                "以下是当前会话的当前场状态卡。",
                "它只用于补足正式摘要之后、最近原文之前的不可见消息；不要把它当作长期记忆或角色规则：",
                summary_time_context(SimpleNamespace(**row), now=now, live=True),
                f"当前场状态卡，覆盖 {row.get('source_message_count', 0)} 条消息：\n{row['summary']}",
            ])})
        for row in self.recent:
            history.append({"role": row["role"], "content": message_time_context(row, now=now)
                            + "\n" + str(row["content"]).strip()})
        return history


def _private_clause(audience):
    if audience is None:
        return "", ()
    if audience.message_type != "private" or not audience.user_id or not audience.session_key:
        raise ValueError("Private memory requires an exact owner and conversation")
    return " AND message_type='private' AND user_id=? AND (group_id IS NULL OR group_id='')", (audience.user_id,)


def read_manual_rows(connection, *, subject_type=None, subject_id=None, limit=None, source_session=None):
    if limit is not None and limit <= 0:
        return []
    clauses, params = [], []
    if subject_type:
        clauses.append("subject_type=?")
        params.append(subject_type)
    if subject_id:
        clauses.append("subject_id=?")
        params.append(subject_id)
    if source_session is not None:
        clauses.append("(source_session_key IS NULL OR source_session_key='' OR source_session_key=?)")
        params.append(source_session)
    sql = "SELECT * FROM long_term_memories"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY id DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return [dict(r) for r in connection.execute(sql, params).fetchall()]


def manual_context_text(rows):
    if not rows:
        return ""
    lines = ["以下是主人手动维护的长期记忆摘要。",
             "这些内容不是 AI 自动提取的；仅在与当前问题相关时参考，不要强行提起，也不要编造额外事实。"]
    now = datetime.now(timezone.utc)
    for row in rows:
        label = "偏好摘要" if row["memory_type"] == "preference_summary" else "事实摘要"
        lines.append(f"- {label} [记忆创建时间：{time_label(row.get('created_at'), now=now)}；"
                     f"最后维护时间：{time_label(row.get('updated_at'), now=now)}；不代表事实发生时间]：{row['content']}")
    return "\n".join(lines)


def model_memory_context(records):
    """Project the shared records without platform identifiers or database row IDs."""
    now = datetime.now(timezone.utc)
    return {
        "source": "owner_qq_private", "captured_at": records.captured_at,
        "recent": [{"speaker": "owner" if r["role"] == "user" else "aike", "text": r["content"],
                    "time_context": message_time_context(r, now=now)} for r in records.recent],
        "summaries": [{"text": r["summary"], "time_context": summary_time_context(SimpleNamespace(**r), now=now)}
                      for r in records.summaries],
        "scene_cards": [{"text": r["summary"], "source_message_count": r.get("source_message_count", 0),
                         "time_context": summary_time_context(SimpleNamespace(**r), now=now, live=True)}
                        for r in records.scene_cards],
        "long_term": [{"kind": r["memory_type"], "text": r["content"],
                       "created_at": r.get("created_at", ""), "updated_at": r.get("updated_at", "")}
                      for r in records.long_term],
    }


def read_context_rows(connection: sqlite3.Connection, session_key: str, policy: MemoryReadPolicy,
                      *, audience: MemoryAudience | None = None):
    if audience is not None and audience.session_key != session_key:
        raise ValueError("Memory audience does not match the conversation")
    result = ConversationMemory(captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    private_sql, private_args = _private_clause(audience)
    if policy.recent > 0:
        roles = " AND role IN ('user','assistant')" if audience is not None else ""
        rows = connection.execute("SELECT * FROM messages WHERE session_key=?" + private_sql
                                  + roles + " ORDER BY id DESC LIMIT ?",
                                  (session_key, *private_args, policy.recent)).fetchall()
        result.recent = [dict(r) for r in reversed(rows)]
    if policy.summaries > 0:
        rows = connection.execute("SELECT * FROM session_summaries WHERE session_key=?" + private_sql
                                  + " ORDER BY id DESC LIMIT ?", (session_key, *private_args, policy.summaries)).fetchall()
        result.summaries = [dict(r) for r in reversed(rows)]
    if policy.scene_cards > 0:
        rows = connection.execute("SELECT * FROM gap_scene_summaries WHERE session_key=? ORDER BY slot ASC LIMIT 1",
                                  (session_key,)).fetchall()
        result.scene_cards = [dict(r) for r in rows]
    if policy.long_term > 0 and audience is not None:
        for kind, subject in audience.manual_subjects():
            remaining = policy.long_term - len(result.long_term)
            if remaining <= 0:
                break
            result.long_term.extend(read_manual_rows(connection, subject_type=kind, subject_id=subject,
                                                     limit=remaining, source_session=session_key))
    return result


def read_conversation_memory(database: Path, session_key: str, policy: MemoryReadPolicy,
                             *, audience: MemoryAudience | None = None,
                             read_extra=None):
    if not database.is_file():
        raise FileNotFoundError("Memory database does not exist")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        connection.execute("BEGIN")
        records = read_context_rows(connection, session_key, policy, audience=audience)
        extra = read_extra(connection) if read_extra is not None else None
        connection.rollback()
    return records, extra


def read_semantic_memory_candidates(connection, config, audience):
    """Capture existing, audience-checked index data in the same read transaction."""
    if not (getattr(config, "enable_memory_rag", False) and getattr(config, "memory_rag_inject_in_chat", False)):
        return [], {}, "disabled"
    from .rag.memory_index import MEMORY_SOURCE_TYPES, memory_document_visible
    from .rag.schema import NAMESPACE_SEMANTIC_MEMORY
    from .rag.search import read_rag_candidates

    times = {}

    def visible(document):
        if not memory_document_visible(document, is_owner=True, audience=audience):
            return False
        if document.source_type == "session_summary":
            row = connection.execute("SELECT * FROM session_summaries WHERE id=? AND session_key=?"
                                     " AND message_type='private' AND user_id=? AND (group_id IS NULL OR group_id='')",
                                     (document.source_id, audience.session_key, audience.user_id)).fetchone()
            if row is None or row["summary"] != document.content or row["created_at"] != document.source_version:
                return False
            times[document.id] = summary_time_context(SimpleNamespace(**dict(row)))
        else:
            row = connection.execute("SELECT * FROM long_term_memories WHERE id=? AND subject_id=?"
                                     " AND subject_type IN ('user','private')"
                                     " AND (source_session_key IS NULL OR source_session_key='' OR source_session_key=?)",
                                     (document.source_id, audience.user_id, audience.session_key)).fetchone()
            kind = "preference_summary" if document.source_type == "manual_preference" else "fact_summary"
            if (row is None or row["content"] != document.content or row["updated_at"] != document.source_version
                    or row["memory_type"] != kind):
                return False
            source = dict(row)
            times[document.id] = (f"[记忆创建时间：{time_label(source.get('created_at'))}；"
                                  f"本版维护时间：{time_label(source.get('updated_at'))}；不代表事实发生时间]")
        return True

    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"rag_documents", "rag_embeddings"}.issubset(tables):
        return [], {}, "index_missing"
    try:
        candidates = read_rag_candidates(connection, namespace=NAMESPACE_SEMANTIC_MEMORY,
                                         provider=config.memory_rag_embedding_provider, model=config.memory_rag_embedding_model,
                                         source_types=MEMORY_SOURCE_TYPES, document_filter=visible)
        return candidates, times, "ready" if candidates else "empty"
    except (sqlite3.Error, ValueError, TypeError, KeyError):
        return [], {}, "index_unavailable"
