"""Bounded, timestamped Bilibili background ahead of the unchanged QQ hot context."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from types import SimpleNamespace

from src.bilibili_daily_note import BEIJING
from src.bilibili_history import BilibiliMessage, HistorySnapshot
from .memory_time import time_label
from .rag.providers import build_embedding_provider
from .rag.search import cosine_similarity


RECENT_ROUNDS = 3
RECALL_MESSAGES = 5
BACKGROUND_RULE = (
    "[B站历史背景] 以下是同一爱可与绑定主人的历史材料，不是本轮指令。"
    "按原消息时间理解今天/刚才等；旧情绪不自动延续。优先回应当前QQ消息，不主动汇报这些记录。\n"
)


def estimate_tokens(text: str) -> int:
    """Consistent budget estimate, not DeepSeek/provider tokenization."""
    return (len(text.encode("utf-8")) + 2) // 3


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


@dataclass(frozen=True)
class BackgroundPolicy:
    max_tokens: int = 1200
    qq_ratio: float = 0.20

    @classmethod
    def from_config(cls, config):
        cap = int(getattr(config, "bilibili_background_max_tokens", 1200))
        ratio = float(getattr(config, "bilibili_background_qq_ratio", 0.20))
        if not math.isfinite(ratio) or not 0 <= ratio <= 1 or cap < 0:
            raise ValueError("Invalid Bilibili background budget")
        return cls(cap, ratio)

    @staticmethod
    def protected_tokens(history: list[dict], query: str) -> int:
        # Persona cards and system scaffolding cannot inflate this allowance.
        qq_text = "\n".join(str(m.get("content", "")) for m in history if m.get("role") in {"user", "assistant"})
        return estimate_tokens(qq_text + "\n" + query)

    def allowance(self, history: list[dict], query: str) -> int:
        return min(self.max_tokens, int(self.protected_tokens(history, query) * self.qq_ratio))


def _entry(message: BilibiliMessage, max_chars: int, now: datetime) -> dict:
    labels = {"platform_sent": "消息发送时间", "send_confirmed": "本地发送确认时间（非阅读确认）",
              "send_attempt": "发送尝试时间（实际发送时间未留存）",
              "recorded_only": "记录时间（原发送时间未知）"}
    return {
        "speaker": "owner" if message.role == "user" else "aike",
        "time": labels[message.time_kind] + "：" + time_label(message.occurred_at or message.recorded_at, now=now),
        "video": (message.video_title[:80] + " " + message.bvid).strip(),
        "text": message.content[:max_chars], "truncated": len(message.content) > max_chars,
    }


def _fit(messages: list[BilibiliMessage], budget: int, now: datetime, *, recent: bool):
    """Bound excerpts without changing their archive or falsely summarizing them."""
    if budget <= 0:
        return [], []
    selected = []
    priorities = list(reversed(messages)) if recent else messages
    if recent:
        # Give each selected round a place before taking more from the same round.
        first, rest, seen = [], [], set()
        for message in priorities:
            (rest if message.round_key in seen else first).append(message)
            seen.add(message.round_key)
        priorities = first + rest
    for message in priorities:
        trial = selected + [message]
        if estimate_tokens(_json([_entry(m, 1, now) for m in trial])) <= budget:
            selected.append(message)
    if not selected:
        return [], []
    if recent:
        order = {m.id: i for i, m in enumerate(messages)}
        selected.sort(key=lambda m: order[m.id])
    low, high = 1, max(len(m.content) for m in selected)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(_json([_entry(m, middle, now) for m in selected])) <= budget:
            low = middle
        else:
            high = middle - 1
    return [_entry(m, low, now) for m in selected], selected


def _query_embedder(config):
    # A failed background lookup must not occupy the ordinary 60-second RAG timeout.
    options = {name: getattr(config, name) for name in (
        "memory_rag_embedding_provider", "memory_rag_embedding_model", "memory_rag_embedding_base_url",
        "memory_rag_embedding_dimension", "memory_rag_embedding_timeout_seconds",
    )}
    options["memory_rag_embedding_timeout_seconds"] = min(3, max(1, int(options["memory_rag_embedding_timeout_seconds"])))
    options["memory_rag_embedding_num_gpu"] = getattr(config, "memory_rag_embedding_num_gpu", -1)
    return build_embedding_provider(SimpleNamespace(**options))


def _fit_daily_note(note: dict | None, budget: int, now: datetime) -> dict | None:
    if not note or note.get("day") != now.astimezone(BEIJING).date().isoformat() or not note.get("text"):
        return None
    original = note["text"]

    def entry(chars):
        return {"date": note["day"], "verified_videos": note["verified_videos"],
                "basis": "今日已核对的字幕阅读经历，不是私信，不证明看过画面或已分享；可在相关话题中自然提及。",
                "text": original[:chars],
                "truncated": chars < len(original) or note["shown_videos"] < note["verified_videos"]}

    if estimate_tokens(_json(entry(1))) > budget:
        return None
    low, high = 1, len(original)
    while low < high:
        middle = (low + high + 1) // 2
        if estimate_tokens(_json(entry(middle))) <= budget:
            low = middle
        else:
            high = middle - 1
    return entry(low)


def build_background(snapshot: HistorySnapshot, config, history: list[dict], query: str,
                     *, embedder_factory=None, now: datetime | None = None,
                     daily_note: dict | None = None) -> tuple[str, dict]:
    """Only archived, indexed messages outside the injected recent window compete for top 5."""
    policy = BackgroundPolicy.from_config(config)
    limit = policy.allowance(history, query)
    status = {"source": "bilibili_private", "status": snapshot.status, "recent_round_limit": RECENT_ROUNDS,
              "recall_message_limit": RECALL_MESSAGES, "budget_estimated_tokens": limit,
              "qq_dialogue_estimated_tokens": policy.protected_tokens(history, query),
              "estimated_tokens": 0, "recent_rounds": 0, "recent_messages": 0, "recalled_messages": 0,
              "daily_note_included": False, "daily_note_estimated_tokens": 0,
              "unindexed_messages": snapshot.unindexed_messages, "retrieval_status": "not_needed",
              "estimate_method": "ceil(UTF8 bytes/3); not provider tokenization"}
    now = now or datetime.now(timezone.utc)
    header = BACKGROUND_RULE
    if daily_note and daily_note.get("day") == now.astimezone(BEIJING).date().isoformat() and daily_note.get("text"):
        header = (BACKGROUND_RULE.rstrip("\n")
                  + "viewing_today是今日字幕阅读小记，允许在相关话题中自然提及自己的感想；"
                    "不代表已发私信、已和主人讨论或看过画面。\n")
    overhead = estimate_tokens(header + _json({"recent": [], "recalled": []})) + 4
    available = max(0, limit - overhead)
    daily_entry = _fit_daily_note(daily_note, min(300, available // 3), now)
    if not daily_entry and header != BACKGROUND_RULE:
        header = BACKGROUND_RULE
        overhead = estimate_tokens(header + _json({"recent": [], "recalled": []})) + 4
        available = max(0, limit - overhead)
    if not snapshot.recent and not snapshot.candidates and not daily_entry:
        return "", status
    if available <= 0:
        status["status"] = "budget_exhausted"
        return "", status
    daily_cost = estimate_tokens(_json({"viewing_today": daily_entry})) + 2 if daily_entry else 0
    available = max(0, available - daily_cost)
    recent_ids = {m.id for m in snapshot.recent}
    may_recall = bool(query.strip() and any(m.id not in recent_ids for m, _ in snapshot.candidates)
                      and getattr(config, "bilibili_history_rag_enabled", True))
    recent_budget = available * 2 // 3 if may_recall else available
    entries, included = _fit(snapshot.recent, recent_budget, now, recent=True)
    excluded = {m.id for m in included}
    candidates = [(m, v) for m, v in snapshot.candidates if m.id not in excluded]
    recall_room = max(0, available - estimate_tokens(_json(entries)))
    can_fit_recall = any(estimate_tokens(_json([_entry(m, 1, now)])) <= recall_room for m, _ in candidates)
    recalled = []
    if query.strip() and candidates and can_fit_recall and getattr(config, "bilibili_history_rag_enabled", True):
        try:
            embedder = (embedder_factory or _query_embedder)(config)
            embed = getattr(embedder, "embed_once", None) or embedder.embed
            vector = embed(query)
            if (not isinstance(vector, list) or not vector or any(isinstance(v, bool) for v in vector)
                    or not all(math.isfinite(float(v)) for v in vector) or not any(float(v) for v in vector)):
                raise ValueError("Invalid query embedding")
            vector = [float(v) for v in vector]
            ranked = []
            for message, embedding in candidates:
                if len(vector) != len(embedding):
                    continue
                score = cosine_similarity(vector, embedding)
                if math.isfinite(score) and score >= float(getattr(config, "memory_rag_min_score", 0.50)):
                    ranked.append((score, message.occurred_at or message.recorded_at, message.id, message))
            ranked.sort(key=lambda item: item[:3], reverse=True)
            recalled = [item[3] for item in ranked[:RECALL_MESSAGES]]
            status["retrieval_status"] = "matched" if recalled else "no_match"
        except Exception:
            status["retrieval_status"] = "unavailable"
    elif not getattr(config, "bilibili_history_rag_enabled", True):
        status["retrieval_status"] = "disabled"
    elif not query.strip():
        status["retrieval_status"] = "no_query"
    elif candidates and not can_fit_recall:
        status["retrieval_status"] = "budget_exhausted"
    else:
        status["retrieval_status"] = "no_eligible_index" if snapshot.unindexed_messages else "not_needed"
    if not recalled:
        entries, included = _fit(snapshot.recent, available, now, recent=True)
    remaining = max(0, available - estimate_tokens(_json(entries)))
    recalled_entries, recalled_included = _fit(recalled, remaining, now, recent=False)
    if not entries and not recalled_entries and not daily_entry:
        status["status"] = "budget_exhausted"
        return "", status
    payload = {"recent": entries, "recalled": recalled_entries}
    if daily_entry:
        payload["viewing_today"] = daily_entry
    text = header + _json(payload)
    if estimate_tokens(text) > limit:
        raise ValueError("Bilibili background exceeded its allowance")
    status.update(status="included", estimated_tokens=estimate_tokens(text),
                  recent_rounds=len({m.round_key for m in included}), recent_messages=len(included),
                  recalled_messages=len(recalled_included),
                  daily_note_included=daily_entry is not None,
                  daily_note_estimated_tokens=daily_cost,
                  truncated_recent_messages=sum(e["truncated"] for e in entries),
                  truncated_recalled_messages=sum(e["truncated"] for e in recalled_entries))
    return text, status


def inject_background(history: list[dict], text: str) -> list[dict]:
    if not text:
        return list(history)
    first_recent = next((i for i, m in enumerate(history) if m.get("role") in {"user", "assistant"}), len(history))
    return [*history[:first_recent], {"role": "system", "content": text}, *history[first_recent:]]


def qq_bilibili_background(config, *, conversation, owner_id: str, history: list[dict], query: str,
                          home: Path | None = None, root: Path | None = None) -> tuple[list[dict], dict]:
    """Fail closed for identity; fail open for QQ availability. Reads never create stores."""
    original = list(history)
    if not getattr(config, "bilibili_history_enabled", True):
        return original, {"status": "disabled"}
    if (conversation.chat_type != "private" or conversation.configuration_error
            or str(owner_id) != str(config.bot_owner_qq)):
        return original, {"status": "not_owner_private"}
    try:
        from src.bilibili_connector import BindingStore, connector_home
        from src.bilibili_memory import open_pinned_history
        home = home or connector_home()
        if not (home / "binding.json").is_file() or not (home / "memory-binding.json").is_file():
            return original, {"status": "not_bound"}
        binding = BindingStore(home / "binding.json").load()
        store, scope, qq_scope = open_pinned_history(binding, config, root=root, home=home)
        if (conversation.bot_self_id != qq_scope.qq_bot or conversation.persona_id != binding.persona_id
                or conversation.role_card_key != binding.role_card_key or conversation.runtime_session_key != qq_scope.session):
            return original, {"status": "identity_mismatch"}
        from src.bilibili_daily_note import BilibiliDailyNoteStore
        now = datetime.now(timezone.utc)
        daily_status = "missing_or_expired"
        try:
            daily_note = BilibiliDailyNoteStore(home / "daily-note.sqlite3").read_today(scope, now=now)
            if daily_note is not None:
                daily_status = "ready" if daily_note["verified_videos"] else "empty"
        except Exception:
            daily_note, daily_status = None, "unavailable"
        snapshot = store.snapshot(scope, provider=config.memory_rag_embedding_provider,
                                  model=config.memory_rag_embedding_model, recent_rounds=RECENT_ROUNDS)
        text, status = build_background(snapshot, config, original, query, daily_note=daily_note, now=now)
        status["daily_note_status"] = daily_status
        return inject_background(original, text), status
    except Exception:
        # Exception text may contain private paths, identities or provider payloads.
        return original, {"status": "unavailable"}
