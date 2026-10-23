from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


SESSION_KEY = "private:10001"


class GapSceneLiveCardTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.module = load_module(
            "src.plugins.ai_chat.gap_scene_summaries",
            AI_CHAT_ROOT / "gap_scene_summaries.py",
        )

    @staticmethod
    def config(**overrides):
        values = {
            "enable_gap_scene_summaries": True,
            "max_context_messages": 40,
            "bot_owner_qq": "10001",
            "gap_scene_summary_1_threshold": 40,
            "gap_scene_summary_2_threshold": 80,
            "max_stored_messages_per_session": 120,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    @staticmethod
    def make_rows(count: int, start_id: int = 1):
        rows = []
        for index in range(count):
            message_id = start_id + index
            rows.append(
                {
                    "id": message_id,
                    "role": "user" if index % 2 == 0 else "assistant",
                    "user_id": "10001" if index % 2 == 0 else None,
                    "content": f"m{message_id}",
                }
            )
        return rows

    def make_card(
        self,
        *,
        end_id: int,
        count: int,
        start_id: int = 1,
        summary: str = "旧卡：室内闲聊。",
    ):
        return self.module.GapSceneSummary(
            id=1,
            session_key=SESSION_KEY,
            slot=1,
            summary=summary,
            message_start_id=start_id,
            message_end_id=end_id,
            source_message_count=count,
            created_at="t",
            updated_at="t",
        )

    async def run_ensure(
        self,
        *,
        rows,
        existing=None,
        summary_text="场景位置：室内\n未决：继续当前场。",
    ):
        store = {"existing": existing, "upserts": [], "deleted": [], "cleared": False}
        generate = AsyncMock(return_value=summary_text)

        def get_card(session_key, slot):
            return store["existing"]

        def upsert(**kwargs):
            store["upserts"].append(kwargs)
            store["existing"] = self.make_card(
                start_id=kwargs["message_start_id"],
                end_id=kwargs["message_end_id"],
                count=kwargs["source_message_count"],
                summary=kwargs["summary"],
            )
            return 1

        def delete_slots(session_key, slots):
            store["deleted"].append(list(slots))
            if self.module.GAP_SCENE_SLOT in slots:
                store["existing"] = None
            return len(slots)

        def clear(session_key):
            store["cleared"] = True
            store["existing"] = None
            return 1

        with (
            patch.object(self.module, "_message_count", return_value=len(rows)),
            patch.object(
                self.module,
                "_message_window",
                side_effect=lambda session_key, offset, limit: rows[offset : offset + limit],
            ),
            patch.object(self.module, "get_gap_scene_summary", side_effect=get_card),
            patch.object(self.module, "upsert_gap_scene_summary", side_effect=upsert),
            patch.object(self.module, "delete_gap_scene_slots", side_effect=delete_slots),
            patch.object(self.module, "clear_gap_scene_summaries", side_effect=clear),
            patch.object(self.module, "_generate_gap_scene_summary", new=generate),
        ):
            await self.module.ensure_gap_scene_summaries(self.config(), SESSION_KEY)
        return store, generate

    def test_take_count_contract(self):
        self.assertEqual(self.module.next_gap_scene_take_count(False, 24), 0)
        self.assertEqual(self.module.next_gap_scene_take_count(False, 25), 25)
        self.assertEqual(self.module.next_gap_scene_take_count(True, 19), 0)
        self.assertEqual(self.module.next_gap_scene_take_count(True, 20), 20)

    async def test_under_65_does_not_write(self):
        store, generate = await self.run_ensure(rows=self.make_rows(64))
        generate.assert_not_awaited()
        self.assertEqual(store["upserts"], [])

    async def test_65_writes_first_card_of_25(self):
        store, generate = await self.run_ensure(rows=self.make_rows(65))
        generate.assert_awaited_once()
        payload = generate.await_args.args[1]
        self.assertIn("【新露出的原文】", payload)
        self.assertIn("m1", payload)
        self.assertIn("m25", payload)
        self.assertNotIn("m26", payload)
        self.assertNotIn("【当前状态卡】", payload)
        self.assertEqual(len(store["upserts"]), 1)
        upsert = store["upserts"][0]
        self.assertEqual(upsert["slot"], 1)
        self.assertEqual(upsert["message_start_id"], 1)
        self.assertEqual(upsert["message_end_id"], 25)
        self.assertEqual(upsert["source_message_count"], 25)

    async def test_84_does_not_update_existing_card(self):
        existing = self.make_card(end_id=25, count=25)
        store, generate = await self.run_ensure(rows=self.make_rows(84), existing=existing)
        generate.assert_not_awaited()
        self.assertEqual(store["upserts"], [])

    async def test_85_merges_next_20_into_same_card(self):
        existing = self.make_card(end_id=25, count=25, summary="旧卡：还在室内。")
        store, generate = await self.run_ensure(rows=self.make_rows(85), existing=existing)
        generate.assert_awaited_once()
        payload = generate.await_args.args[1]
        self.assertIn("【当前状态卡】", payload)
        self.assertIn("旧卡：还在室内。", payload)
        self.assertIn("【新露出的原文】", payload)
        self.assertIn("m26", payload)
        self.assertIn("m45", payload)
        self.assertNotIn("m46", payload)
        upsert = store["upserts"][0]
        self.assertEqual(upsert["message_start_id"], 1)
        self.assertEqual(upsert["message_end_id"], 45)
        self.assertEqual(upsert["source_message_count"], 45)

    async def test_catch_up_from_empty_writes_first_then_merge(self):
        store, generate = await self.run_ensure(rows=self.make_rows(85))
        self.assertEqual(generate.await_count, 2)
        self.assertEqual(len(store["upserts"]), 2)
        self.assertEqual(store["upserts"][0]["source_message_count"], 25)
        self.assertEqual(store["upserts"][0]["message_end_id"], 25)
        self.assertEqual(store["upserts"][1]["source_message_count"], 45)
        self.assertEqual(store["upserts"][1]["message_end_id"], 45)

    async def test_refusal_does_not_upsert(self):
        existing = self.make_card(end_id=25, count=25)
        store, generate = await self.run_ensure(
            rows=self.make_rows(85),
            existing=existing,
            summary_text="",
        )
        generate.assert_awaited_once()
        self.assertEqual(store["upserts"], [])
        self.assertIsNotNone(store["existing"])
        self.assertEqual(store["existing"].message_end_id, 25)

    async def test_orphan_card_is_dropped_before_rewrite(self):
        existing = self.make_card(start_id=900, end_id=920, count=21)
        store, generate = await self.run_ensure(rows=self.make_rows(64), existing=existing)
        generate.assert_not_awaited()
        self.assertEqual(store["upserts"], [])
        self.assertIn([1], store["deleted"])

    def test_format_shows_single_live_card(self):
        card = self.make_card(end_id=25, count=25, summary="当前在厨房做早餐。")
        with patch.object(self.module, "list_gap_scene_summaries", return_value=[card]):
            text = self.module.format_gap_scene_context(SESSION_KEY, 2)
        self.assertIn("当前场状态卡", text)
        self.assertIn("当前在厨房做早餐。", text)
        self.assertNotIn("空窗摘要 1", text)
        self.assertNotIn("空窗摘要 2", text)


if __name__ == "__main__":
    unittest.main()