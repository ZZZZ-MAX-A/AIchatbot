from __future__ import annotations

from dataclasses import dataclass
import random
import time

from .sticker_intent import StickerIntent
from .sticker_library import StickerLibrary


@dataclass(frozen=True)
class StickerSelectionPolicy:
    enabled: bool = False
    owner_private_only: bool = True
    cooldown_seconds: int = 120
    min_messages_between: int = 4
    max_per_hour: int = 6
    max_per_reply: int = 1
    min_confidence: float = 0.82

    def validate(self) -> None:
        if type(self.enabled) is not bool or self.owner_private_only is not True:
            raise ValueError("invalid_selection_policy")
        integer_values = (
            self.cooldown_seconds,
            self.min_messages_between,
            self.max_per_hour,
            self.max_per_reply,
        )
        if any(type(value) is not int or value <= 0 for value in integer_values):
            raise ValueError("invalid_selection_policy")
        if self.max_per_reply != 1:
            raise ValueError("invalid_selection_policy")
        if (
            not isinstance(self.min_confidence, (int, float))
            or isinstance(self.min_confidence, bool)
            or not 0.0 <= float(self.min_confidence) <= 1.0
        ):
            raise ValueError("invalid_selection_policy")


@dataclass(frozen=True)
class StickerSelectionContext:
    session_key: str
    is_owner: bool
    is_private: bool
    persona_key: str
    message_index: int
    reply_text: str
    now: float


@dataclass(frozen=True)
class StickerSelectionDecision:
    selected_sticker_id: str | None
    reason: str
    eligible_count: int = 0
    bag_key: tuple[str, str, str, str] | None = None

    @property
    def selected(self) -> bool:
        return self.selected_sticker_id is not None


@dataclass(frozen=True)
class StickerSelectionPreflight:
    allowed: bool
    reason: str


class StickerSelectionRuntime:
    def __init__(self, *, rng: random.Random | None = None) -> None:
        self._rng = rng or random.SystemRandom()
        self._last_sent_at: dict[str, float] = {}
        self._last_sent_message_index: dict[str, int] = {}
        self._sent_times: dict[str, list[float]] = {}
        self._bags: dict[tuple[str, str, str, str], list[str]] = {}

    @staticmethod
    def _base_gate_reason(
        context: StickerSelectionContext,
        policy: StickerSelectionPolicy,
    ) -> str | None:
        try:
            policy.validate()
        except ValueError:
            return "policy_invalid"
        if not policy.enabled:
            return "disabled"
        if not context.session_key or not context.reply_text.strip():
            return "reply_unavailable"
        if policy.owner_private_only and not (context.is_owner and context.is_private):
            return "scope_denied"
        return None

    def _frequency_gate_reason(
        self,
        context: StickerSelectionContext,
        policy: StickerSelectionPolicy,
    ) -> str | None:
        last_sent_at = self._last_sent_at.get(context.session_key)
        if last_sent_at is not None and context.now - last_sent_at < policy.cooldown_seconds:
            return "cooldown"
        last_message_index = self._last_sent_message_index.get(context.session_key)
        if (
            last_message_index is not None
            and context.message_index - last_message_index < policy.min_messages_between
        ):
            return "message_gap"
        cutoff = context.now - 3600.0
        recent = [
            sent_at
            for sent_at in self._sent_times.get(context.session_key, [])
            if sent_at > cutoff
        ]
        self._sent_times[context.session_key] = recent
        if len(recent) >= policy.max_per_hour:
            return "hourly_cap"
        return None

    def preflight(
        self,
        context: StickerSelectionContext,
        policy: StickerSelectionPolicy,
    ) -> StickerSelectionPreflight:
        reason = self._base_gate_reason(context, policy)
        if reason is None:
            reason = self._frequency_gate_reason(context, policy)
        if reason is not None:
            return StickerSelectionPreflight(False, reason)
        return StickerSelectionPreflight(True, "ready")

    def decide(
        self,
        library: StickerLibrary,
        intent: StickerIntent | None,
        context: StickerSelectionContext,
        policy: StickerSelectionPolicy,
    ) -> StickerSelectionDecision:
        base_reason = self._base_gate_reason(context, policy)
        if base_reason is not None:
            return StickerSelectionDecision(None, base_reason)
        if intent is None:
            return StickerSelectionDecision(None, "intent_absent")
        if intent.confidence < policy.min_confidence:
            return StickerSelectionDecision(None, "confidence_low")
        if library.issues:
            return StickerSelectionDecision(None, "library_invalid")

        frequency_reason = self._frequency_gate_reason(context, policy)
        if frequency_reason is not None:
            return StickerSelectionDecision(None, frequency_reason)

        eligible_ids = sorted(
            asset.sticker_id
            for asset in library.assets
            if asset.enabled
            and asset.persona_key == context.persona_key
            and asset.scope == "owner_private"
            and intent.mood in asset.moods
            and asset.intensity == intent.intensity
            and intent.scene in asset.usage_tags
        )
        if not eligible_ids:
            return StickerSelectionDecision(None, "no_match")
        bag_key = (
            context.persona_key,
            intent.mood,
            intent.intensity,
            intent.scene,
        )
        current_bag = [
            sticker_id
            for sticker_id in self._bags.get(bag_key, [])
            if sticker_id in eligible_ids
        ]
        if not current_bag:
            current_bag = list(eligible_ids)
            self._rng.shuffle(current_bag)
        self._bags[bag_key] = current_bag
        return StickerSelectionDecision(
            current_bag[0],
            "selected",
            eligible_count=len(eligible_ids),
            bag_key=bag_key,
        )

    def commit_sent(
        self,
        decision: StickerSelectionDecision,
        context: StickerSelectionContext,
    ) -> None:
        if not decision.selected or decision.bag_key is None:
            raise ValueError("selection_not_committable")
        bag = self._bags.get(decision.bag_key)
        if not bag or bag[0] != decision.selected_sticker_id:
            raise ValueError("selection_bag_changed")
        bag.pop(0)
        self._last_sent_at[context.session_key] = context.now
        self._last_sent_message_index[context.session_key] = context.message_index
        self._sent_times.setdefault(context.session_key, []).append(context.now)


def current_selection_time() -> float:
    return time.monotonic()
