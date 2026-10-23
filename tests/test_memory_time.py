from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from pure_ai_chat_loader import (
    AI_CHAT_ROOT, ensure_ai_chat_packages, load_legacy_memory_modules,
    load_module, load_rag_modules,
)
from test_chat_time_reunion_runtime import plugin_functions


NOW = datetime.fromisoformat("2026-10-19T08:00:00+08:00")
OLD = "2026-10-17T00:00:00+00:00"
RECENT = "2026-10-19T00:00:00+00:00"


class MemoryTimeFormattingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.times = load_module("src.plugins.ai_chat.memory_time", AI_CHAT_ROOT / "memory_time.py")

    def test_beijing_and_elapsed_time_across_midnight(self):
        label = self.times.time_label("2026-10-18T23:55:00Z", now=NOW)
        self.assertIn("2026-10-19 07:55:00 北京时间", label)
        self.assertIn("5分0秒前", label)
        self.assertIn("2天0小时前", self.times.time_label(OLD, now=NOW))
        self.assertIn("2026-10-19 00:00:00", self.times.time_label("2026-10-18T16:00:00Z", now=NOW))

    def test_unknown_naive_and_future_times_are_not_fabricated(self):
        for value in [None, "", "bad", "2026-10-19T08:00:00", 123]:
            with self.subTest(value=value):
                self.assertEqual(self.times.time_label(value, now=NOW), "未知")
        self.assertIn("需核对时钟", self.times.time_label("2026-10-20T00:00:00Z", now=NOW))

    def test_platform_time_validation(self):
        self.assertEqual(self.times.event_message_time(SimpleNamespace(time=NOW.timestamp()), now=NOW), RECENT)
        for value in [None, True, -1, 0, "123", float("inf"), float("nan"), 1e100, NOW.timestamp() + 1]:
            with self.subTest(value=value):
                self.assertIsNone(self.times.event_message_time(SimpleNamespace(time=value), now=NOW))

    def test_record_time_is_not_called_sent_time(self):
        old = self.times.message_time_context({"created_at": OLD}, now=NOW)
        self.assertIn("记录时间（非发送确认）", old)
        self.assertIn("2天0小时前", old)

    def test_summary_generation_and_coverage_are_distinct(self):
        summary = SimpleNamespace(created_at=RECENT, source_start_at=OLD, source_end_at=OLD)
        text = self.times.summary_time_context(summary, now=NOW)
        self.assertIn("摘要生成时间：2026-10-19", text)
        self.assertIn("原消息时间范围：2026-10-17", text)
        unknown = self.times.summary_time_context(SimpleNamespace(created_at=RECENT), now=NOW)
        self.assertIn("未知（旧原文时间未保留）", unknown)


class MemoryTimelineStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = load_legacy_memory_modules()
        for name, module in cls.modules.items():
            setattr(cls, name, module)
        cls.rag = load_rag_modules()
        cls.times = load_module("src.plugins.ai_chat.memory_time", AI_CHAT_ROOT / "memory_time.py")
        cls.rag_times = load_module("src.plugins.ai_chat.rag.memory_time", AI_CHAT_ROOT / "rag" / "memory_time.py")
        cls.compressor = load_module("src.plugins.ai_chat.compressor", AI_CHAT_ROOT / "compressor.py")
        cls.ephemeral = load_module("src.plugins.ai_chat.ephemeral_persona_history", AI_CHAT_ROOT / "ephemeral_persona_history.py")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "test.db"
        self.scope = self.database.database_path_scope(self.path)
        self.scope.__enter__()
        self.addCleanup(self.scope.__exit__, None, None, None)
        for name in ["sync_session_summary_after_write", "sync_manual_memory_after_write"]:
            patcher = patch.object(self.rag["runtime_sync"], name)
            patcher.start()
            self.addCleanup(patcher.stop)

    def append(self, role, text, at=OLD, key="private:1"):
        self.memory.append_message(key, role, text, "private", "1", occurred_at=at if role == "user" else None)
        if role == "assistant" and at:
            self.memory.mark_assistant_sent(key, text, sent_at=at)

    def rows(self):
        with self.database.connect() as connection:
            return connection.execute("SELECT * FROM messages ORDER BY id").fetchall()

    def add_summary(self, start, end, key="private:1"):
        return self.summaries.add_summary(key, "private", "1", None, "摘要正文", start, end, end - start + 1)

    def test_persisted_event_time_and_send_receipt_do_not_change_body(self):
        self.append("user", "原始正文")
        self.append("assistant", "原始回答", at=None)
        self.assertIsNone(self.rows()[1]["occurred_at"])
        self.memory.mark_assistant_sent("private:1", "不匹配", sent_at=OLD)
        self.assertIsNone(self.rows()[1]["occurred_at"])
        self.memory.mark_assistant_sent("private:1", "原始回答", sent_at=RECENT)
        self.memory.mark_assistant_sent("private:1", "原始回答", sent_at=OLD)
        rows = self.rows()
        self.assertEqual(rows[0]["occurred_at"], OLD)
        self.assertEqual(rows[0]["time_kind"], "platform_sent")
        self.assertEqual(rows[1]["occurred_at"], RECENT)
        self.assertEqual(rows[1]["time_kind"], "reply_sent")
        self.assertEqual([row["content"] for row in rows], ["原始正文", "原始回答"])

    def test_receipt_cannot_mark_an_older_reply_or_another_session(self):
        self.append("assistant", "旧答复", at=None)
        self.append("user", "新请求")
        self.memory.mark_assistant_sent("private:1", "旧答复", sent_at=RECENT)
        self.memory.mark_assistant_sent("private:other", "旧答复", sent_at=RECENT)
        self.assertIsNone(self.rows()[0]["occurred_at"])

    def test_recent_history_ages_on_read_and_retains_chat_api_shape(self):
        self.append("user", "昨天的计划")
        self.append("assistant", "记下了", at=OLD)
        with patch.object(self.memory, "datetime") as clock:
            clock.now.return_value = NOW
            first = self.memory.build_history("private:1", 10)
            clock.now.return_value = NOW + timedelta(days=3)
            second = self.memory.build_history("private:1", 10)
        self.assertEqual([item["role"] for item in first], ["user", "assistant"])
        self.assertTrue(all(set(item) == {"role", "content"} for item in first))
        self.assertIn("2天0小时前", first[1]["content"])
        self.assertIn("5天0小时前", second[1]["content"])
        self.assertEqual(second[1]["content"].count("回复首段发送确认时间"), 1)
        self.assertEqual(self.rows()[1]["content"], "记下了")

    def test_summary_ranges_survive_original_deletion(self):
        self.append("user", "过去", at=OLD)
        self.append("assistant", "现在", at=RECENT)
        summary_id = self.add_summary(1, 2)
        with self.database.connect() as connection:
            connection.execute("DELETE FROM messages")
        summary = self.summaries.get_session_summary(summary_id)
        self.assertEqual((summary.source_start_at, summary.source_end_at), (OLD, RECENT))
        context = self.summaries.format_summary_context("private:1", 1)
        self.assertIn("摘要生成时间", context)
        self.assertIn("2026-10-17 08:00:00", context)
        self.assertIn("摘要正文", context)

    def test_missing_endpoint_is_not_replaced_by_partial_range(self):
        self.append("user", "other", key="private:other")
        self.append("assistant", "本会话", at=RECENT)
        summary = self.summaries.get_session_summary(self.add_summary(1, 2))
        self.assertIsNone(summary.source_start_at)
        self.assertEqual(summary.source_end_at, RECENT)
        self.gap_scene_summaries.upsert_gap_scene_summary("private:1", 1, "卡片", 1, 2, 2)
        card = self.gap_scene_summaries.get_gap_scene_summary("private:1", 1)
        self.assertIsNone(card.source_start_at)
        self.assertEqual(card.source_end_at, RECENT)

    def test_legacy_upgrade_is_idempotent_and_respects_session_boundaries(self):
        self.append("user", "legacy", key="private:other")
        self.append("assistant", "legacy answer", at=None)
        first_id = self.add_summary(1, 2)
        missing_id = self.add_summary(99, 100)
        self.gap_scene_summaries.upsert_gap_scene_summary("private:1", 1, "旧卡片", 1, 2, 2)
        with self.database.connect() as connection:
            original = [(row["content"], row["created_at"]) for row in self.rows()]
            for table, fields in {"messages": ["occurred_at", "time_kind"],
                                  "session_summaries": ["source_start_at", "source_end_at"],
                                  "gap_scene_summaries": ["source_start_at", "source_end_at"]}.items():
                for field in fields:
                    connection.execute(f"ALTER TABLE {table} DROP COLUMN {field}")
            connection.execute("UPDATE schema_meta SET value='7' WHERE key='schema_version'")
        self.database.ensure_database()
        self.database.ensure_database()
        self.assertEqual([(row["content"], row["created_at"]) for row in self.rows()], original)
        self.assertTrue(all(row["occurred_at"] is None for row in self.rows()))
        summary = self.summaries.get_session_summary(first_id)
        self.assertIsNone(summary.source_start_at)
        self.assertEqual(summary.source_end_at, original[1][1])
        missing = self.summaries.get_session_summary(missing_id)
        self.assertIsNone(missing.source_start_at)
        self.assertIsNone(missing.source_end_at)
        card = self.gap_scene_summaries.get_gap_scene_summary("private:1", 1)
        self.assertIsNone(card.source_start_at)
        self.assertEqual(card.source_end_at, original[1][1])
        self.assertIn("记录时间（非发送确认）", self.memory.build_history("private:1", 2)[0]["content"])

    def test_failed_upgrade_rolls_back_all_new_columns(self):
        connection = sqlite3.connect(":memory:")
        self.addCleanup(connection.close)
        connection.executescript("CREATE TABLE schema_meta (key TEXT, value TEXT); CREATE TABLE messages (id INTEGER);")
        def execute(sql, *args):
            if "ADD COLUMN time_kind" in sql:
                raise sqlite3.OperationalError("simulated failure")
            return connection.execute(sql, *args)
        with self.assertRaises(sqlite3.OperationalError):
            self.database._ensure_memory_time_schema(SimpleNamespace(execute=execute))
        self.assertEqual([row[1] for row in connection.execute("PRAGMA table_info(messages)")], ["id"])

    def test_compression_preserves_time_before_deleting_source(self):
        self.append("user", "过去", at=OLD)
        self.append("assistant", "现在", at=RECENT)
        config = SimpleNamespace(enable_auto_summary_compression=True, summary_keep_recent_messages=0,
                                 summary_min_source_messages=0, bot_owner_qq="1")
        summarize = AsyncMock(return_value=SimpleNamespace(succeeded=True, summary="压缩摘要"))
        with patch.object(self.compressor, "summarize_messages_with_detail", new=summarize):
            result = asyncio.run(self.compressor.compress_session(config, "private:1", force=True))
        self.assertTrue(result.compressed)
        self.assertEqual(self.rows(), [])
        self.assertIn("2026-10-17 08:00:00", summarize.call_args.args[1])
        summary = self.summaries.get_session_summary(result.summary_id)
        self.assertEqual((summary.source_start_at, summary.source_end_at), (OLD, RECENT))

    def test_failed_compression_keeps_original_time_and_messages(self):
        self.append("user", "保留")
        config = SimpleNamespace(enable_auto_summary_compression=True, summary_keep_recent_messages=0,
                                 summary_min_source_messages=0, bot_owner_qq="1")
        with patch.object(self.compressor, "summarize_messages_with_detail", new=AsyncMock(
                return_value=SimpleNamespace(succeeded=False, failure_detail="timeout"))):
            result = asyncio.run(self.compressor.compress_session(config, "private:1", force=True))
        self.assertFalse(result.compressed)
        self.assertEqual(self.rows()[0]["occurred_at"], OLD)

    def test_live_card_generation_update_and_source_times_are_separate(self):
        self.append("user", "first", at=OLD)
        self.append("assistant", "second", at=RECENT)
        gap = self.gap_scene_summaries
        with patch.object(gap, "utc_now", return_value=OLD):
            gap.upsert_gap_scene_summary("private:1", 1, "第一版", 1, 1, 1)
        with patch.object(gap, "utc_now", return_value=RECENT):
            gap.upsert_gap_scene_summary("private:1", 1, "第二版", 1, 2, 2)
        card = gap.get_gap_scene_summary("private:1", 1)
        self.assertEqual((card.created_at, card.updated_at), (OLD, RECENT))
        self.assertEqual((card.source_start_at, card.source_end_at), (OLD, RECENT))
        self.assertIn("状态卡更新时间", gap.format_gap_scene_context("private:1", 1))

    def test_persona_database_times_do_not_mix(self):
        self.append("user", "aike", at=OLD)
        with self.database.database_path_scope(self.path.with_name("linyin.db")):
            self.append("user", "linyin", at=RECENT)
            linyin = self.memory.build_history("private:1", 2)
        aike = self.memory.build_history("private:1", 2)
        self.assertIn("2026-10-17", aike[0]["content"])
        self.assertNotIn("linyin", aike[0]["content"])
        self.assertIn("2026-10-19", linyin[0]["content"])

    def test_rag_summary_uses_original_source_not_index_creation(self):
        self.append("user", "source", at=OLD)
        summary_id = self.add_summary(1, 1)
        doc = SimpleNamespace(source_type="session_summary", source_id=str(summary_id), session_key="private:1",
                              source_version=RECENT, created_at="2099-01-01T00:00:00Z")
        text = self.rag_times.memory_document_time_context(doc)
        self.assertIn("2026-10-17", text)
        self.assertNotIn("2099", text)
        doc.session_key = "private:other"
        self.assertIn("未知（旧原文时间未保留）", self.rag_times.memory_document_time_context(doc))

    def test_rag_stale_manual_memory_does_not_use_new_edit_time(self):
        with patch.object(self.manual_memory, "utc_now", return_value=OLD):
            memory_id = self.manual_memory.add_manual_memory("private", "1", "old content")
        with self.database.connect() as connection:
            connection.execute("UPDATE long_term_memories SET updated_at=?, content='new content' WHERE id=?",
                               (RECENT, memory_id))
        doc = SimpleNamespace(source_type="manual_fact", source_id=str(memory_id), source_version=OLD)
        text = self.rag_times.memory_document_time_context(doc)
        self.assertIn("旧版检索内容", text)
        self.assertIn("本版维护时间：2026-10-17", text)
        self.assertNotIn("2026-10-19", text)
        self.assertIn("最后维护时间：2026-10-19", self.manual_memory.format_manual_memory_context([("private", "1")], 10))

    def test_rag_missing_database_is_read_only_and_falls_back_to_source_version(self):
        doc = SimpleNamespace(source_type="session_summary", source_id="1", session_key="private:1", source_version=OLD)
        self.assertFalse(self.path.exists())
        text = self.rag_times.memory_document_time_context(doc)
        self.assertFalse(self.path.exists())
        self.assertIn("摘要生成时间：2026-10-17", text)
        self.assertIn("未知（旧原文时间未保留）", text)

    def test_rag_time_rendering_does_not_reembed_or_mutate_document(self):
        self.append("user", "source", at=OLD)
        summary_id = self.add_summary(1, 1)
        provider = SimpleNamespace(provider="unit", model="unit", embed=Mock(return_value=[1.0, 0.0]))
        index = self.rag["memory_index"]
        document_id = index.sync_session_summary_by_id(summary_id, embedder=provider)
        document = self.rag["documents"].get_rag_document(document_id)
        result = self.rag["schema"].RagSearchResult(document=document, score=1.0)
        first = index.format_memory_results([result])
        second = index.format_memory_results([result])
        index.sync_session_summary_by_id(summary_id, embedder=provider)
        provider.embed.assert_called_once()
        self.assertIn("摘要生成时间", first)
        self.assertIn("原消息时间范围", second)
        self.assertEqual(document.content, "摘要正文")
        self.assertEqual(document.content_hash, self.rag["documents"].get_rag_document(document_id).content_hash)

    def test_persist_graph_forwards_platform_time_without_labeling_unsent_reply(self):
        graph = load_module("src.plugins.ai_chat.graph.memory", AI_CHAT_ROOT / "graph" / "memory.py")
        ns = plugin_functions({"run_memory_persist_graph"}, {
            "MemoryPersistState": graph.MemoryPersistState, "MemoryPersistGraphRunner": graph.MemoryPersistGraphRunner,
            "stored_user_content": lambda event, text: text, "append_message": self.memory.append_message,
            "event_message_time": self.times.event_message_time,
        })
        event = SimpleNamespace(time=NOW.timestamp(), message_type="private")
        asyncio.run(ns["run_memory_persist_graph"]("private:1", event,
            prompt_context=SimpleNamespace(user_id="1", group_id=None),
            turn=SimpleNamespace(stored_user="user", stored_assistant="answer")))
        rows = self.rows()
        self.assertEqual(rows[0]["occurred_at"], RECENT)
        self.assertEqual(rows[0]["time_kind"], "platform_sent")
        self.assertIsNone(rows[1]["occurred_at"])

    def test_ephemeral_history_preserves_times_without_extra_api_fields(self):
        history = self.ephemeral.EphemeralPersonaHistory()
        history.append_turn("persona:linyin:private:1", "user", "answer", 10, user_occurred_at=OLD)
        history.mark_assistant_sent("persona:linyin:private:1", "answer", sent_at=RECENT)
        prompt = history.build_history("persona:linyin:private:1", 10)
        self.assertTrue(all(set(item) == {"role", "content"} for item in prompt))
        self.assertIn("消息发送时间：2026-10-17", prompt[0]["content"])
        self.assertIn("回复首段发送确认时间：2026-10-19", prompt[1]["content"])
        self.assertEqual(history._messages["persona:linyin:private:1"][1]["content"], "answer")


class MemoryTimeRuntimeTests(unittest.TestCase):
    def test_voice_receipt_is_carried_through_persistence_and_failures_have_no_receipt(self):
        ensure_ai_chat_packages()
        contracts = load_module("src.plugins.ai_chat.chat_contracts", AI_CHAT_ROOT / "chat_contracts.py")
        module = load_module("src.plugins.ai_chat.ephemeral_persona_history", AI_CHAT_ROOT / "ephemeral_persona_history.py")
        times = load_module("src.plugins.ai_chat.memory_time", AI_CHAT_ROOT / "memory_time.py")
        history = module.EphemeralPersonaHistory()
        markers = []
        def delivery(event, content, *, sent_at):
            self.assertEqual(history.message_count("private:1"), 2)
            markers.append(sent_at)
            history.mark_assistant_sent("private:1", content, sent_at=sent_at)
        namespace = plugin_functions({"send_semantic_voice_response", "finalize_chat_result"}, {
            "ChatRuntimeResult": contracts.ChatRuntimeResult, "datetime": datetime, "timezone": timezone,
            "send_tts_record": AsyncMock(), "log_ai_event_error": Mock(), "config": SimpleNamespace(max_context_messages=10),
            "build_chat_turn": lambda user, answer: contracts.ChatTurn(user, answer),
            "ephemeral_persona_history": history, "event_message_time": times.event_message_time,
            "record_chat_message_delivery": delivery, "update_chat_commit": Mock(), "should_count_private_trial": lambda event: False,
        })
        event, matcher = SimpleNamespace(time=NOW.timestamp()), SimpleNamespace(finish=AsyncMock())
        result = contracts.ChatRuntimeResult(reply="voice", stored_assistant="voice")
        options = contracts.ChatOptions(semantic_voice=True)
        sent = asyncio.run(namespace["send_semantic_voice_response"](None, event, matcher, result, options))
        self.assertIsNotNone(times.parse_memory_time(sent.assistant_sent_at))
        self.assertEqual(markers, [])
        asyncio.run(namespace["finalize_chat_result"](None, event, matcher, "private:1", None,
            contracts.ChatUserContent("user", "user", "user"), sent, options,
            persistent_memory_enabled=False, tts_candidate_enabled=False))
        self.assertEqual(markers, [sent.assistant_sent_at])
        self.assertIn("回复首段发送确认时间", history.build_history("private:1", 10)[1]["content"])
        namespace["send_tts_record"] = AsyncMock(side_effect=RuntimeError("failed"))
        failed = asyncio.run(namespace["send_semantic_voice_response"](None, event, matcher, result, options))
        self.assertIsNone(failed)
        self.assertEqual(markers, [sent.assistant_sent_at])

    def test_delivery_routes_to_persona_scoped_database_and_isolates_failures(self):
        ensure_ai_chat_packages()
        database = load_module("src.plugins.ai_chat.database", AI_CHAT_ROOT / "database.py")
        marker = Mock()
        ephemeral = SimpleNamespace(mark_assistant_sent=Mock())
        scope = SimpleNamespace(configuration_error="", memory_v2_active=True, routing_v2_active=True, persona_id="linyin")
        with tempfile.TemporaryDirectory() as root:
            linyin_path = Path(root) / "linyin.db"
            def mark(*args, **kwargs):
                self.assertEqual(database.current_database_path(), linyin_path)
                marker(*args, **kwargs)
            namespace = plugin_functions({"record_chat_message_delivery"}, {
                "conversation_scope": lambda event: scope, "chat_session_key": lambda event: "persona:linyin:private:1",
                "persona_memory_database_scope": lambda persona: database.database_path_scope(linyin_path),
                "mark_assistant_sent": mark, "ephemeral_persona_history": ephemeral, "log_background_error": Mock(),
            })
            namespace["record_chat_message_delivery"](object(), "answer", sent_at=RECENT)
            marker.assert_called_once_with("persona:linyin:private:1", "answer", sent_at=RECENT)
            ephemeral.mark_assistant_sent.assert_not_called()
            scope.memory_v2_active = False
            namespace["record_chat_message_delivery"](object(), "temporary")
            ephemeral.mark_assistant_sent.assert_called_once()
            scope.configuration_error = "unassigned"
            namespace["record_chat_message_delivery"](object(), "rejected")
            self.assertEqual(marker.call_count, 1)
            scope.configuration_error = ""
            scope.routing_v2_active = False
            namespace["mark_assistant_sent"] = Mock(side_effect=RuntimeError("busy"))
            namespace["record_chat_message_delivery"](object(), "answer")
            namespace["log_background_error"].assert_called_once()

    def test_scene_context_retains_absolute_and_relative_time_without_modifying_text(self):
        ensure_ai_chat_packages()
        hub = load_module("src.plugins.ai_chat.scene_hub", AI_CHAT_ROOT / "scene_hub.py")
        event = hub.PublicSceneEvent("turn", "aike", "scene text", recorded_at=OLD)
        with patch.object(hub, "datetime") as clock:
            clock.now.return_value = NOW
            payload = hub.public_context_payload([event], max_events=1)
        self.assertEqual(payload[0]["text"], "scene text")
        self.assertIn("2026-10-17 08:00:00", payload[0]["time_context"])
        self.assertIn("2天0小时前", payload[0]["time_context"])


if __name__ == "__main__":
    unittest.main()
