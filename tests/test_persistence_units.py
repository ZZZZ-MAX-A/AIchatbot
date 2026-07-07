from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pure_ai_chat_loader import load_legacy_memory_modules, load_legacy_operation_modules


class TempDatabaseMixin:
    def temp_database(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(temp_dir.name) / "chatbot.db"
        patcher = patch.object(self.database, "DATABASE_PATH", db_path)
        return temp_dir, patcher


class DatabaseSchemaUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]

    def test_ensure_database_creates_expected_tables_and_schema_version(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            self.database.ensure_database()
            with self.database.connect() as connection:
                table_rows = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
                schema_row = connection.execute(
                    "SELECT value FROM schema_meta WHERE key = 'schema_version'"
                ).fetchone()

        table_names = {str(row["name"]) for row in table_rows}
        self.assertIn("messages", table_names)
        self.assertIn("long_term_memories", table_names)
        self.assertIn("session_summaries", table_names)
        self.assertIn("gap_scene_summaries", table_names)
        self.assertIn("rag_documents", table_names)
        self.assertIn("rag_embeddings", table_names)
        self.assertIn("private_trials", table_names)
        self.assertIn("agent_tasks", table_names)
        self.assertIn("agent_task_events", table_names)
        self.assertIn("agent_approvals", table_names)
        self.assertEqual(schema_row["value"], self.database.SCHEMA_VERSION)


class TrialPersistenceUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.operation_modules = load_legacy_operation_modules()
        cls.database = cls.memory_modules["database"]
        cls.trials = cls.operation_modules["trials"]

    def test_private_trial_counts_round_trip_in_temp_database(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            self.assertEqual(self.trials.private_trial_used("10001"), 0)
            self.assertTrue(self.trials.can_use_private_trial("10001", 2))

            self.trials.increment_private_trial("10001")
            self.trials.increment_private_trial("10001")
            self.trials.increment_private_trial("20002")

            self.assertEqual(self.trials.private_trial_used("10001"), 2)
            self.assertFalse(self.trials.can_use_private_trial("10001", 2))
            stats = self.trials.trial_stats()
        self.assertEqual(stats, {"trial_user_count": 2, "trial_message_count": 3})


class AgentTaskPersistenceUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.agent_tasks = cls.memory_modules["agent_tasks"]
        cls.owner_agent_runtime = cls.memory_modules["owner_agent_runtime"]
        cls.summaries = cls.memory_modules["summaries"]
        cls.manual_memory = cls.memory_modules["manual_memory"]

    def test_agent_tasks_round_trip_and_format_without_execution(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="整理 MainAgentGraph 下一步计划",
            )
            other_id = self.agent_tasks.create_agent_task(
                session_key="private:20002",
                user_id="20002",
                goal="other task",
            )

            task = self.agent_tasks.get_agent_task(task_id)
            tasks = self.agent_tasks.list_agent_tasks(
                session_key="private:10001",
                user_id="10001",
            )
            formatted_created = self.agent_tasks.format_agent_task_created(task)
            formatted_list = self.agent_tasks.format_agent_task_list(tasks)
            events = self.agent_tasks.list_agent_task_events(task_id)
            formatted_detail = self.agent_tasks.format_agent_task_detail(task, events)

        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task.id, task_id)
        self.assertEqual(task.status, self.agent_tasks.AGENT_TASK_PENDING)
        self.assertEqual(task.goal, "整理 MainAgentGraph 下一步计划")
        self.assertEqual([item.id for item in tasks], [task_id])
        self.assertNotIn(str(other_id), formatted_list)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "created")
        self.assertIn("启用审批恢复", formatted_created)
        self.assertIn("不执行任意 shell", formatted_list)
        self.assertIn("事件：", formatted_detail)
        self.assertIn("关联审批：", formatted_detail)
        self.assertIn("暂无关联审批", formatted_detail)

    def test_agent_task_detail_card_links_related_approval(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="删除摘要 41",
            )
            other_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="other task",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"delete_session_summary","summary_id":41}',
                risk_level="write_local",
                reason="主人要求删除当前会话摘要 41",
            )
            other_approval_id = self.agent_tasks.create_agent_approval(
                task_id=other_task_id,
                tool_name="dry_run_write_file",
                tool_input_json='{"dry_run": true}',
                risk_level="write_local",
                reason="other approval",
            )
            task = self.agent_tasks.get_agent_task(
                task_id,
                session_key="private:10001",
                user_id="10001",
            )
            events = self.agent_tasks.list_agent_task_events(task_id)
            approvals = self.agent_tasks.list_agent_approvals(
                session_key="private:10001",
                user_id="10001",
                task_id=task_id,
            )
            assert task is not None
            task_detail = self.agent_tasks.format_agent_task_detail(task, events, approvals)
            approval_detail = self.agent_tasks.format_agent_approval_detail(
                approvals[0],
                task=task,
                events=events,
            )

        self.assertEqual([approval.id for approval in approvals], [approval_id])
        self.assertNotIn(f"审批 #{other_approval_id}", task_detail)
        self.assertIn(f"Agent 任务详情卡 #{task_id}", task_detail)
        self.assertIn("关联审批：", task_detail)
        self.assertIn(f"审批 #{approval_id} [待审批]", task_detail)
        self.assertIn(f"/agent 审批详情 {approval_id}", task_detail)
        self.assertIn(f"/agent 确认 {approval_id}", task_detail)
        self.assertIn("approval_requested", task_detail)
        self.assertIn(f"Agent 审批详情卡 #{approval_id}", approval_detail)
        self.assertIn("关联任务：", approval_detail)
        self.assertIn(f"/agent 任务详情 {task_id}", approval_detail)
        self.assertIn("最近事件：approval_requested", approval_detail)
        self.assertIn(f"/agent 拒绝 {approval_id}", approval_detail)

    def test_agent_task_next_step_prioritizes_pending_approvals(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            empty_reply = self.agent_tasks.format_agent_task_next_step(
                session_key="private:10001",
                user_id="10001",
            )
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="整理协作台下一步",
            )
            pending_reply = self.agent_tasks.format_agent_task_next_step(
                session_key="private:10001",
                user_id="10001",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="dry_run_write_file",
                tool_input_json='{"dry_run": true}',
                risk_level="write_local",
                reason="测试待审批优先级",
            )
            approval_reply = self.agent_tasks.format_agent_task_next_step(
                session_key="private:10001",
                user_id="10001",
            )

        self.assertIn("当前没有任务或审批记录", empty_reply)
        self.assertIn("有待处理任务，但没有待审批项", pending_reply)
        self.assertIn(f"/agent 任务详情 {task_id}", pending_reply)
        self.assertIn("有待审批项需要主人确认或拒绝", approval_reply)
        self.assertIn(f"/agent 审批详情 {approval_id}", approval_reply)
        self.assertIn(f"审批 #{approval_id}", approval_reply)
        self.assertIn(f"任务 #{task_id}", approval_reply)
        self.assertIn("失败任务：", approval_reply)
        self.assertIn("可复盘/已完成：", approval_reply)
        self.assertIn("完整工作台：/agent 任务工作台", approval_reply)

    def test_agent_task_workbench_groups_read_model_sections(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            pending_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="等待主人确认的任务",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=pending_task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"select_persona","target":"aike"}',
                risk_level="write_local",
                reason="测试工作台待确认分区",
            )
            ordinary_pending_ids = [
                self.agent_tasks.create_agent_task(
                    session_key="private:10001",
                    user_id="10001",
                    goal=f"旧测试待处理任务 {index}",
                )
                for index in range(5)
            ]
            failed_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="失败任务",
            )
            done_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="完成任务",
            )
            cancelled_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="取消任务",
            )
            self.agent_tasks.cancel_agent_task(
                task_id=cancelled_task_id,
                session_key="private:10001",
                user_id="10001",
            )
            with self.database.connect() as connection:
                now = self.database.utc_now()
                connection.execute(
                    """
                    UPDATE agent_tasks
                    SET status = ?, result = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (self.agent_tasks.AGENT_TASK_FAILED, "失败：测试错误", now, failed_task_id),
                )
                connection.execute(
                    """
                    UPDATE agent_tasks
                    SET status = ?, result = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (self.agent_tasks.AGENT_TASK_DONE, "完成：测试结果", now, done_task_id),
                )
            workbench = self.agent_tasks.format_agent_task_workbench(
                session_key="private:10001",
                user_id="10001",
            )

        self.assertIn("Agent 任务工作台", workbench)
        self.assertIn("待主人确认：", workbench)
        self.assertIn("失败任务：", workbench)
        self.assertIn("待处理任务：", workbench)
        self.assertIn("可复盘/已完成：", workbench)
        self.assertIn(f"审批 #{approval_id} [待审批]", workbench)
        self.assertIn(f"任务 #{pending_task_id} [待处理]", workbench)
        self.assertIn(f"待审批：#{approval_id}", workbench)
        self.assertIn("普通待处理/积压：", workbench)
        self.assertNotIn(f"任务 #{ordinary_pending_ids[-1]} [待处理]", workbench)
        self.assertIn("5 项普通待处理任务已折叠", workbench)
        self.assertIn("不批量取消任务，只做只读降噪", workbench)
        self.assertIn(f"任务 #{failed_task_id} [失败]", workbench)
        self.assertIn(f"任务 #{done_task_id} [已完成]", workbench)
        self.assertIn(f"任务 #{cancelled_task_id} [已取消]", workbench)
        self.assertIn("只读保证", workbench)

    def test_owner_agent_runtime_uses_context_without_qq_event(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            context = self.owner_agent_runtime.OwnerAgentContext(
                session_key="private:10001",
                user_id="10001",
            )
            task_id = self.agent_tasks.create_agent_task(
                session_key=context.session_key,
                user_id=context.user_id,
                goal="验证 service 层任务详情",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="dry_run_write_file",
                tool_input_json='{"dry_run": true}',
                risk_level="write_local",
                reason="验证 service 层不依赖 QQ event",
            )
            workbench = self.owner_agent_runtime.run_owner_agent_task_command(
                context,
                "任务工作台",
                approval_resume_tool_registry_factory=lambda: None,
            )
            task_detail = self.owner_agent_runtime.format_owner_agent_task_read(
                context,
                "task_detail",
                "latest",
            )
            approval_detail = self.owner_agent_runtime.format_owner_agent_task_read(
                context,
                "approval_detail",
                "latest",
            )

        self.assertIn("Agent 任务工作台", workbench)
        self.assertIn(f"审批 #{approval_id} [待审批]", workbench)
        self.assertIn(f"Agent 任务详情卡 #{task_id}", task_detail)
        self.assertIn(f"/agent 审批详情 {approval_id}", task_detail)
        self.assertIn(f"Agent 审批详情卡 #{approval_id}", approval_detail)
        self.assertIn(f"/agent 任务详情 {task_id}", approval_detail)

    def test_agent_task_cancel_is_scoped_and_records_event(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="等待取消的任务",
            )
            missing_task, missing_changed = self.agent_tasks.cancel_agent_task(
                task_id=task_id,
                session_key="private:20002",
                user_id="20002",
            )
            task, changed = self.agent_tasks.cancel_agent_task(
                task_id=task_id,
                session_key="private:10001",
                user_id="10001",
            )
            again_task, again_changed = self.agent_tasks.cancel_agent_task(
                task_id=task_id,
                session_key="private:10001",
                user_id="10001",
            )
            events = self.agent_tasks.list_agent_task_events(task_id)
            formatted = self.agent_tasks.format_agent_task_cancelled(task, changed=changed)

        self.assertIsNone(missing_task)
        self.assertFalse(missing_changed)
        self.assertIsNotNone(task)
        assert task is not None
        self.assertTrue(changed)
        self.assertEqual(task.status, self.agent_tasks.AGENT_TASK_CANCELLED)
        self.assertIsNotNone(again_task)
        self.assertFalse(again_changed)
        self.assertEqual([event.kind for event in events], ["created", "cancelled"])
        self.assertIn("已取消 Agent 任务", formatted)

    def test_agent_approvals_are_scoped_and_read_only_formatted(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="需要审批的任务",
            )
            other_task_id = self.agent_tasks.create_agent_task(
                session_key="private:20002",
                user_id="20002",
                goal="other approval task",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="write_file",
                tool_input_json='{"path":"docs/example.md"}',
                risk_level="L3_WRITE_LOCAL",
                reason="需要写入文档",
            )
            other_approval_id = self.agent_tasks.create_agent_approval(
                task_id=other_task_id,
                tool_name="shell",
                tool_input_json='{"command":"dir"}',
                risk_level="L5_DANGEROUS",
                reason="other",
            )

            approval = self.agent_tasks.get_agent_approval(
                approval_id,
                session_key="private:10001",
                user_id="10001",
            )
            approvals = self.agent_tasks.list_agent_approvals(
                session_key="private:10001",
                user_id="10001",
            )
            missing = self.agent_tasks.get_agent_approval(
                approval_id,
                session_key="private:20002",
                user_id="20002",
            )
            assert approval is not None
            formatted_list = self.agent_tasks.format_agent_approval_list(approvals)
            formatted_detail = self.agent_tasks.format_agent_approval_detail(approval)
            formatted_requested = self.agent_tasks.format_agent_approval_requested(approval)
            events = self.agent_tasks.list_agent_task_events(task_id)
            requested_reply = self.agent_tasks.create_agent_approval_request_reply(
                task_id=task_id,
                session_key="private:10001",
                user_id="10001",
                tool_name="write_file",
                tool_input_json='{"path":"docs/another.md"}',
                risk_level="L3_WRITE_LOCAL",
                reason="需要再次写入文档",
            )
            events_after_reply = self.agent_tasks.list_agent_task_events(task_id)

        self.assertIsNotNone(approval)
        self.assertIsNone(missing)
        self.assertEqual(approval.status, self.agent_tasks.AGENT_APPROVAL_PENDING)
        self.assertEqual([item.id for item in approvals], [approval_id])
        self.assertNotIn(f"#{other_approval_id}", formatted_list)
        self.assertEqual([event.kind for event in events], ["created", "approval_requested"])
        self.assertEqual(events[-1].tool_name, "write_file")
        self.assertIn(f"审批 #{approval_id}", events[-1].output_summary)
        self.assertIn("待审批", formatted_detail)
        self.assertIn("启用审批恢复", formatted_detail)
        self.assertIn("Agent 请求审批", formatted_requested)
        self.assertIn(f"审批ID：#{approval_id}", formatted_requested)
        self.assertIn(f"任务ID：#{task_id}", formatted_requested)
        self.assertIn(f"/agent 确认 {approval_id}", formatted_requested)
        self.assertIn("/agent 确认 最新", formatted_requested)
        self.assertIn(f"/agent 拒绝 {approval_id}", formatted_requested)
        self.assertIn("Agent 请求审批", requested_reply)
        self.assertIn("docs/another.md", requested_reply)
        self.assertEqual(events_after_reply[-1].kind, "approval_requested")

    def test_agent_approval_decision_is_scoped_and_records_event(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="需要审批决定的任务",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="write_file",
                tool_input_json='{"path":"docs/example.md"}',
                risk_level="L3_WRITE_LOCAL",
                reason="需要写入文档",
            )

            missing, missing_changed = self.agent_tasks.decide_agent_approval(
                approval_id=approval_id,
                session_key="private:20002",
                user_id="20002",
                approved=True,
            )
            approval, changed = self.agent_tasks.decide_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                approved=True,
            )
            again, again_changed = self.agent_tasks.decide_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                approved=False,
            )
            events = self.agent_tasks.list_agent_task_events(task_id)
            assert approval is not None
            formatted = self.agent_tasks.format_agent_approval_decision(
                approval,
                changed=changed,
            )

        self.assertIsNone(missing)
        self.assertFalse(missing_changed)
        self.assertIsNotNone(approval)
        self.assertTrue(changed)
        self.assertEqual(approval.status, self.agent_tasks.AGENT_APPROVAL_APPROVED)
        self.assertTrue(approval.decided_at)
        self.assertIsNotNone(again)
        self.assertFalse(again_changed)
        self.assertEqual(
            [event.kind for event in events],
            ["created", "approval_requested", "approval_approved"],
        )
        self.assertEqual(events[-1].tool_name, "write_file")
        self.assertIn("启用审批恢复", events[-1].output_summary)
        self.assertIn("已确认 Agent 审批", formatted)

    def test_agent_approval_drill_creates_task_approval_and_requested_event(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            reply = self.agent_tasks.create_agent_approval_drill_reply(
                session_key="private:10001",
                user_id="10001",
                goal="整理版本日志 dry-run",
            )
            tasks = self.agent_tasks.list_agent_tasks(
                session_key="private:10001",
                user_id="10001",
            )
            approvals = self.agent_tasks.list_agent_approvals(
                session_key="private:10001",
                user_id="10001",
            )
            assert tasks
            events = self.agent_tasks.list_agent_task_events(tasks[0].id)

        self.assertEqual(len(tasks), 1)
        self.assertIn("审批演练", tasks[0].goal)
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0].tool_name, "dry_run_write_file")
        self.assertEqual(approvals[0].risk_level, "write_local")
        self.assertIn('"dry_run": true', approvals[0].tool_input_json)
        self.assertEqual([event.kind for event in events], ["created", "approval_requested"])
        self.assertIn("dry-run", reply)
        self.assertIn("任务ID：#", reply)
        self.assertIn("审批ID：#", reply)
        self.assertIn("审批详情 最新", reply)
        self.assertIn("/agent 确认", reply)
        self.assertIn("/agent 确认 最新", reply)
        self.assertIn("/agent 拒绝", reply)

    def test_agent_approval_dry_run_resume_executes_after_approval_once(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            self.agent_tasks.create_agent_approval_drill_reply(
                session_key="private:10001",
                user_id="10001",
                goal="append dry-run note",
            )
            approval = self.agent_tasks.list_agent_approvals(
                session_key="private:10001",
                user_id="10001",
            )[0]

            decided, changed = self.agent_tasks.decide_agent_approval(
                approval_id=approval.id,
                session_key="private:10001",
                user_id="10001",
                approved=True,
            )
            resumed_approval, resumed, resume_text = self.agent_tasks.resume_agent_approval_dry_run(
                approval_id=approval.id,
                session_key="private:10001",
                user_id="10001",
            )
            resumed_again, resumed_again_changed, resumed_again_text = (
                self.agent_tasks.resume_agent_approval_dry_run(
                    approval_id=approval.id,
                    session_key="private:10001",
                    user_id="10001",
                )
            )
            task = self.agent_tasks.get_agent_task(
                approval.task_id,
                session_key="private:10001",
                user_id="10001",
            )
            events = self.agent_tasks.list_agent_task_events(approval.task_id)

        self.assertIsNotNone(decided)
        self.assertTrue(changed)
        self.assertIsNotNone(resumed_approval)
        self.assertTrue(resumed)
        self.assertIn("Dry-run resume completed", resume_text)
        self.assertIn("side_effect: none", resume_text)
        self.assertIsNotNone(resumed_again)
        self.assertFalse(resumed_again_changed)
        self.assertIn("already completed", resumed_again_text)
        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task.status, self.agent_tasks.AGENT_TASK_DONE)
        self.assertIn("dry_run_write_file result", task.result)
        self.assertEqual(
            [event.kind for event in events],
            [
                "created",
                "approval_requested",
                "approval_approved",
                "tool_resume_started",
                "tool_resume_finished",
            ],
        )
        self.assertEqual(events[-1].tool_name, "dry_run_write_file")
        self.assertIn("side_effect: none", events[-1].output_summary)

    def test_agent_approval_dry_run_resume_skips_rejected_and_non_dry_run_tools(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            rejected_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="rejected dry run",
            )
            rejected_approval_id = self.agent_tasks.create_agent_approval(
                task_id=rejected_task_id,
                tool_name="dry_run_write_file",
                tool_input_json='{"path":"docs/version-runlog.md","content_summary":"skip"}',
                risk_level="write_local",
                reason="dry-run should be rejected",
            )
            write_task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="real write stays blocked",
            )
            write_approval_id = self.agent_tasks.create_agent_approval(
                task_id=write_task_id,
                tool_name="write_file",
                tool_input_json='{"path":"docs/version-runlog.md","content_summary":"blocked"}',
                risk_level="write_local",
                reason="unsupported real write",
            )

            self.agent_tasks.decide_agent_approval(
                approval_id=rejected_approval_id,
                session_key="private:10001",
                user_id="10001",
                approved=False,
            )
            rejected_approval, rejected_resumed, rejected_text = (
                self.agent_tasks.resume_agent_approval_dry_run(
                    approval_id=rejected_approval_id,
                    session_key="private:10001",
                    user_id="10001",
                )
            )
            self.agent_tasks.decide_agent_approval(
                approval_id=write_approval_id,
                session_key="private:10001",
                user_id="10001",
                approved=True,
            )
            write_approval, write_resumed, write_text = (
                self.agent_tasks.resume_agent_approval_dry_run(
                    approval_id=write_approval_id,
                    session_key="private:10001",
                    user_id="10001",
                )
            )
            rejected_events = self.agent_tasks.list_agent_task_events(rejected_task_id)
            write_events = self.agent_tasks.list_agent_task_events(write_task_id)

        self.assertIsNotNone(rejected_approval)
        self.assertFalse(rejected_resumed)
        self.assertIn("not approved", rejected_text)
        self.assertEqual(
            [event.kind for event in rejected_events],
            ["created", "approval_requested", "approval_rejected"],
        )
        self.assertIsNotNone(write_approval)
        self.assertFalse(write_resumed)
        self.assertIn("not registered", write_text)
        self.assertEqual(
            [event.kind for event in write_events],
            ["created", "approval_requested", "approval_approved"],
        )

    def test_agent_approval_resume_requires_registry_resume_flag(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="registered but disabled resume",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="dry_run_write_file",
                tool_input_json='{"path":"docs/version-runlog.md","content_summary":"blocked"}',
                risk_level="write_local",
                reason="registered dry run with disabled resume flag",
            )
            self.agent_tasks.decide_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                approved=True,
            )
            base_spec = self.agent_tasks.create_default_main_agent_tool_registry(
                include_dry_run_tools=True
            ).require("dry_run_write_file")
            registry = self.agent_tasks.ToolRegistry(
                [
                    type(base_spec)(
                        name=base_spec.name,
                        description=base_spec.description,
                        risk_level=base_spec.risk_level,
                        required_arguments=base_spec.required_arguments,
                        optional_arguments=base_spec.optional_arguments,
                        executor=base_spec.executor,
                        enabled=base_spec.enabled,
                        llm_visible=base_spec.llm_visible,
                        requires_approval=base_spec.requires_approval,
                        approval_resume_enabled=False,
                    )
                ]
            )

            approval, resumed, resume_text = self.agent_tasks.resume_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                tool_registry=registry,
            )
            events = self.agent_tasks.list_agent_task_events(task_id)

        self.assertIsNotNone(approval)
        self.assertFalse(resumed)
        self.assertIn("not enabled for approval resume", resume_text)
        self.assertEqual(
            [event.kind for event in events],
            ["created", "approval_requested", "approval_approved"],
        )

    def test_agent_approval_resume_executes_registered_owner_write_tool(self):
        temp_dir, patcher = self.temp_database()
        calls = []
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="clear image cache after approval",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"clear_image_cache"}',
                risk_level="write_local",
                reason="local writes require approval",
            )
            self.agent_tasks.decide_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                approved=True,
            )
            base_spec = self.agent_tasks.create_default_main_agent_tool_registry(
                include_dry_run_tools=True
            ).require("dry_run_write_file")

            def execute_owner_write(arguments, context):
                calls.append(
                    (
                        arguments["command"],
                        context.metadata["approval_id"],
                        context.metadata["task_id"],
                        context.metadata["resume_mode"],
                        context.metadata["resume_tool_name"],
                    )
                )
                return self.agent_tasks.ToolResult(
                    text="已清空图片缓存：3 条。",
                    metadata={"command": arguments["command"]},
                )

            registry = self.agent_tasks.ToolRegistry(
                [
                    type(base_spec)(
                        name="owner_write_command",
                        description="Run approved owner write command.",
                        risk_level=base_spec.risk_level,
                        required_arguments=("command",),
                        executor=execute_owner_write,
                        enabled=True,
                        llm_visible=True,
                        requires_approval=True,
                        approval_resume_enabled=True,
                    )
                ]
            )

            approval, resumed, resume_text = self.agent_tasks.resume_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                tool_registry=registry,
            )
            task = self.agent_tasks.get_agent_task(task_id)
            events = self.agent_tasks.list_agent_task_events(task_id)

        self.assertIsNotNone(approval)
        self.assertTrue(resumed)
        self.assertEqual(
            calls,
            [
                (
                    "clear_image_cache",
                    approval_id,
                    task_id,
                    "approval_resume",
                    "owner_write_command",
                )
            ],
        )
        self.assertIn("Approval resume completed", resume_text)
        self.assertIn("已清空图片缓存：3 条。", resume_text)
        self.assertNotIn("Side effect: none", resume_text)
        self.assertIsNotNone(task)
        self.assertEqual(task.status, self.agent_tasks.AGENT_TASK_DONE)
        self.assertEqual(
            [event.kind for event in events],
            [
                "created",
                "approval_requested",
                "approval_approved",
                "tool_resume_started",
                "tool_resume_finished",
            ],
        )

    def test_agent_approval_resume_owner_write_delete_summary_keeps_summary_id(self):
        temp_dir, patcher = self.temp_database()
        calls = []
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="delete one summary after approval",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"delete_session_summary","summary_id":"123"}',
                risk_level="write_local",
                reason="local writes require approval",
            )
            self.agent_tasks.decide_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                approved=True,
            )
            base_spec = self.agent_tasks.create_default_main_agent_tool_registry(
                include_dry_run_tools=True
            ).require("dry_run_write_file")

            def execute_owner_write(arguments, context):
                calls.append(
                    (
                        arguments["command"],
                        arguments["summary_id"],
                        context.metadata["session_key"],
                        context.metadata["user_id"],
                    )
                )
                return self.agent_tasks.ToolResult(
                    text="已删除当前会话摘要：ID 123。",
                    metadata={"command": arguments["command"], "summary_id": arguments["summary_id"]},
                )

            registry = self.agent_tasks.ToolRegistry(
                [
                    type(base_spec)(
                        name="owner_write_command",
                        description="Run approved owner write command.",
                        risk_level=base_spec.risk_level,
                        required_arguments=("command",),
                        optional_arguments=("summary_id",),
                        executor=execute_owner_write,
                        enabled=True,
                        llm_visible=True,
                        requires_approval=True,
                        approval_resume_enabled=True,
                    )
                ]
            )

            approval, resumed, resume_text = self.agent_tasks.resume_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                tool_registry=registry,
            )
            events = self.agent_tasks.list_agent_task_events(task_id)

        self.assertIsNotNone(approval)
        self.assertTrue(resumed)
        self.assertEqual(
            calls,
            [("delete_session_summary", "123", "private:10001", "10001")],
        )
        self.assertIn("执行结果", resume_text)
        self.assertIn("已删除当前会话摘要：ID 123。", resume_text)
        self.assertEqual(
            [event.kind for event in events],
            [
                "created",
                "approval_requested",
                "approval_approved",
                "tool_resume_started",
                "tool_resume_finished",
            ],
        )

    def test_agent_approval_resume_executes_summary_delete_without_database_lock(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            summary_id = self.summaries.add_summary(
                session_key="private:10001",
                message_type="private",
                user_id="10001",
                group_id=None,
                summary="summary to delete",
                message_start_id=1,
                message_end_id=2,
                source_message_count=2,
            )
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="delete summary after approval",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="owner_write_command",
                tool_input_json=f'{{"command":"delete_session_summary","summary_id":"{summary_id}"}}',
                risk_level="write_local",
                reason="local writes require approval",
            )
            self.agent_tasks.decide_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                approved=True,
            )
            base_spec = self.agent_tasks.create_default_main_agent_tool_registry(
                include_dry_run_tools=True
            ).require("dry_run_write_file")

            def execute_owner_write(arguments, context):
                deleted = self.summaries.delete_session_summary(
                    str(context.metadata["session_key"]),
                    int(arguments["summary_id"]),
                )
                text = (
                    f"已删除当前会话摘要：ID {arguments['summary_id']}。"
                    if deleted
                    else f"没有找到当前会话摘要：{arguments['summary_id']}"
                )
                return self.agent_tasks.ToolResult(
                    text=text,
                    metadata={
                        "command": arguments["command"],
                        "summary_id": arguments["summary_id"],
                        "deleted": deleted,
                    },
                )

            registry = self.agent_tasks.ToolRegistry(
                [
                    type(base_spec)(
                        name="owner_write_command",
                        description="Run approved owner write command.",
                        risk_level=base_spec.risk_level,
                        required_arguments=("command",),
                        optional_arguments=("summary_id",),
                        executor=execute_owner_write,
                        enabled=True,
                        llm_visible=True,
                        requires_approval=True,
                        approval_resume_enabled=True,
                    )
                ]
            )

            approval, resumed, resume_text = self.agent_tasks.resume_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                tool_registry=registry,
            )
            remaining = self.summaries.recent_summaries("private:10001", 5)
            task = self.agent_tasks.get_agent_task(task_id)
            events = self.agent_tasks.list_agent_task_events(task_id)

        self.assertIsNotNone(approval)
        self.assertTrue(resumed)
        self.assertIn(f"已删除当前会话摘要：ID {summary_id}。", resume_text)
        self.assertEqual(remaining, [])
        self.assertIsNotNone(task)
        self.assertEqual(task.status, self.agent_tasks.AGENT_TASK_DONE)
        self.assertEqual(
            [event.kind for event in events],
            [
                "created",
                "approval_requested",
                "approval_approved",
                "tool_resume_started",
                "tool_resume_finished",
            ],
        )

    def test_agent_approval_resume_executes_manual_memory_write_without_database_lock(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            task_id = self.agent_tasks.create_agent_task(
                session_key="private:10001",
                user_id="10001",
                goal="add fact memory after approval",
            )
            approval_id = self.agent_tasks.create_agent_approval(
                task_id=task_id,
                tool_name="owner_write_command",
                tool_input_json='{"command":"add_fact_memory","content":"主人喜欢先看结论"}',
                risk_level="write_local",
                reason="local writes require approval",
            )
            self.agent_tasks.decide_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                approved=True,
            )
            base_spec = self.agent_tasks.create_default_main_agent_tool_registry(
                include_dry_run_tools=True
            ).require("dry_run_write_file")

            def execute_owner_write(arguments, context):
                memory_id = self.manual_memory.add_manual_memory(
                    subject_type="user",
                    subject_id=str(context.metadata["user_id"]),
                    content=str(arguments["content"]),
                    memory_type=self.manual_memory.MANUAL_FACT_TYPE,
                    source_session_key=str(context.metadata["session_key"]),
                )
                return self.agent_tasks.ToolResult(
                    text=f"已添加事实摘要记忆：ID {memory_id}。",
                    metadata={"command": arguments["command"], "memory_id": memory_id},
                )

            registry = self.agent_tasks.ToolRegistry(
                [
                    type(base_spec)(
                        name="owner_write_command",
                        description="Run approved owner write command.",
                        risk_level=base_spec.risk_level,
                        required_arguments=("command",),
                        optional_arguments=("content",),
                        executor=execute_owner_write,
                        enabled=True,
                        llm_visible=True,
                        requires_approval=True,
                        approval_resume_enabled=True,
                    )
                ]
            )

            approval, resumed, resume_text = self.agent_tasks.resume_agent_approval(
                approval_id=approval_id,
                session_key="private:10001",
                user_id="10001",
                tool_registry=registry,
            )
            memories = self.manual_memory.list_manual_memories("user", "10001", limit=5)
            task = self.agent_tasks.get_agent_task(task_id)
            events = self.agent_tasks.list_agent_task_events(task_id)

        self.assertIsNotNone(approval)
        self.assertTrue(resumed)
        self.assertIn("已添加事实摘要记忆：ID", resume_text)
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0].content, "主人喜欢先看结论")
        self.assertIsNotNone(task)
        self.assertEqual(task.status, self.agent_tasks.AGENT_TASK_DONE)
        self.assertEqual(
            [event.kind for event in events],
            [
                "created",
                "approval_requested",
                "approval_approved",
                "tool_resume_started",
                "tool_resume_finished",
            ],
        )

    def test_agent_task_command_parser(self):
        parse = self.agent_tasks.parse_agent_task_command

        self.assertEqual(
            parse("任务 整理 MainAgentGraph 下一步计划"),
            (self.agent_tasks.AGENT_TASK_COMMAND_CREATE, "整理 MainAgentGraph 下一步计划"),
        )
        self.assertEqual(parse("任务状态"), (self.agent_tasks.AGENT_TASK_COMMAND_STATUS, ""))
        self.assertEqual(parse("task status"), (self.agent_tasks.AGENT_TASK_COMMAND_STATUS, ""))
        self.assertEqual(parse("下一步"), (self.agent_tasks.AGENT_TASK_COMMAND_NEXT_STEP, ""))
        self.assertEqual(parse("现在卡在哪"), (self.agent_tasks.AGENT_TASK_COMMAND_NEXT_STEP, ""))
        self.assertEqual(parse("任务工作台"), (self.agent_tasks.AGENT_TASK_COMMAND_WORKBENCH, ""))
        self.assertEqual(parse("任务看板"), (self.agent_tasks.AGENT_TASK_COMMAND_WORKBENCH, ""))
        self.assertEqual(parse("审批状态"), (self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_STATUS, ""))
        self.assertEqual(parse("审批演练"), (self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_DRILL, ""))
        self.assertEqual(
            parse("审批演练 写入版本日志"),
            (self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_DRILL, "写入版本日志"),
        )
        self.assertEqual(
            parse("approval drill write version log"),
            (self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_DRILL, "write version log"),
        )
        self.assertEqual(parse("审批详情 #7"), (self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_DETAIL, "#7"))
        self.assertEqual(parse("审批详情"), (self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_DETAIL, ""))
        self.assertEqual(parse("确认 7"), (self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_APPROVE, "7"))
        self.assertEqual(parse("确认审批 #7"), (self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_APPROVE, "#7"))
        self.assertEqual(
            parse("同意"),
            (
                self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_APPROVE,
                self.agent_tasks.AGENT_APPROVAL_IMPLICIT_LATEST,
            ),
        )
        self.assertEqual(parse("拒绝 7"), (self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_REJECT, "7"))
        self.assertEqual(parse("reject approval #7"), (self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_REJECT, "#7"))
        self.assertEqual(
            parse("不同意"),
            (
                self.agent_tasks.AGENT_TASK_COMMAND_APPROVAL_REJECT,
                self.agent_tasks.AGENT_APPROVAL_IMPLICIT_LATEST,
            ),
        )
        self.assertEqual(parse("任务详情 #12"), (self.agent_tasks.AGENT_TASK_COMMAND_DETAIL, "#12"))
        self.assertEqual(parse("任务详情"), (self.agent_tasks.AGENT_TASK_COMMAND_DETAIL, ""))
        self.assertEqual(parse("取消任务 12"), (self.agent_tasks.AGENT_TASK_COMMAND_CANCEL, "12"))
        self.assertEqual(parse("取消任务"), (self.agent_tasks.AGENT_TASK_COMMAND_CANCEL, ""))
        self.assertEqual(
            parse("新增任务：整理审批流"),
            (self.agent_tasks.AGENT_TASK_COMMAND_CREATE, "整理审批流"),
        )
        self.assertEqual(
            parse("帮我记一个任务：整理 Route B 审批流"),
            (self.agent_tasks.AGENT_TASK_COMMAND_CREATE, "整理 Route B 审批流"),
        )
        self.assertEqual(
            parse("把“整理审批流”加入任务"),
            (self.agent_tasks.AGENT_TASK_COMMAND_CREATE, "整理审批流"),
        )
        self.assertEqual(
            parse("把 Route B 的执行器先放进待办"),
            (self.agent_tasks.AGENT_TASK_COMMAND_CREATE, "Route B 的执行器"),
        )
        self.assertEqual(self.agent_tasks.parse_agent_task_id("#12"), 12)
        self.assertIsNone(self.agent_tasks.parse_agent_task_id("abc"))
        self.assertTrue(self.agent_tasks.is_latest_agent_reference("最新"))
        self.assertTrue(self.agent_tasks.is_latest_agent_reference("latest"))
        self.assertTrue(
            self.agent_tasks.is_implicit_latest_agent_reference(
                self.agent_tasks.AGENT_APPROVAL_IMPLICIT_LATEST
            )
        )
        self.assertFalse(self.agent_tasks.is_latest_agent_reference("审批最新"))
        self.assertEqual(parse("任务"), (self.agent_tasks.AGENT_TASK_COMMAND_CREATE, ""))
        self.assertIsNone(parse("后面是不是该整理任务系统？"))
        self.assertIsNone(parse("后面记得做一下审批流"))
        self.assertIsNone(parse("查 MainAgentGraph 当前状态"))


class SummaryPersistenceUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.summaries = cls.memory_modules["summaries"]

    def add_summary(self, session_key: str, text: str, count: int = 2) -> int:
        return self.summaries.add_summary(
            session_key=session_key,
            message_type="private",
            user_id="10001",
            group_id=None,
            summary=text,
            message_start_id=1,
            message_end_id=count,
            source_message_count=count,
        )

    def test_session_summaries_round_trip_stats_delete_and_clear(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            first_id = self.add_summary("private:10001", "first", 2)
            second_id = self.add_summary("private:10001", "second", 3)
            self.add_summary("private:20002", "other", 4)

            recent = self.summaries.recent_summaries("private:10001", 2)
            scoped_stats = self.summaries.summary_stats("private:10001")
            all_stats = self.summaries.summary_stats()
            deleted = self.summaries.delete_session_summary("private:10001", first_id)
            missing_deleted = self.summaries.delete_session_summary("private:10001", first_id)
            remaining_after_delete = self.summaries.recent_summaries("private:10001", 5)
            cleared = self.summaries.clear_session_summaries("private:10001")
            all_cleared = self.summaries.clear_all_summaries()

        self.assertEqual([summary.summary for summary in recent], ["first", "second"])
        self.assertEqual(recent[0].id, first_id)
        self.assertEqual(recent[1].id, second_id)
        self.assertEqual(scoped_stats, {"summary_count": 2, "summarized_message_count": 5})
        self.assertEqual(all_stats, {"summary_count": 3, "summarized_message_count": 9})
        self.assertTrue(deleted)
        self.assertFalse(missing_deleted)
        self.assertEqual([summary.summary for summary in remaining_after_delete], ["second"])
        self.assertEqual(cleared, 1)
        self.assertEqual(all_cleared, 1)


class ManualMemoryPersistenceUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.manual_memory = cls.memory_modules["manual_memory"]

    def test_manual_memories_round_trip_filters_stats_and_delete(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            fact_id = self.manual_memory.add_manual_memory(
                "private",
                "10001",
                "fact memory",
                memory_type="fact",
                source_session_key="private:10001",
                confidence=0.8,
            )
            preference_id = self.manual_memory.add_manual_memory(
                "private",
                "10001",
                "preference memory",
                memory_type="preferences",
            )
            self.manual_memory.add_manual_memory("group", "42", "group memory")

            private_memories = self.manual_memory.list_manual_memories("private", "10001", limit=10)
            fact_only = [memory for memory in private_memories if memory.id == fact_id][0]
            stats = self.manual_memory.manual_memory_stats()
            deleted = self.manual_memory.delete_manual_memory(preference_id)
            missing_deleted = self.manual_memory.delete_manual_memory(preference_id)
            remaining = self.manual_memory.list_manual_memories("private", "10001", limit=10)

        self.assertEqual([memory.content for memory in private_memories], ["preference memory", "fact memory"])
        self.assertEqual(fact_only.memory_type, self.manual_memory.MANUAL_FACT_TYPE)
        self.assertEqual(fact_only.confidence, 0.8)
        self.assertEqual(stats, {"memory_count": 3, "subject_count": 2})
        self.assertTrue(deleted)
        self.assertFalse(missing_deleted)
        self.assertEqual([memory.content for memory in remaining], ["fact memory"])


class MessageHistoryPersistenceUnitTests(TempDatabaseMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.memory_modules = load_legacy_memory_modules()
        cls.database = cls.memory_modules["database"]
        cls.memory = cls.memory_modules["memory"]

    def test_messages_append_build_history_count_stats_and_clear(self):
        temp_dir, patcher = self.temp_database()
        with temp_dir, patcher:
            self.memory.append_message("private:10001", "user", " first ", "private", "10001")
            self.memory.append_message("private:10001", "assistant", "second", "private", "10001")
            self.memory.append_message("private:10001", "user", "third", "private", "10001")
            self.memory.append_message("private:20002", "user", "other", "private", "20002")

            history = self.memory.build_history(
                "private:10001",
                max_messages=2,
                system_contexts=["system context"],
            )
            count = self.memory.session_message_count("private:10001")
            stats = self.memory.memory_stats()
            self.memory.clear_session("private:10001")
            count_after_clear = self.memory.session_message_count("private:10001")
            self.memory.clear_all_sessions()
            stats_after_clear_all = self.memory.memory_stats()

        self.assertEqual(
            history,
            [
                {"role": "system", "content": "system context"},
                {"role": "assistant", "content": "second"},
                {"role": "user", "content": "third"},
            ],
        )
        self.assertEqual(count, 3)
        self.assertEqual(stats["message_count"], 4)
        self.assertEqual(stats["session_count"], 2)
        self.assertEqual(count_after_clear, 0)
        self.assertEqual(stats_after_clear_all["message_count"], 0)
        self.assertEqual(stats_after_clear_all["session_count"], 0)


if __name__ == "__main__":
    unittest.main()
