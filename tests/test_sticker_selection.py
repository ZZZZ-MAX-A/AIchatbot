from __future__ import annotations

from pathlib import Path
import random
import unittest

from pure_ai_chat_loader import (
    load_sticker_intent_module,
    load_sticker_library_module,
    load_sticker_selection_module,
)


class StickerSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.library_module = load_sticker_library_module()
        cls.intent_module = load_sticker_intent_module()
        cls.module = load_sticker_selection_module()

    def asset(
        self,
        sticker_id: str,
        *,
        enabled: bool = True,
        moods: tuple[str, ...] = ("playful",),
        intensity: str = "medium",
        usage_tags: tuple[str, ...] = ("acting_cute",),
        persona_key: str = "aike",
        scope: str = "owner_private",
    ):
        return self.library_module.StickerAsset(
            sticker_id=sticker_id,
            file_path=Path(f"C:/approved/{sticker_id}.gif"),
            relative_file=f"{sticker_id}.gif",
            sha256="1" * 64,
            source_sha256="2" * 64,
            media_type="image/gif",
            width=64,
            height=64,
            bytes=100,
            animated=True,
            frame_count=2,
            duration_ms=300,
            persona_key=persona_key,
            moods=moods,
            intensity=intensity,
            actions=("act_cute",),
            usage_tags=usage_tags,
            scope=scope,
            enabled=enabled,
            approved_at="2026-07-13T17:00:00+08:00",
            approval_source="owner_local_command",
        )

    def library(self, assets, *, issues=()):
        return self.library_module.StickerLibrary(2, 1, tuple(assets), tuple(issues))

    def intent(
        self,
        *,
        mood: str = "playful",
        intensity: str = "medium",
        scene: str = "acting_cute",
        confidence: float = 0.91,
    ):
        return self.intent_module.StickerIntent(mood, intensity, scene, confidence)

    def context(
        self,
        *,
        session_key: str = "private:owner",
        is_owner: bool = True,
        is_private: bool = True,
        persona_key: str = "aike",
        message_index: int = 10,
        reply_text: str = "正常且完整的文本回复",
        now: float = 1_000.0,
    ):
        return self.module.StickerSelectionContext(
            session_key,
            is_owner,
            is_private,
            persona_key,
            message_index,
            reply_text,
            now,
        )

    def policy(self, **overrides):
        values = {
            "enabled": True,
            "owner_private_only": True,
            "cooldown_seconds": 120,
            "min_messages_between": 4,
            "max_per_hour": 6,
            "max_per_reply": 1,
            "min_confidence": 0.82,
        }
        values.update(overrides)
        return self.module.StickerSelectionPolicy(**values)

    def test_exact_mood_intensity_scene_and_enabled_asset_are_required(self):
        runtime = self.module.StickerSelectionRuntime(rng=random.Random(1))
        assets = (
            self.asset("match"),
            self.asset("disabled", enabled=False),
            self.asset("wrong_mood", moods=("happy",)),
            self.asset("wrong_intensity", intensity="strong"),
            self.asset("wrong_scene", usage_tags=("teasing",)),
            self.asset("wrong_persona", persona_key="other"),
        )

        decision = runtime.decide(
            self.library(assets),
            self.intent(),
            self.context(),
            self.policy(),
        )

        self.assertTrue(decision.selected)
        self.assertEqual(decision.selected_sticker_id, "match")
        self.assertEqual(decision.eligible_count, 1)

    def test_default_disabled_scope_low_confidence_and_empty_reply_fail_closed(self):
        library = self.library((self.asset("match"),))
        cases = (
            (self.policy(enabled=False), self.intent(), self.context(), "disabled"),
            (self.policy(), None, self.context(), "intent_absent"),
            (self.policy(), self.intent(confidence=0.81), self.context(), "confidence_low"),
            (self.policy(), self.intent(), self.context(is_owner=False), "scope_denied"),
            (self.policy(), self.intent(), self.context(is_private=False), "scope_denied"),
            (self.policy(), self.intent(), self.context(reply_text=""), "reply_unavailable"),
            (self.policy(max_per_reply=2), self.intent(), self.context(), "policy_invalid"),
        )
        for policy, intent, context, expected in cases:
            with self.subTest(expected=expected):
                runtime = self.module.StickerSelectionRuntime(rng=random.Random(2))
                decision = runtime.decide(library, intent, context, policy)
                self.assertFalse(decision.selected)
                self.assertEqual(decision.reason, expected)

    def test_invalid_library_and_no_match_do_not_select(self):
        runtime = self.module.StickerSelectionRuntime(rng=random.Random(3))
        issue = self.library_module.StickerIssue(0, "bad", "sha256_mismatch")
        invalid = runtime.decide(
            self.library((self.asset("match"),), issues=(issue,)),
            self.intent(),
            self.context(),
            self.policy(),
        )
        no_match = runtime.decide(
            self.library((self.asset("happy", moods=("happy",)),)),
            self.intent(),
            self.context(),
            self.policy(),
        )
        self.assertEqual(invalid.reason, "library_invalid")
        self.assertEqual(no_match.reason, "no_match")

    def test_commit_enforces_cooldown_message_gap_and_hourly_cap(self):
        runtime = self.module.StickerSelectionRuntime(rng=random.Random(4))
        library = self.library((self.asset("match"),))
        first_context = self.context(message_index=10, now=1_000.0)
        first = runtime.decide(library, self.intent(), first_context, self.policy(max_per_hour=2))
        runtime.commit_sent(first, first_context)

        cooldown = runtime.decide(
            library,
            self.intent(),
            self.context(message_index=14, now=1_050.0),
            self.policy(max_per_hour=2),
        )
        gap = runtime.decide(
            library,
            self.intent(),
            self.context(message_index=12, now=1_200.0),
            self.policy(max_per_hour=2),
        )
        second_context = self.context(message_index=14, now=1_200.0)
        second = runtime.decide(
            library,
            self.intent(),
            second_context,
            self.policy(max_per_hour=2),
        )
        runtime.commit_sent(second, second_context)
        hourly = runtime.decide(
            library,
            self.intent(),
            self.context(message_index=18, now=1_400.0),
            self.policy(max_per_hour=2),
        )

        self.assertEqual(cooldown.reason, "cooldown")
        self.assertEqual(gap.reason, "message_gap")
        self.assertTrue(second.selected)
        self.assertEqual(hourly.reason, "hourly_cap")

    def test_preflight_blocks_frequency_without_intent_and_recovers(self):
        runtime = self.module.StickerSelectionRuntime(rng=random.Random(5))
        library = self.library((self.asset("match"),))
        policy = self.policy(max_per_hour=2)
        first_context = self.context(message_index=10, now=1_000.0)
        first = runtime.decide(library, self.intent(), first_context, policy)
        runtime.commit_sent(first, first_context)

        cooldown = runtime.preflight(
            self.context(message_index=14, now=1_050.0),
            policy,
        )
        gap = runtime.preflight(
            self.context(message_index=12, now=1_200.0),
            policy,
        )
        ready_context = self.context(message_index=14, now=1_200.0)
        ready_one = runtime.preflight(ready_context, policy)
        ready_two = runtime.preflight(ready_context, policy)
        second = runtime.decide(library, self.intent(), ready_context, policy)

        self.assertFalse(cooldown.allowed)
        self.assertEqual(cooldown.reason, "cooldown")
        self.assertFalse(gap.allowed)
        self.assertEqual(gap.reason, "message_gap")
        self.assertTrue(ready_one.allowed)
        self.assertEqual(ready_one.reason, "ready")
        self.assertEqual(ready_one, ready_two)
        self.assertTrue(second.selected)

    def test_preflight_hourly_cap_expires_without_consuming_state(self):
        runtime = self.module.StickerSelectionRuntime(rng=random.Random(6))
        library = self.library((self.asset("match"),))
        policy = self.policy(max_per_hour=1)
        first_context = self.context(message_index=10, now=1_000.0)
        first = runtime.decide(library, self.intent(), first_context, policy)
        runtime.commit_sent(first, first_context)

        capped = runtime.preflight(
            self.context(message_index=14, now=1_120.0),
            policy,
        )
        expired = runtime.preflight(
            self.context(message_index=14, now=4_601.0),
            policy,
        )

        self.assertFalse(capped.allowed)
        self.assertEqual(capped.reason, "hourly_cap")
        self.assertTrue(expired.allowed)
        self.assertEqual(expired.reason, "ready")

    def test_shuffle_bag_uses_every_match_before_repeating(self):
        runtime = self.module.StickerSelectionRuntime(rng=random.Random(7))
        library = self.library(tuple(self.asset(f"item_{index}") for index in range(3)))
        selected: list[str] = []
        for index in range(3):
            context = self.context(message_index=10 + index * 4, now=1_000.0 + index * 120)
            decision = runtime.decide(library, self.intent(), context, self.policy())
            selected.append(decision.selected_sticker_id)
            runtime.commit_sent(decision, context)

        self.assertEqual(len(set(selected)), 3)
        fourth_context = self.context(message_index=22, now=1_360.0)
        fourth = runtime.decide(library, self.intent(), fourth_context, self.policy())
        self.assertIn(fourth.selected_sticker_id, set(selected))

    def test_decision_does_not_consume_bag_or_frequency_until_send_commit(self):
        runtime = self.module.StickerSelectionRuntime(rng=random.Random(9))
        library = self.library((self.asset("first"), self.asset("second")))
        context = self.context()

        one = runtime.decide(library, self.intent(), context, self.policy())
        two = runtime.decide(library, self.intent(), context, self.policy())

        self.assertEqual(one.selected_sticker_id, two.selected_sticker_id)
        self.assertEqual(two.reason, "selected")
        runtime.commit_sent(two, context)
        blocked = runtime.decide(
            library,
            self.intent(),
            self.context(message_index=14, now=1_010.0),
            self.policy(),
        )
        self.assertEqual(blocked.reason, "cooldown")


if __name__ == "__main__":
    unittest.main()
