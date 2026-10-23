"""Fixed-account maintenance targets and strictly read-only aggregate counts."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import sqlite3

from . import database
from .persona_memory_scope import persona_database_path
from .persona_scope import resolve_conversation_scope
from .role_cards import role_card_by_key
from .rag.schema import NAMESPACE_SEMANTIC_MEMORY


class MemoryMaintenanceError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code, self.message, self.status_code = code, message, status_code


@dataclass(frozen=True)
class MemoryMaintenanceScope:
    bot_self_id: str
    persona_id: str
    persona_name: str
    role_card_key: str
    storage: str
    database: str
    session_namespace: str
    revision: str

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def path(self) -> Path:
        return (persona_database_path(self.persona_id) if self.storage == "persona_database"
                else database.DATABASE_PATH)


def resolve_memory_maintenance_scope(config, bot_self_id: str | None = None,
                                     revision: str | None = None) -> MemoryMaintenanceScope:
    settings = config.persona_routing
    if bot_self_id is None:
        candidates = [b for b in settings.bindings if b.persona_id == settings.legacy_persona_id
                      and b.role_card_key == settings.legacy_role_card_key]
        if len(candidates) != 1:
            raise MemoryMaintenanceError("default_scope_unavailable", "默认记忆账号绑定不唯一或未配置")
        bot_self_id = candidates[0].bot_self_id
    binding = next((b for b in settings.bindings if b.bot_self_id == bot_self_id), None)
    if binding is None:
        raise MemoryMaintenanceError("unknown_memory_account", "记忆维护账号没有固定绑定", 404)
    available = frozenset({binding.role_card_key}) if role_card_by_key(binding.role_card_key) else frozenset()
    scope = resolve_conversation_scope(settings, bot_self_id=binding.bot_self_id,
        user_id="", chat_type="private", legacy_session_key="private:", available_role_card_keys=available)
    if scope.configuration_error:
        raise MemoryMaintenanceError("invalid_memory_binding", "当前账号的人格或角色卡绑定异常")
    if scope.routing_v2_active and not scope.memory_v2_active:
        raise MemoryMaintenanceError("persistent_memory_unavailable", "当前人格尚未启用持久记忆库")
    storage = "persona_database" if scope.memory_v2_active else "legacy_database"
    path = persona_database_path(scope.persona_id) if scope.memory_v2_active else database.DATABASE_PATH
    fingerprint = {
        "account": binding.bot_self_id, "persona": scope.persona_id, "card": scope.role_card_key,
        "mode": scope.runtime_mode, "path": str(path.resolve()),
        "embedding_provider": config.memory_rag_embedding_provider,
        "embedding_model": config.memory_rag_embedding_model,
        "embedding_base_url": config.memory_rag_embedding_base_url,
        "rag_enabled": config.enable_memory_rag,
        "facts": config.memory_rag_include_manual_facts,
        "preferences": config.memory_rag_include_manual_preferences,
        "summaries": config.memory_rag_include_session_summaries,
    }
    current_revision = hashlib.sha256(json.dumps(fingerprint, sort_keys=True).encode()).hexdigest()
    if revision is not None and revision != current_revision:
        raise MemoryMaintenanceError("stale_memory_scope", "记忆维护绑定或索引配置已变化，请刷新后重新确认")
    return MemoryMaintenanceScope(binding.bot_self_id, scope.persona_id,
        {"aike": "爱可", "linyin": "凛音"}.get(scope.persona_id, scope.persona_id), scope.role_card_key,
        storage, f"data/persona-memory/{scope.persona_id}.db" if scope.memory_v2_active else "data/chatbot.db",
        f"persona:{scope.persona_id}:" if scope.routing_v2_active else "private:/group:", current_revision)


@contextmanager
def memory_maintenance_database_scope(config, target: MemoryMaintenanceScope):
    # Re-resolve from the fixed account; never trust a caller-supplied DB path or persona.
    current = resolve_memory_maintenance_scope(config, target.bot_self_id, target.revision)
    if current != target:
        raise MemoryMaintenanceError("stale_memory_scope", "记忆维护范围已变化，请刷新后重新确认")
    path = current.path
    # Refuse links/junctions so a persona DB cannot redirect maintenance to another library.
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise MemoryMaintenanceError("memory_path_unavailable", "记忆库路径不可用于维护")
        if part == database.PROJECT_ROOT:
            break
    if not path.is_file():
        raise MemoryMaintenanceError("memory_database_missing", "当前人格的记忆库尚未创建")
    with database.database_path_scope(path):
        yield current


def read_memory_maintenance_counts() -> dict[str, dict[str, int]]:
    """One read-only connection, fixed aggregate SQL; no initialization or content."""
    try:
        with database.connect_read_only() as con:
            memory = dict(con.execute("SELECT COUNT(*) AS message_count, COUNT(DISTINCT session_key) AS session_count FROM messages").fetchone())
            memory.update(dict(con.execute("SELECT COUNT(*) AS summary_count, COALESCE(SUM(source_message_count),0) AS summarized_message_count FROM session_summaries").fetchone()))
            manual = dict(con.execute("SELECT COUNT(*) AS memory_count, COUNT(DISTINCT subject_type || ':' || subject_id) AS subject_count FROM long_term_memories").fetchone())
            gap = dict(con.execute("SELECT COUNT(*) AS summary_count, COALESCE(SUM(source_message_count),0) AS source_message_count FROM gap_scene_summaries").fetchone())
            rag = dict(con.execute("SELECT COUNT(*) AS document_count, COALESCE(SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END),0) AS active_document_count FROM rag_documents WHERE namespace = ?", (NAMESPACE_SEMANTIC_MEMORY,)).fetchone())
            rag["embedding_count"] = con.execute("SELECT COUNT(*) FROM rag_embeddings e JOIN rag_documents d ON d.id = e.document_id WHERE d.namespace = ?", (NAMESPACE_SEMANTIC_MEMORY,)).fetchone()[0]
        return {"memory_stats": memory, "manual_memory_stats": manual,
                "gap_scene_stats": gap, "rag_document_stats": rag}
    except (sqlite3.Error, OSError):
        raise MemoryMaintenanceError("memory_schema_unavailable", "记忆库不存在、不可读或结构不完整；本次未建库或迁移") from None
