from __future__ import annotations

import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from pure_ai_chat_loader import AI_CHAT_ROOT, load_legacy_memory_modules, load_module


class TempDatabaseMixin:
    def temp_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "chatbot.db"
        patcher = patch.object(self.database, "DATABASE_PATH", db_path)
        return temp_dir, patcher


class OwnerConsoleReadRuntimeTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.agent_tasks = cls.memory_modules["agent_tasks"]
        cls.owner_console = load_module(
            "src.plugins.ai_chat.owner_console_read_runtime",
            AI_CHAT_ROOT / "owner_console_read_runtime.py",
        )
        cls.config_module = load_module(
            "src.plugins.ai_chat.config",
            AI_CHAT_ROOT / "config.py",
        )
        cls.access_store = load_module(
            "src.plugins.ai_chat.access_store",
            AI_CHAT_ROOT / "access_store.py",
        )

    def test_task_and_approval_lists_are_structured_and_scoped(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="delete summary 41",
            )
            other_task_id = self.agent_tasks.create_agent_task(
                session_key="private:20002",
                user_id="20002",
                goal="other owner task",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"delete_session_summary","summary_id":41}',
                risk_level="write_local",
                reason="delete the selected session summary",
            )
            context = self.owner_console.OwnerConsoleContext(
                session_key="private:10001",
                user_id="10001",
            )

            task_list = self.owner_console.build_owner_console_task_list(context)
            approval_list = self.owner_console.build_owner_console_approval_list(context)

        self.assertEqual([row.task_id for row in task_list.rows], [task_id])
        self.assertNotIn(other_task_id, [row.task_id for row in task_list.rows])
        self.assertEqual(task_list.total_visible, 1)
        self.assertEqual(task_list.rows[0].status, self.agent_tasks.AGENT_TASK_PENDING)
        self.assertEqual(task_list.rows[0].status_label, "待处理")
        self.assertEqual(task_list.rows[0].pending_approval_ids, [approval_id])
        self.assertEqual(task_list.rows[0].next_action, "review_pending_approval")
        self.assertEqual(task_list.rows[0].latest_event_kind, "approval_requested")
        self.assertFalse(task_list.boundary.ordinary_chat_can_trigger_main_agent)
        self.assertTrue(task_list.boundary.owner_write_requires_approval)

        self.assertEqual([row.approval_id for row in approval_list.rows], [approval_id])
        actionability = approval_list.rows[0].actionability
        self.assertTrue(actionability.can_approve)
        self.assertTrue(actionability.can_reject)
        self.assertIsNone(actionability.resume_enabled)
        self.assertEqual(actionability.blocked_reason, "")
        self.assertTrue(actionability.future_operation_only)

    def test_running_work_task_is_visible_through_read_only_task_models(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                title="研发上下文报告",
                goal="研发上下文报告：恢复当前开发状态",
            )
            task, claimed = self.agent_tasks.claim_agent_task_for_work(
                task_id=task_id,
                session_key="private:10001",
                user_id="10001",
                work_type="development_context_report",
                query_summary="恢复当前开发状态",
            )
            context = self.owner_console.OwnerConsoleContext(
                session_key="private:10001",
                user_id="10001",
            )
            task_list = self.owner_console.build_owner_console_task_list(
                context,
                status="running",
            )
            task_detail = self.owner_console.build_owner_console_task_detail(
                context,
                task_id,
            )

        self.assertTrue(claimed)
        self.assertIsNotNone(task)
        self.assertEqual(task_list.status_filter, "running")
        self.assertIsNone(task_list.work_type_filter)
        self.assertEqual([row.task_id for row in task_list.rows], [task_id])
        self.assertEqual(task_list.rows[0].work_type, "development_context_report")
        self.assertEqual(task_list.rows[0].status, self.agent_tasks.AGENT_TASK_RUNNING)
        self.assertEqual(task_list.rows[0].status_label, "运行中")
        self.assertEqual(task_list.rows[0].next_action, "monitor_running_task")
        self.assertIsNotNone(task_detail)
        assert task_detail is not None
        self.assertEqual(task_detail.task.status, self.agent_tasks.AGENT_TASK_RUNNING)
        self.assertEqual(
            [event.kind for event in task_detail.events],
            ["created", "work_claimed", "work_started"],
        )
        self.assertEqual(task_detail.task.work_type, "development_context_report")

    def test_task_work_type_is_filtered_in_sql_and_unknown_values_are_hidden(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            external_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="主人显式提供的外部只读查询（原文未持久化）",
            )
            self.agent_tasks.claim_agent_task_for_work(
                task_id=external_task_id,
                session_key="private:10001",
                user_id="10001",
                work_type="external_read_report",
                query_summary="主人显式提供的外部只读查询（原文未持久化）",
            )
            polluted_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="newer task",
            )
            self.agent_tasks.claim_agent_task_for_work(
                task_id=polluted_task_id,
                session_key="private:10001",
                user_id="10001",
                work_type="query=must-not-leak",
                query_summary="fixed placeholder",
            )
            context = self.owner_console.OwnerConsoleContext(
                session_key="private:10001",
                user_id="10001",
            )

            filtered = self.owner_console.build_owner_console_task_list(
                context,
                work_type="external_read_report",
                limit=1,
            )
            all_tasks = self.owner_console.build_owner_console_task_list(
                context,
                limit=5,
            )

        self.assertEqual(filtered.work_type_filter, "external_read_report")
        self.assertEqual([row.task_id for row in filtered.rows], [external_task_id])
        rows = {row.task_id: row for row in all_tasks.rows}
        self.assertEqual(rows[external_task_id].work_type, "external_read_report")
        self.assertEqual(rows[polluted_task_id].work_type, "")
        self.assertNotIn(
            "must-not-leak",
            json.dumps(
                self.owner_console.owner_console_to_jsonable(rows[polluted_task_id]),
                ensure_ascii=False,
            ),
        )
        with self.assertRaises(ValueError):
            self.owner_console.build_owner_console_task_list(
                context,
                work_type="unknown_work",
            )

    def test_task_and_approval_details_include_redacted_previews(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="store a redacted tool input preview",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="owner_write_command",
                tool_input_json=(
                    '{"command":"add_fact_memory","api_key":"SECRET-KEY",'
                    '"content":"'
                    + ("x" * 240)
                    + '"}'
                ),
                risk_level="write_local",
                reason="owner requested a fact memory with secret-looking input",
            )
            context = self.owner_console.OwnerConsoleContext(
                session_key="private:10001",
                user_id="10001",
            )

            task_detail = self.owner_console.build_owner_console_task_detail(
                context,
                task_id,
                preview_limit=120,
            )
            approval_detail = self.owner_console.build_owner_console_approval_detail(
                context,
                approval_id,
                preview_limit=120,
            )

        self.assertIsNotNone(task_detail)
        assert task_detail is not None
        self.assertEqual(task_detail.task.task_id, task_id)
        self.assertEqual(task_detail.goal, "store a redacted tool input preview")
        self.assertEqual([approval.approval_id for approval in task_detail.approvals], [approval_id])
        self.assertEqual(
            [event.kind for event in task_detail.events],
            ["created", "approval_requested"],
        )
        event_previews = "\n".join(event.input_preview for event in task_detail.events)
        self.assertNotIn("SECRET-KEY", event_previews)

        self.assertIsNotNone(approval_detail)
        assert approval_detail is not None
        self.assertEqual(approval_detail.approval.approval_id, approval_id)
        self.assertIsNotNone(approval_detail.task)
        assert approval_detail.task is not None
        self.assertEqual(approval_detail.task.task_id, task_id)
        self.assertTrue(approval_detail.tool_input.redacted)
        self.assertTrue(approval_detail.tool_input.truncated)
        self.assertIn('"api_key":"***"', approval_detail.tool_input.preview_json)
        self.assertNotIn("SECRET-KEY", approval_detail.tool_input.preview_json)
        self.assertNotIn("Agent 审批详情卡", approval_detail.tool_input.preview_json)

    def test_non_pending_approval_actionability_is_blocked(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="approve once",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"clear_error_log"}',
                risk_level="write_local",
                reason="clear errors",
            )
            self.agent_tasks.decide_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                approved=True,
            )
            context = self.owner_console.OwnerConsoleContext(
                session_key="private:10001",
                user_id="10001",
            )

            approval_detail = self.owner_console.build_owner_console_approval_detail(
                context,
                approval_id,
            )

        self.assertIsNotNone(approval_detail)
        assert approval_detail is not None
        actionability = approval_detail.approval.actionability
        self.assertEqual(approval_detail.approval.status, self.agent_tasks.AGENT_APPROVAL_APPROVED)
        self.assertFalse(actionability.can_approve)
        self.assertFalse(actionability.can_reject)
        self.assertIsNone(actionability.resume_enabled)
        self.assertEqual(actionability.blocked_reason, "approval is not pending")
        self.assertTrue(actionability.future_operation_only)

    def test_overview_summarizes_counts_and_recent_items(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            first_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="pending task with approval",
            )
            second_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="failed task",
            )
            third_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="latest pending task",
            )
            other_task_id = self.agent_tasks.create_agent_task(
                session_key="private:20002",
                user_id="20002",
                goal="other owner pending task",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=first_task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"clear_image_cache"}',
                risk_level="write_local",
                reason="clear image cache",
            )
            self.agent_tasks.create_agent_approval(
                task_id=other_task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"clear_error_log"}',
                risk_level="write_local",
                reason="other owner approval",
            )
            with self.database.connect() as connection:
                connection.execute(
                    """
                    UPDATE agent_tasks
                    SET status = ?, result = ?
                    WHERE id = ?
                    """,
                    (
                        self.agent_tasks.AGENT_TASK_FAILED,
                        "failed during test",
                        second_task_id,
                    ),
                )
            context = self.owner_console.OwnerConsoleContext(
                session_key="private:10001",
                user_id="10001",
            )

            overview = self.owner_console.build_owner_console_overview(
                context,
                task_limit=2,
                approval_limit=3,
            )

        self.assertEqual(overview.task_limit, 2)
        self.assertEqual(overview.approval_limit, 3)
        self.assertEqual(overview.counters.pending_tasks, 2)
        self.assertEqual(overview.counters.failed_tasks, 1)
        self.assertEqual(overview.counters.pending_approvals, 1)
        self.assertEqual(overview.counters.recent_tasks_visible, 2)
        self.assertEqual(overview.counters.pending_approvals_visible, 1)
        self.assertEqual(
            [row.task_id for row in overview.recent_tasks],
            [third_task_id, second_task_id],
        )
        self.assertNotIn(other_task_id, [row.task_id for row in overview.recent_tasks])
        self.assertEqual([row.approval_id for row in overview.pending_approvals], [approval_id])
        self.assertFalse(overview.boundary.ordinary_chat_can_trigger_main_agent)
        self.assertTrue(overview.boundary.owner_write_requires_approval)

    def test_access_control_snapshot_is_structured_and_truncated(self):
        with patch.dict(
            os.environ,
            {
                "BOT_OWNER_QQ": "10001",
                "ENABLE_PRIVATE_CHAT": "true",
                "ENABLE_GROUP_CHAT": "true",
                "ALLOW_UNKNOWN_PRIVATE_CHAT": "false",
            },
            clear=True,
        ):
            config = self.config_module.load_config()
        access = self.access_store.AccessStore(
            private_whitelist=frozenset({"30003", "10001", "20002"}),
            group_whitelist=frozenset({"90001", "90002"}),
            user_blacklist=frozenset({"40004"}),
        )

        snapshot = self.owner_console.build_owner_console_access_control_snapshot(
            config,
            access,
            item_limit=2,
        )

        self.assertTrue(snapshot.owner_configured)
        self.assertTrue(snapshot.private_chat_enabled)
        self.assertTrue(snapshot.group_chat_enabled)
        self.assertEqual(snapshot.unknown_private_policy, "deny")
        self.assertEqual(snapshot.private_whitelist.count, 3)
        self.assertEqual(snapshot.private_whitelist.items, ["10001", "20002"])
        self.assertTrue(snapshot.private_whitelist.truncated)
        self.assertEqual(snapshot.group_whitelist.items, ["90001", "90002"])
        self.assertFalse(snapshot.group_whitelist.truncated)
        self.assertEqual(snapshot.user_blacklist.items, ["40004"])
        self.assertTrue(snapshot.boundary.owner_write_requires_approval)

    def test_settings_snapshot_redacts_urls_and_lists_role_cards(self):
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-secret-openai",
                "OPENAI_BASE_URL": "https://user:pass@example.com/v1?api_key=hidden",
                "OPENAI_MODEL": "fallback-chat",
                "CHAT_LLM_MODEL": "chat-model",
                "CHAT_LLM_TIMEOUT_SECONDS": "31",
                "MAIN_LLM_API_KEY": "main-secret",
                "MAIN_LLM_BASE_URL": "https://main.example.com/v1?token=hidden",
                "MAIN_LLM_MODEL": "main-model",
                "MAIN_LLM_TIMEOUT_SECONDS": "41",
                "MEMORY_RAG_EMBEDDING_BASE_URL": "http://127.0.0.1:11434/private?token=hidden",
                "MEMORY_RAG_EMBEDDING_MODEL": "bge-m3",
                "MEMORY_RAG_EMBEDDING_TIMEOUT_SECONDS": "17",
                "ENABLE_MAIN_AGENT": "true",
                "MAIN_AGENT_USE_LLM": "true",
                "ENABLE_MEMORY_RAG": "true",
                "ENABLE_PROJECT_DOC_RAG": "true",
                "MEMORY_RAG_INJECT_IN_CHAT": "false",
                "ENABLE_AGENT_WEB": "false",
                "ENABLE_AGENT_SHELL": "false",
            },
            clear=True,
        ):
            config = self.config_module.load_config()
        role_cards = [
            types.SimpleNamespace(key="moyan", title="墨烟"),
            types.SimpleNamespace(key="aike", title="爱可"),
        ]

        snapshot = self.owner_console.build_owner_console_settings_snapshot(
            config,
            role_cards=role_cards,
            active_role_card_key="aike",
        )

        self.assertEqual(snapshot.chat_model.model_name, "chat-model")
        self.assertEqual(snapshot.chat_model.base_url_redacted, "https://example.com/v1")
        self.assertTrue(snapshot.chat_model.api_key_configured)
        self.assertEqual(snapshot.chat_model.timeout_seconds, 31)
        self.assertEqual(snapshot.main_agent_model.base_url_redacted, "https://main.example.com/v1")
        self.assertTrue(snapshot.main_agent_model.api_key_configured)
        self.assertEqual(snapshot.embedding.base_url_redacted, "http://127.0.0.1:11434/private")
        self.assertFalse(snapshot.embedding.api_key_configured)
        self.assertEqual(
            [(row.key, row.title, row.active) for row in snapshot.role_cards],
            [("moyan", "墨烟", False), ("aike", "爱可", True)],
        )
        self.assertEqual(snapshot.active_role_card_key, "aike")
        self.assertTrue(snapshot.feature_flags["enable_main_agent"])
        self.assertTrue(snapshot.feature_flags["main_agent_use_llm"])
        self.assertTrue(snapshot.feature_flags["enable_memory_rag"])
        self.assertFalse(snapshot.feature_flags["memory_rag_inject_in_chat"])
        self.assertFalse(snapshot.feature_flags["enable_agent_web"])
        self.assertFalse(snapshot.feature_flags["enable_agent_shell"])
        rendered = repr(snapshot)
        self.assertNotIn("sk-secret-openai", rendered)
        self.assertNotIn("main-secret", rendered)
        self.assertNotIn("hidden", rendered)

    def test_memory_snapshot_exposes_counts_flags_and_boundaries_without_content(self):
        with patch.dict(
            os.environ,
            {
                "ENABLE_MEMORY_COMPRESSION": "false",
                "ENABLE_GAP_SCENE_SUMMARIES": "true",
                "ENABLE_LONG_TERM_MEMORY_CONTEXT": "true",
                "MAX_CONTEXT_MESSAGES": "42",
                "MAX_STORED_MESSAGES_PER_SESSION": "121",
                "SUMMARY_KEEP_RECENT_MESSAGES": "43",
                "SUMMARY_BATCH_MESSAGES": "83",
                "SUMMARY_MIN_SOURCE_MESSAGES": "44",
                "MAX_SESSION_SUMMARIES_IN_CONTEXT": "4",
                "MAX_GAP_SCENE_SUMMARIES_IN_CONTEXT": "3",
                "MAX_LONG_TERM_MEMORIES_IN_CONTEXT": "9",
                "ENABLE_MEMORY_RAG": "true",
                "MEMORY_RAG_INJECT_IN_CHAT": "false",
                "MEMORY_RAG_OWNER_ONLY_DEBUG": "false",
                "MEMORY_RAG_TOP_K": "6",
                "MEMORY_RAG_MIN_SCORE": "0.61",
                "MEMORY_RAG_MAX_CONTEXT_CHARS": "1666",
                "MEMORY_RAG_INCLUDE_MANUAL_FACTS": "true",
                "MEMORY_RAG_INCLUDE_MANUAL_PREFERENCES": "false",
                "MEMORY_RAG_INCLUDE_SESSION_SUMMARIES": "true",
                "MEMORY_RAG_INCLUDE_SHORT_MESSAGES": "true",
                "MEMORY_RAG_INCLUDE_GAP_SCENE_SUMMARIES": "true",
                "ENABLE_PROJECT_DOC_RAG": "true",
                "PROJECT_DOC_RAG_TOP_K": "3",
                "PROJECT_DOC_RAG_MIN_SCORE": "0.49",
                "PROJECT_DOC_RAG_MAX_CONTEXT_CHARS": "1234",
            },
            clear=True,
        ):
            config = self.config_module.load_config()

        snapshot = self.owner_console.build_owner_console_memory_snapshot(
            config,
            memory_stats={
                "message_count": 11,
                "session_count": 2,
                "summary_count": 3,
                "summarized_message_count": 34,
                "content": "secret memory content",
            },
            manual_memory_stats={
                "memory_count": 5,
                "subject_count": 4,
                "content": "manual secret",
            },
            gap_scene_stats={
                "summary_count": 6,
                "source_message_count": 78,
                "summary": "gap secret",
            },
            rag_document_stats={
                "document_count": 9,
                "active_document_count": 8,
                "embedding_count": 7,
                "content": "rag secret",
            },
        )

        self.assertEqual(snapshot.counts.message_count, 11)
        self.assertEqual(snapshot.counts.session_count, 2)
        self.assertEqual(snapshot.counts.session_summary_count, 3)
        self.assertEqual(snapshot.counts.summarized_message_count, 34)
        self.assertEqual(snapshot.counts.manual_memory_count, 5)
        self.assertEqual(snapshot.counts.manual_memory_subject_count, 4)
        self.assertEqual(snapshot.counts.gap_scene_summary_count, 6)
        self.assertEqual(snapshot.counts.gap_scene_source_message_count, 78)
        self.assertEqual(snapshot.counts.rag_document_count, 9)
        self.assertEqual(snapshot.counts.rag_active_document_count, 8)
        self.assertEqual(snapshot.counts.rag_embedding_count, 7)
        self.assertFalse(snapshot.context_policy.memory_compression_enabled)
        self.assertTrue(snapshot.context_policy.gap_scene_summaries_enabled)
        self.assertTrue(snapshot.context_policy.long_term_memory_context_enabled)
        self.assertEqual(snapshot.context_policy.max_context_messages, 42)
        self.assertEqual(snapshot.context_policy.max_stored_messages_per_session, 121)
        self.assertEqual(snapshot.context_policy.summary_keep_recent_messages, 43)
        self.assertEqual(snapshot.context_policy.summary_batch_messages, 83)
        self.assertEqual(snapshot.context_policy.summary_min_source_messages, 44)
        self.assertEqual(snapshot.context_policy.max_session_summaries_in_context, 4)
        self.assertEqual(snapshot.context_policy.max_gap_scene_summaries_in_context, 3)
        self.assertEqual(snapshot.context_policy.max_long_term_memories_in_context, 9)
        self.assertTrue(snapshot.memory_rag.enabled)
        self.assertFalse(snapshot.memory_rag.inject_in_chat)
        self.assertFalse(snapshot.memory_rag.owner_only_debug)
        self.assertEqual(snapshot.memory_rag.top_k, 6)
        self.assertAlmostEqual(snapshot.memory_rag.min_score, 0.61)
        self.assertEqual(snapshot.memory_rag.max_context_chars, 1666)
        self.assertTrue(snapshot.memory_rag.include_manual_facts)
        self.assertFalse(snapshot.memory_rag.include_manual_preferences)
        self.assertTrue(snapshot.memory_rag.include_session_summaries)
        self.assertTrue(snapshot.memory_rag.include_short_messages)
        self.assertTrue(snapshot.memory_rag.include_gap_scene_summaries)
        self.assertTrue(snapshot.project_doc_rag.enabled)
        self.assertTrue(snapshot.project_doc_rag.explicit_agent_dev_context_only)
        self.assertFalse(snapshot.project_doc_rag.ordinary_chat_injection_allowed)
        self.assertEqual(snapshot.project_doc_rag.top_k, 3)
        self.assertAlmostEqual(snapshot.project_doc_rag.min_score, 0.49)
        self.assertEqual(snapshot.project_doc_rag.max_context_chars, 1234)
        self.assertFalse(snapshot.memory_content_exposed)
        self.assertFalse(snapshot.project_doc_content_exposed)
        self.assertFalse(snapshot.retrieval_executed)
        self.assertFalse(snapshot.index_rebuild_executed)
        self.assertFalse(snapshot.boundary.project_doc_rag_in_ordinary_chat)
        rendered = repr(snapshot)
        self.assertNotIn("secret memory content", rendered)
        self.assertNotIn("manual secret", rendered)
        self.assertNotIn("gap secret", rendered)
        self.assertNotIn("rag secret", rendered)

    def test_read_runtime_facade_uses_injected_providers_for_console_pages(self):
        temp_dir, patcher = self.temp_database()
        with patch.dict(
            os.environ,
            {
                "BOT_OWNER_QQ": "10001",
                "ENABLE_PRIVATE_CHAT": "true",
                "ENABLE_GROUP_CHAT": "false",
                "ENABLE_MEMORY_RAG": "true",
                "ENABLE_PROJECT_DOC_RAG": "true",
            },
            clear=True,
        ):
            config = self.config_module.load_config()
        access = self.access_store.AccessStore(
            private_whitelist=frozenset({"10001"}),
            group_whitelist=frozenset({"90001"}),
            user_blacklist=frozenset(),
        )
        role_cards = [
            types.SimpleNamespace(key="aike", title="爱可"),
        ]
        runtime = self.owner_console.OwnerConsoleReadRuntime(
            config_provider=lambda: config,
            access_provider=lambda: access,
            role_cards_provider=lambda: role_cards,
            active_role_card_key_provider=lambda: "aike",
            memory_stats_provider=lambda: {
                "message_count": 2,
                "session_count": 1,
                "summary_count": 1,
                "summarized_message_count": 8,
            },
            manual_memory_stats_provider=lambda: {
                "memory_count": 3,
                "subject_count": 2,
            },
            gap_scene_stats_provider=lambda: {
                "summary_count": 4,
                "source_message_count": 30,
            },
            rag_document_stats_provider=lambda: {
                "document_count": 5,
                "active_document_count": 5,
                "embedding_count": 5,
            },
        )

        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="facade task",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"clear_error_log"}',
                risk_level="write_local",
                reason="clear recent errors",
            )
            context = self.owner_console.OwnerConsoleContext(
                session_key="private:10001",
                user_id="10001",
            )

            overview = runtime.build_overview(context)
            task_list = runtime.build_task_list(context)
            task_detail = runtime.build_task_detail(context, task_id)
            approval_list = runtime.build_approval_list(context)
            approval_detail = runtime.build_approval_detail(context, approval_id)

        access_snapshot = runtime.build_access_control_snapshot()
        settings_snapshot = runtime.build_settings_snapshot()
        memory_snapshot = runtime.build_memory_snapshot()
        health_snapshot = runtime.build_health_snapshot(
            bot_status_lines=["Bot OK"],
            diagnostics="诊断正常",
        )

        self.assertEqual(overview.counters.pending_tasks, 1)
        self.assertEqual(overview.counters.pending_approvals, 1)
        self.assertEqual([row.task_id for row in task_list.rows], [task_id])
        self.assertIsNotNone(task_detail)
        assert task_detail is not None
        self.assertEqual(task_detail.task.task_id, task_id)
        self.assertEqual([row.approval_id for row in approval_list.rows], [approval_id])
        self.assertIsNotNone(approval_detail)
        assert approval_detail is not None
        self.assertEqual(approval_detail.approval.approval_id, approval_id)
        self.assertEqual(access_snapshot.private_whitelist.items, ["10001"])
        self.assertFalse(access_snapshot.group_chat_enabled)
        self.assertEqual(settings_snapshot.role_cards[0].key, "aike")
        self.assertTrue(settings_snapshot.role_cards[0].active)
        self.assertTrue(settings_snapshot.feature_flags["enable_memory_rag"])
        self.assertEqual(memory_snapshot.counts.message_count, 2)
        self.assertEqual(memory_snapshot.counts.manual_memory_count, 3)
        self.assertEqual(memory_snapshot.counts.rag_embedding_count, 5)
        self.assertTrue(memory_snapshot.project_doc_rag.explicit_agent_dev_context_only)
        self.assertFalse(memory_snapshot.project_doc_rag.ordinary_chat_injection_allowed)
        self.assertEqual(health_snapshot.bot_status.display_lines, ["Bot OK"])
        self.assertEqual(health_snapshot.diagnostics.summary_text, "诊断正常")
        self.assertFalse(health_snapshot.boundary.ordinary_chat_can_trigger_main_agent)

    def test_provider_wiring_audit_and_factory_keep_adapter_glue_explicit(self):
        calls = {"config": 0, "access": 0}
        with patch.dict(
            os.environ,
            {
                "BOT_OWNER_QQ": "10001",
                "ENABLE_PRIVATE_CHAT": "true",
                "ENABLE_GROUP_CHAT": "true",
            },
            clear=True,
        ):
            config = self.config_module.load_config()
        access = self.access_store.AccessStore(
            private_whitelist=frozenset({"10001"}),
            group_whitelist=frozenset(),
            user_blacklist=frozenset(),
        )

        def config_provider():
            calls["config"] += 1
            return config

        def access_provider():
            calls["access"] += 1
            return access

        providers = self.owner_console.OwnerConsoleReadProviders(
            config_provider=config_provider,
            access_provider=access_provider,
            memory_stats_provider=lambda: {"message_count": 12},
        )

        audit = self.owner_console.build_owner_console_provider_wiring_snapshot(
            providers
        )
        runtime = self.owner_console.create_owner_console_read_runtime(providers)
        access_snapshot = runtime.build_access_control_snapshot()
        memory_snapshot = runtime.build_memory_snapshot()
        serialized_audit = runtime.serialize_page("provider_wiring", audit)

        self.assertEqual(calls, {"config": 2, "access": 1})
        self.assertTrue(audit.runtime_ready)
        self.assertEqual(audit.missing_required, [])
        self.assertFalse(audit.boundary.ordinary_chat_can_trigger_main_agent)
        rows = {row.provider_name: row for row in audit.rows}
        self.assertTrue(rows["config_provider"].required)
        self.assertTrue(rows["config_provider"].configured)
        self.assertTrue(rows["access_provider"].configured)
        self.assertFalse(rows["role_cards_provider"].required)
        self.assertFalse(rows["role_cards_provider"].configured)
        self.assertEqual(
            rows["role_cards_provider"].fallback_behavior,
            "empty role card list",
        )
        self.assertFalse(rows["memory_stats_provider"].required)
        self.assertTrue(rows["memory_stats_provider"].configured)
        self.assertFalse(
            any(row.direct_qq_dependency_allowed for row in audit.rows)
        )
        self.assertFalse(any(row.write_side_effect_allowed for row in audit.rows))
        self.assertEqual(access_snapshot.private_whitelist.items, ["10001"])
        self.assertEqual(memory_snapshot.counts.message_count, 12)
        self.assertEqual(
            serialized_audit["data"]["rows"][0]["provider_name"],
            "config_provider",
        )
        self.assertTrue(serialized_audit["read_only"])

        missing = self.owner_console.OwnerConsoleReadProviders(
            config_provider=config_provider
        )
        missing_audit = self.owner_console.build_owner_console_provider_wiring_snapshot(
            missing
        )
        self.assertFalse(missing_audit.runtime_ready)
        self.assertEqual(missing_audit.missing_required, ["access_provider"])
        with self.assertRaises(ValueError):
            self.owner_console.create_owner_console_read_runtime(missing)

    def test_read_only_route_contract_maps_pages_to_facade_methods(self):
        runtime = self.owner_console.OwnerConsoleReadRuntime(
            config_provider=lambda: self.config_module.load_config(),
            access_provider=lambda: self.access_store.EMPTY_STORE,
        )

        contract = self.owner_console.build_owner_console_route_contract_snapshot()
        runtime_contract = runtime.build_route_contract_snapshot()
        payload = runtime.serialize_page("route_contract", contract)

        expected_pages = [
            "dashboard",
            "tasks",
            "task_detail",
            "approvals",
            "approval_detail",
            "diagnostics",
            "external_read",
            "memory",
            "access_control",
            "settings",
        ]
        self.assertEqual([row.page for row in contract.rows], expected_pages)
        self.assertEqual(contract.route_count, len(expected_pages))
        self.assertEqual(runtime_contract.route_count, contract.route_count)
        self.assertEqual(
            [row.page for row in runtime_contract.rows],
            expected_pages,
        )

        runtime_class = self.owner_console.OwnerConsoleReadRuntime
        for row in contract.rows:
            self.assertTrue(hasattr(runtime_class, row.runtime_method), row.page)
            self.assertEqual(row.response_page, row.page)
            self.assertTrue(row.read_only)
            self.assertFalse(row.http_api_enabled)
            self.assertFalse(row.web_write_enabled)
            self.assertFalse(row.direct_qq_dependency_allowed)
            self.assertFalse(row.write_side_effect_allowed)
        rows = {row.page: row for row in contract.rows}
        self.assertEqual(rows["dashboard"].runtime_method, "build_overview")
        self.assertEqual(rows["dashboard"].read_model, "OwnerConsoleOverview")
        self.assertTrue(rows["dashboard"].requires_context)
        self.assertEqual(rows["task_detail"].required_params, ["task_id"])
        self.assertEqual(rows["approval_detail"].required_params, ["approval_id"])
        self.assertFalse(rows["settings"].requires_context)
        self.assertIn("recent_errors", rows["diagnostics"].optional_params)
        self.assertEqual(payload["page"], "route_contract")
        self.assertEqual(payload["data"]["route_count"], len(expected_pages))
        self.assertFalse(
            payload["data"]["boundary"]["ordinary_chat_can_trigger_main_agent"]
        )

    def test_read_model_serialization_contract_is_json_safe_and_read_only(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="serialize an approval detail",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"add_fact_memory","api_key":"SECRET-KEY"}',
                risk_level="write_local",
                reason="test serializer redaction",
            )
            context = self.owner_console.OwnerConsoleContext(
                session_key="private:10001",
                user_id="10001",
            )

            detail = self.owner_console.build_owner_console_approval_detail(
                context,
                approval_id,
            )

        self.assertIsNotNone(detail)
        assert detail is not None
        payload = self.owner_console.owner_console_page_response(
            "approval_detail",
            detail,
        )
        serialized_detail = self.owner_console.owner_console_to_jsonable(detail)
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        self.assertEqual(
            payload["schema_version"],
            self.owner_console.OWNER_CONSOLE_SCHEMA_VERSION,
        )
        self.assertEqual(payload["page"], "approval_detail")
        self.assertEqual(payload["generated_at"], detail.generated_at)
        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["http_api_enabled"])
        self.assertFalse(payload["web_write_enabled"])
        self.assertEqual(payload["data"]["approval"]["approval_id"], approval_id)
        self.assertEqual(payload["data"]["approval"]["actionability"]["resume_enabled"], None)
        self.assertFalse(
            payload["data"]["boundary"]["ordinary_chat_can_trigger_main_agent"]
        )
        self.assertEqual(serialized_detail["approval"]["approval_id"], approval_id)
        self.assertIn('"api_key":"***"', payload["data"]["tool_input"]["preview_json"])
        self.assertNotIn("SECRET-KEY", rendered)

        runtime = self.owner_console.OwnerConsoleReadRuntime(
            config_provider=lambda: self.config_module.load_config(),
            access_provider=lambda: self.access_store.EMPTY_STORE,
        )
        runtime_payload = runtime.serialize_page("approval_detail", detail)
        self.assertEqual(runtime_payload, payload)
        with self.assertRaises(ValueError):
            self.owner_console.owner_console_page_response("", detail)
        with self.assertRaises(TypeError):
            self.owner_console.owner_console_to_jsonable(object())

    def test_health_snapshot_wraps_diagnostics_text_and_executions(self):
        ok_execution = types.SimpleNamespace(
            result=types.SimpleNamespace(
                reply_text="诊断：正常\n图片缓存：2 条",
                error="",
            )
        )
        error_execution = types.SimpleNamespace(
            result=types.SimpleNamespace(
                reply_text="视觉状态读取失败",
                error="vision unavailable",
            )
        )

        snapshot = self.owner_console.build_owner_console_health_snapshot(
            bot_status_lines=["Bot 状态", "OK"],
            diagnostics=ok_execution,
            config="配置状态：\nMainAgent：开启",
            vision=error_execution,
            image_cache=["图片缓存：2 条"],
            memory=None,
            tts="TTS：关闭",
            recent_errors="暂无最近错误",
            main_agent_observation_lines=["main observation"],
            root_graph_observation_lines=("root observation",),
        )

        self.assertEqual(snapshot.bot_status.display_lines, ["Bot 状态", "OK"])
        self.assertTrue(snapshot.diagnostics.ok)
        self.assertEqual(
            snapshot.diagnostics.display_lines,
            ["诊断：正常", "图片缓存：2 条"],
        )
        self.assertFalse(snapshot.vision.ok)
        self.assertEqual(snapshot.vision.error, "vision unavailable")
        self.assertEqual(snapshot.vision.summary_text, "视觉状态读取失败")
        self.assertEqual(snapshot.config.display_lines, ["配置状态：", "MainAgent：开启"])
        self.assertEqual(snapshot.memory.display_lines, [])
        self.assertEqual(snapshot.tts.summary_text, "TTS：关闭")
        self.assertEqual(snapshot.observations.main_agent, ["main observation"])
        self.assertEqual(snapshot.observations.root_graph, ["root observation"])
        self.assertFalse(snapshot.boundary.ordinary_chat_can_trigger_main_agent)

    def test_owner_console_read_runtime_has_no_qq_adapter_dependency(self):
        runtime_source = (AI_CHAT_ROOT / "owner_console_read_runtime.py").read_text(
            encoding="utf-8"
        )
        models_source = (AI_CHAT_ROOT / "owner_console_read_models.py").read_text(
            encoding="utf-8"
        )
        combined_source = runtime_source + "\n" + models_source

        self.assertNotIn("nonebot", combined_source.lower())
        self.assertNotIn("MessageEvent", combined_source)
        self.assertNotIn("matcher.finish", combined_source)
        self.assertNotIn("bot.send", combined_source)
        self.assertNotIn("owner_write_runtime", combined_source)
