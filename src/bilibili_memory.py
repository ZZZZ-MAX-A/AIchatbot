"""Owner-private QQ continuity for Bilibili, read-only and explicitly scoped."""
from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import json
from pathlib import Path
import re
import sqlite3

from .bilibili_connector import BilibiliBinding, BilibiliConnectorError, _atomic_write, connector_home


@dataclass(frozen=True)
class MemoryScope:
    qq_owner: str = field(repr=False)
    qq_bot: str = field(repr=False)
    session: str = field(repr=False)
    database: Path = field(repr=False)
    mode: str


def resolve_memory_scope(binding: BilibiliBinding, config, root: Path) -> MemoryScope:
    binding.validate()
    routing = config.persona_routing
    if (binding.persona_id != routing.legacy_persona_id or
            binding.role_card_key != routing.legacy_role_card_key):
        raise BilibiliConnectorError("B 站角色与 QQ 爱可固定映射不一致")
    owner = str(config.bot_owner_qq).strip()
    if not re.fullmatch(r"[1-9][0-9]{4,19}", owner):
        raise BilibiliConnectorError("未配置有效的 QQ 主人身份，停止记忆读取")
    matches = [b for b in routing.bindings if b.persona_id == binding.persona_id and b.role_card_key == binding.role_card_key]
    if len(matches) != 1:
        raise BilibiliConnectorError("QQ 爱可账号映射缺失或不唯一，停止记忆读取")
    scopes = importlib.import_module("src.plugins.ai_chat.persona_scope")
    scope = scopes.resolve_conversation_scope(
        routing, bot_self_id=matches[0].bot_self_id, user_id=owner,
        chat_type="private", legacy_session_key=f"private:{owner}",
        available_role_card_keys=frozenset({binding.role_card_key}),
    )
    if scope.configuration_error or (scope.routing_v2_active and not scope.memory_v2_active):
        raise BilibiliConnectorError("QQ 人格存储范围无效或仅有临时记忆，停止跨平台读取")
    database = (root / "data/persona-memory" / f"{scope.persona_id}.db"
                if scope.memory_v2_active else root / "data/chatbot.db")
    return MemoryScope(owner, matches[0].bot_self_id, scope.runtime_session_key, database, scope.runtime_mode)


def mapping_data(binding: BilibiliBinding, scope: MemoryScope) -> dict:
    return {"version": 1, "persona_id": binding.persona_id, "role_card_key": binding.role_card_key,
                "bilibili_aike_uid": binding.aike_mid, "bilibili_owner_uid": binding.owner_mid,
                "qq_aike_uid": scope.qq_bot, "qq_owner_uid": scope.qq_owner,
                "qq_session": scope.session, "storage_mode": scope.mode}


def pin_mapping(binding: BilibiliBinding, scope: MemoryScope, path: Path) -> None:
    """Pin the already configured owner pair, never infer identity from names."""
    expected = mapping_data(binding, scope)
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _atomic_write(path, json.dumps(expected, ensure_ascii=False, indent=2) + "\n")
        return
    except (OSError, ValueError, UnicodeError) as exc:
        raise BilibiliConnectorError("跨平台记忆身份文件不可读取") from exc
    if previous != expected:
        raise BilibiliConnectorError("跨平台主人或人格映射已变化，停止记忆读取；请核对本机 memory-binding.json 与账号配置")


def open_pinned_history(binding: BilibiliBinding, config, *, root: Path | None = None, home: Path | None = None):
    """Verify an existing mapping without creating one or opening QQ storage."""
    from .bilibili_history import BilibiliHistoryStore, HistoryScope
    root = root or Path(__file__).resolve().parents[1]
    home = home or connector_home()
    scope = resolve_memory_scope(binding, config, root)
    expected = mapping_data(binding, scope)
    previous = json.loads((home / "memory-binding.json").read_text(encoding="utf-8"))
    if previous != expected:
        raise BilibiliConnectorError("B 站经历的主人或人格映射不匹配")
    return BilibiliHistoryStore(home / "history.db"), HistoryScope.from_mapping(expected), scope


@dataclass
class MemorySnapshot:
    records: object = field(repr=False)
    policy: object = field(repr=False)
    config: object = field(repr=False)
    audience: object = field(repr=False)
    storage_mode: str = ""
    semantic_candidates: list = field(default_factory=list, repr=False)
    semantic_times: dict = field(default_factory=dict, repr=False)
    semantic_status: str = "disabled"

    @property
    def recent(self):
        return self.records.recent

    @property
    def summaries(self):
        return self.records.summaries

    @property
    def scene_cards(self):
        return self.records.scene_cards

    @property
    def long_term(self):
        return self.records.long_term

    def public_status(self) -> dict:
        return {"enabled": True, "status": "loaded" if any((self.recent, self.summaries, self.scene_cards,
                                                            self.long_term, self.semantic_candidates)) else "empty",
                "strategy": "shared_qq_memory_reader", "storage_mode": self.storage_mode,
                "captured_at": self.records.captured_at,
                "available_counts": {"recent": len(self.recent), "summaries": len(self.summaries),
                                     "scene_cards": len(self.scene_cards), "long_term": len(self.long_term)},
                "configured_limits": dict(vars(self.policy)), "max_context_characters": None,
                "semantic_retrieval": {"status": self.semantic_status,
                                       "indexed_candidates": len(self.semantic_candidates)}, "read_only": True}

    def context(self, task_data: dict) -> tuple[dict, dict]:
        reader = importlib.import_module("src.plugins.ai_chat.memory_reader")
        result = reader.model_memory_context(self.records)
        status = self.semantic_status
        semantic = []
        videos = task_data.get("candidates") or [task_data.get("video", {})]
        query = (str(task_data["query"])[:12000] if task_data.get("query") else
                 " ".join(str(v.get(k, ""))[:600] for v in videos for k in ("title", "category", "description"))[:12000])
        if status == "ready" and query.strip():
            try:
                providers = importlib.import_module("src.plugins.ai_chat.rag.providers")
                index = importlib.import_module("src.plugins.ai_chat.rag.memory_index")
                hits = index.retrieve_memory(query=query, embedder=providers.build_embedding_provider(self.config),
                                             is_owner=True, audience=self.audience,
                                             top_k=self.config.memory_rag_top_k, min_score=self.config.memory_rag_min_score,
                                             max_context_chars=self.config.memory_rag_max_context_chars,
                                             candidates=self.semantic_candidates)
                semantic = [{"source_type": h.document.source_type, "text": h.document.content,
                             "time_context": self.semantic_times[h.document.id], "score": h.score} for h in hits]
                status = "matched" if semantic else "no_match"
            except Exception:
                # Provider errors may contain private payloads or local addresses.
                status = "retrieval_unavailable"
        elif status == "ready":
            status = "no_query"
        result["semantic_memory"] = semantic
        result["semantic_retrieval_status"] = status
        counts = {key: len(result[key]) for key in ("recent", "summaries", "scene_cards", "long_term", "semantic_memory")}
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        measured = {"characters": len(encoded), "utf8_bytes": len(encoded.encode("utf-8")),
                    "included_counts": counts, "semantic_retrieval_status": status,
                    "token_estimate": (len(encoded.encode("utf-8")) + 2) // 3,
                    "token_estimate_method": "ceil(UTF8 bytes/3); rough estimate, not provider tokenization"}
        return result, measured


def read_snapshot(scope: MemoryScope, config) -> MemorySnapshot:
    reader = importlib.import_module("src.plugins.ai_chat.memory_reader")
    audiences = importlib.import_module("src.plugins.ai_chat.memory_audience")
    policy = reader.MemoryReadPolicy.from_config(config)
    audience = audiences.MemoryAudience("private", scope.qq_owner, session_key=scope.session)
    try:
        records, semantic = reader.read_conversation_memory(
            scope.database, scope.session, policy, audience=audience,
            read_extra=lambda c: reader.read_semantic_memory_candidates(c, config, audience),
        )
    except (sqlite3.Error, OSError, ValueError) as exc:
        raise BilibiliConnectorError("QQ 记忆只读查询失败，未迁移数据库或借用其他会话") from exc
    candidates, times, status = semantic
    return MemorySnapshot(records=records, policy=policy, config=config, audience=audience,
                          storage_mode=scope.mode, semantic_candidates=candidates, semantic_times=times, semantic_status=status)


def load_owner_memory(binding: BilibiliBinding, config, *, root: Path | None = None,
                      mapping_path: Path | None = None) -> MemorySnapshot:
    root = root or Path(__file__).resolve().parents[1]
    scope = resolve_memory_scope(binding, config, root)
    mapping_path = mapping_path or connector_home() / "memory-binding.json"
    if mapping_path.exists():
        pin_mapping(binding, scope, mapping_path)
    snapshot = read_snapshot(scope, config)
    pin_mapping(binding, scope, mapping_path)
    return snapshot
