from __future__ import annotations

import asyncio
import types
import unittest

from pure_ai_chat_loader import load_pure_graph_modules


class MainAgentReadOnlyBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.main_agent = cls.modules["main_agent"]
        cls.main_agent_bridge = cls.modules["main_agent_bridge"]
        cls.owner_read_runtime = cls.modules["owner_read_runtime"]
        cls.owner_write_runtime = cls.modules["owner_write_runtime"]
        cls.owner_runtime_factory = cls.modules["owner_runtime_factory"]
        cls.policy_risk = cls.modules["policy_risk"]
        cls.tool_registry = cls.modules["tool_registry"]

    def test_owner_runtime_factory_assembles_services_without_qq_event(self):
        event = {"session_key": "private:10001", "user_id": "10001"}
        access = types.SimpleNamespace(
            group_whitelist=["123456"],
            private_whitelist=["10001"],
            user_blacklist=[],
        )

        async def run_diagnostics_graph(_event, view=None):
            return types.SimpleNamespace(
                result=types.SimpleNamespace(
                    reply_text=f"diagnostics:{view}",
                    error="",
                )
            )

        async def run_memory_retrieval_graph(_event, action, query=""):
            return types.SimpleNamespace(
                result=types.SimpleNamespace(
                    reply_text=f"retrieval:{action}:{query}",
                    error="",
                )
            )

        async def run_memory_admin_graph(_event, action):
            return types.SimpleNamespace(
                result=types.SimpleNamespace(
                    reply_text=f"admin:{action}",
                    error="",
                )
            )

        factory = self.owner_runtime_factory.OwnerRuntimeFactory(
            session_key_from_event=lambda item: item["session_key"],
            user_id_from_event=lambda item: item["user_id"],
            bot_status_lines=lambda: ["Bot 状态", "OK"],
            ops_health_reply_for_event=lambda _event: "聚合诊断",
            vision_troubleshoot_reply_for_event=lambda _event: "图片识别排查",
            memory_rag_troubleshoot_reply_for_event=lambda _event: "记忆检索排查",
            run_diagnostics_graph=run_diagnostics_graph,
            run_memory_retrieval_graph=run_memory_retrieval_graph,
            run_memory_admin_graph=run_memory_admin_graph,
            load_persona_prompt=lambda: "persona body",
            persona_status_lines=lambda: ["角色卡状态"],
            role_card_list_lines=lambda: ["角色卡列表"],
            model_config_status_lines=lambda: ["模型配置"],
            access_overview_lines=lambda: ["访问控制"],
            rag_index_detail_lines=lambda: ["RAG 索引"],
            main_agent_observation_lines=lambda: ["MainAgent 观测"],
            root_graph_observation_lines=lambda: ["RootGraph 观测"],
            current_access=lambda: access,
            list_lines=lambda label, values: f"{label}:{','.join(values)}",
            clear_image_cache=lambda: 1,
            clear_error_log=lambda: "已清空错误日志。",
            add_access_item=lambda _list_name, _target: True,
            remove_access_item=lambda _list_name, _target: True,
            select_role_card=lambda _target: types.SimpleNamespace(
                key="moyan",
                title="角色卡：莫言",
            ),
            add_manual_memory=lambda **_kwargs: 47,
            subject_label=lambda subject_type, subject_id: f"{subject_type}:{subject_id}",
            clear_session_summaries=lambda _session_key: 3,
            delete_session_summary=lambda _session_key, _summary_id: True,
            owner_user_id_default="10001",
            fact_memory_type="fact_summary",
            preference_memory_type="preference_summary",
            development_context_report_for_event=lambda _event, _query: (
                "project docs: 0\nmemories: 0"
            ),
            system_diagnostics_report_for_event=lambda _event, _scope: (
                "system diagnostics overview"
            ),
        )
        context = self.tool_registry.ToolContext(
            metadata={
                "session_key": "private:10001",
                "user_id": "10001",
                "tool_arguments": {"command": "clear_image_cache"},
            }
        )

        owner_context = factory.agent_context(event)
        self.assertEqual(owner_context.session_key, "private:10001")
        self.assertEqual(owner_context.user_id, "10001")
        work_runtime = factory.work_runtime(event)
        self.assertEqual(
            work_runtime.registered_work_types,
            ("development_context_report", "system_diagnostics_report"),
        )
        self.assertEqual(
            work_runtime.work_spec("development_context_report").executor("factory query"),
            "project docs: 0\nmemories: 0",
        )
        self.assertEqual(
            work_runtime.work_spec("system_diagnostics_report").executor("overview"),
            "system diagnostics overview",
        )
        self.assertEqual(
            asyncio.run(factory.run_read_command(event, "bot_status", context)),
            "Bot 状态\nOK",
        )
        self.assertEqual(
            asyncio.run(factory.run_read_command(event, "group_whitelist", context)),
            "群白名单:123456",
        )
        self.assertEqual(
            factory.run_write_command("clear_image_cache", context),
            "已清空图片缓存：1 条。",
        )

    def test_owner_read_runtime_dispatches_without_qq_event(self):
        calls = []

        def execution(text, error=""):
            return types.SimpleNamespace(
                result=types.SimpleNamespace(reply_text=text, error=error)
            )

        async def run_diagnostics(view):
            calls.append(("diagnostics", view))
            return execution(f"diagnostics:{view}")

        async def run_memory_retrieval(action, query=""):
            calls.append(("retrieval", action, query))
            return execution(f"retrieval:{action}:{query}")

        async def run_memory_admin(action):
            calls.append(("admin", action))
            return execution(f"admin:{action}")

        runtime = self.owner_read_runtime.OwnerReadRuntime(
            bot_status_lines=lambda: ["Bot 状态", "OK"],
            ops_health_reply=lambda: "聚合诊断",
            vision_troubleshoot_reply=lambda: "图片识别排查",
            memory_rag_troubleshoot_reply=lambda: "记忆检索排查",
            run_diagnostics=run_diagnostics,
            run_memory_retrieval=run_memory_retrieval,
            run_memory_admin=run_memory_admin,
            load_persona_prompt=lambda: "persona body",
            persona_status_lines=lambda: ["角色卡状态"],
            role_card_list_lines=lambda: ["角色卡列表"],
            model_config_status_lines=lambda: ["模型配置"],
            access_overview_lines=lambda: ["访问控制"],
            rag_index_detail_lines=lambda: ["RAG 索引"],
            main_agent_observation_lines=lambda: ["MainAgent 观测"],
            root_graph_observation_lines=lambda: ["RootGraph 观测"],
            group_whitelist_reply=lambda: "群白名单",
            private_whitelist_reply=lambda: "私聊白名单",
            blacklist_reply=lambda: "黑名单",
        )
        context = self.tool_registry.ToolContext(
            metadata={"tool_arguments": {"query": "Route B 审批流"}}
        )

        self.assertEqual(
            asyncio.run(
                self.owner_read_runtime.run_owner_read_command(
                    runtime,
                    "bot_status",
                    context,
                )
            ),
            "Bot 状态\nOK",
        )
        self.assertEqual(
            asyncio.run(
                self.owner_read_runtime.run_owner_read_command(
                    runtime,
                    "ops_health",
                    context,
                )
            ),
            "聚合诊断",
        )
        self.assertEqual(
            asyncio.run(
                self.owner_read_runtime.run_owner_read_command(
                    runtime,
                    "config_status",
                    context,
                )
            ),
            f"diagnostics:{self.modules['diagnostics'].DiagnosticsView.CONFIG}",
        )
        self.assertEqual(
            asyncio.run(
                self.owner_read_runtime.run_owner_read_command(
                    runtime,
                    "memory_retrieval",
                    context,
                )
            ),
            f"retrieval:{self.modules['retrieval'].MemoryRetrievalAction.QUERY}:Route B 审批流",
        )
        self.assertEqual(
            asyncio.run(
                self.owner_read_runtime.run_owner_read_command(
                    runtime,
                    "summary_status",
                    context,
                )
            ),
            f"admin:{self.modules['memory'].MemoryAdminAction.SUMMARY_STATUS}",
        )
        self.assertEqual(
            asyncio.run(
                self.owner_read_runtime.run_owner_read_command(
                    runtime,
                    "view_persona",
                    context,
                )
            ),
            "当前角色卡内容：\npersona body",
        )
        self.assertEqual(
            calls,
            [
                ("diagnostics", self.modules["diagnostics"].DiagnosticsView.CONFIG),
                (
                    "retrieval",
                    self.modules["retrieval"].MemoryRetrievalAction.QUERY,
                    "Route B 审批流",
                ),
                ("admin", self.modules["memory"].MemoryAdminAction.SUMMARY_STATUS),
            ],
        )

        with self.assertRaises(RuntimeError):
            asyncio.run(
                self.owner_read_runtime.run_owner_read_command(
                    runtime,
                    "unsupported",
                    context,
                )
            )

    def test_owner_write_runtime_dispatches_without_qq_event(self):
        calls = []
        access_values = set()
        summaries = {("private:10001", 41)}
        card = types.SimpleNamespace(key="moyan", title="角色卡：莫言")

        def add_access_item(list_name, target):
            calls.append(("add_access", list_name, target))
            key = (list_name, target)
            changed = key not in access_values
            access_values.add(key)
            return changed

        def remove_access_item(list_name, target):
            calls.append(("remove_access", list_name, target))
            key = (list_name, target)
            changed = key in access_values
            access_values.discard(key)
            return changed

        def add_manual_memory(**kwargs):
            calls.append(("add_memory", kwargs))
            return 47

        def clear_session_summaries(session_key):
            calls.append(("clear_summaries", session_key))
            return 3

        def delete_session_summary(session_key, summary_id):
            calls.append(("delete_summary", session_key, summary_id))
            key = (session_key, summary_id)
            deleted = key in summaries
            summaries.discard(key)
            return deleted

        runtime = self.owner_write_runtime.OwnerWriteRuntime(
            clear_image_cache=lambda: 2,
            clear_error_log=lambda: "已清空错误日志。",
            add_access_item=add_access_item,
            remove_access_item=remove_access_item,
            select_role_card=lambda target: card if target == "moyan" else None,
            add_manual_memory=add_manual_memory,
            subject_label=lambda subject_type, subject_id: f"{subject_type}:{subject_id}",
            clear_session_summaries=clear_session_summaries,
            delete_session_summary=delete_session_summary,
            owner_user_id_default="owner-default",
            fact_memory_type="fact_summary",
            preference_memory_type="preference_summary",
        )

        def context(arguments, **metadata):
            data = {
                "tool_arguments": arguments,
                "session_key": "private:10001",
                "user_id": "10001",
            }
            data.update(metadata)
            return self.tool_registry.ToolContext(metadata=data)

        self.assertEqual(
            self.owner_write_runtime.run_owner_write_command(
                runtime,
                "clear_image_cache",
                context({"command": "clear_image_cache"}),
            ),
            "已清空图片缓存：2 条。",
        )
        self.assertEqual(
            self.owner_write_runtime.run_owner_write_command(
                runtime,
                "allow_group",
                context({"command": "allow_group", "target": "123456"}),
            ),
            "已加入群白名单：123456",
        )
        self.assertEqual(
            self.owner_write_runtime.run_owner_write_command(
                runtime,
                "select_persona",
                context({"command": "select_persona", "target": "moyan"}),
            ),
            "已选择角色卡：moyan，角色卡：莫言",
        )
        self.assertEqual(
            self.owner_write_runtime.run_owner_write_command(
                runtime,
                "add_fact_memory",
                context({"command": "add_fact_memory", "content": "主人喜欢先看结论"}),
            ),
            "已添加事实摘要记忆：ID 47，对象：user:10001。",
        )
        self.assertEqual(
            self.owner_write_runtime.run_owner_write_command(
                runtime,
                "clear_session_summaries",
                context({"command": "clear_session_summaries"}),
            ),
            "已清空当前会话摘要：3 条。",
        )
        self.assertEqual(
            self.owner_write_runtime.run_owner_write_command(
                runtime,
                "delete_session_summary",
                context({"command": "delete_session_summary", "summary_id": "41"}),
            ),
            "已删除当前会话摘要：ID 41。",
        )
        self.assertEqual(
            self.owner_write_runtime.run_owner_write_command(
                runtime,
                "delete_session_summary",
                context({"command": "delete_session_summary", "summary_id": "41"}),
            ),
            "没有找到当前会话摘要：41",
        )
        self.assertEqual(
            calls,
            [
                ("add_access", "group_whitelist", "123456"),
                (
                    "add_memory",
                    {
                        "subject_type": "user",
                        "subject_id": "10001",
                        "content": "主人喜欢先看结论",
                        "memory_type": "fact_summary",
                        "source_session_key": "private:10001",
                    },
                ),
                ("clear_summaries", "private:10001"),
                ("delete_summary", "private:10001", 41),
                ("delete_summary", "private:10001", 41),
            ],
        )

        with self.assertRaises(RuntimeError):
            self.owner_write_runtime.run_owner_write_command(
                runtime,
                "allow_group",
                context({"command": "allow_group", "target": "not-a-number"}),
            )

    def test_read_only_runner_executes_dev_context_for_owner_private_chat(self):
        calls = []

        async def retrieve_dev_context(query, is_owner):
            calls.append((query, is_owner))
            return "DevContextGraph result"

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context
        )
        state = self.main_agent.MainAgentState(
            query="recover project context",
            is_owner=True,
            is_group=False,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.node_trace, self.main_agent.MAIN_AGENT_NODE_SEQUENCE)
        self.assertEqual(calls, [("recover project context", True)])
        self.assertEqual(execution.result.error, "")
        self.assertEqual(execution.result.action, self.main_agent.MainAgentAction.TOOL_REQUEST.value)
        self.assertEqual(
            execution.result.requested_tool,
            self.main_agent.MainAgentToolName.DEV_CONTEXT.value,
        )
        self.assertEqual(execution.result.policy_decision, "allow")
        self.assertEqual(execution.result.tool_result, "DevContextGraph result")
        self.assertIn("MainAgentGraph read-only tool result", execution.result.response_text)

    def test_read_only_runner_can_render_concise_dev_context_summary(self):
        async def retrieve_dev_context(_query, _is_owner):
            return "\n".join(
                [
                    "DevContextGraph dev-side context:",
                    "query: recover project context",
                    "project docs: 4",
                    "memories: 1",
                    "",
                    "top:",
                    "1. docs/runlog.md#Current State",
                    "   path: docs/runlog.md",
                    "2. docs/design.md#Boundary",
                ]
            )

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            render_mode="concise",
        )
        state = self.main_agent.MainAgentState(
            query="recover project context",
            is_owner=True,
        )

        execution = asyncio.run(runner.run(state))

        self.assertIn("MainAgentGraph read-only summary", execution.result.response_text)
        self.assertIn("project docs: 4", execution.result.response_text)
        self.assertIn("memories: 1", execution.result.response_text)
        self.assertIn("docs/runlog.md#Current State", execution.result.response_text)
        self.assertIn("/agent-debug", execution.result.response_text)
        self.assertNotIn("path: docs/runlog.md", execution.result.response_text)

    def test_read_only_runner_executes_semantic_owner_read_command(self):
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for owner command")

        async def execute_owner_read_command(command, context):
            calls.append((command, context.query, context.metadata["session_key"]))
            return "最近错误：\n暂无。"

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_read_command=execute_owner_read_command,
            render_mode="concise",
        )
        state = self.main_agent.MainAgentState(
            query="帮我看一下最近错误",
            is_owner=True,
            metadata={"session_key": "private:10001"},
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "")
        self.assertEqual(execution.result.requested_tool, "owner_read_command")
        self.assertEqual(execution.result.metadata["tool_arguments"]["command"], "recent_errors")
        self.assertEqual(calls, [("recent_errors", "帮我看一下最近错误", "private:10001")])
        self.assertIn("最近错误", execution.result.response_text)
        self.assertNotIn("/agent-debug", execution.result.response_text)
        self.assertNotIn("MainAgentGraph read-only summary", execution.result.response_text)

    def test_semantic_owner_read_runs_before_configured_llm_handler(self):
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for semantic owner read")

        async def execute_owner_read_command(command, _context):
            calls.append(command)
            return "最近错误：\n暂无。"

        async def configured_llm_handler(_state):
            raise AssertionError("configured llm handler should not run for semantic owner read")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_read_command=execute_owner_read_command,
            call_main_agent=configured_llm_handler,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="帮我看一下最近错误",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "")
        self.assertEqual(execution.result.requested_tool, "owner_read_command")
        self.assertEqual(calls, ["recent_errors"])

    def test_semantic_memory_retrieval_owner_read_extracts_query(self):
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for semantic memory retrieval")

        async def execute_owner_read_command(command, context):
            arguments = context.metadata["tool_arguments"]
            calls.append((command, arguments.get("query"), context.query))
            return f"记忆检索结果：{arguments.get('query')}"

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_read_command=execute_owner_read_command,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="记忆检索 Route B 审批流",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "")
        self.assertEqual(execution.result.requested_tool, "owner_read_command")
        self.assertEqual(
            execution.result.metadata["tool_arguments"],
            {"command": "memory_retrieval", "query": "Route B 审批流"},
        )
        self.assertEqual(
            calls,
            [("memory_retrieval", "Route B 审批流", "记忆检索 Route B 审批流")],
        )
        self.assertIn("记忆检索结果：Route B 审批流", execution.result.response_text)

    def test_owner_read_tool_is_visible_and_validates_command_in_executor(self):
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            return "dev context"

        async def execute_owner_read_command(command, _context):
            calls.append(command)
            return f"read:{command}"

        registry = self.main_agent_bridge.create_read_only_main_agent_tool_registry(
            retrieve_dev_context,
            execute_owner_read_command=execute_owner_read_command,
        )

        self.assertEqual(
            registry.visible_tool_names(),
            ["dev_context", "owner_read_command"],
        )
        self.assertEqual(
            registry.require("owner_read_command").risk_level,
            self.policy_risk.RiskLevel.READ_LOCAL,
        )

        result = asyncio.run(
            registry.execute(
                "owner_read_command",
                {"command": "ops_health"},
                self.tool_registry.ToolContext(is_owner=True),
            )
        )
        self.assertEqual(result.text, "read:ops_health")
        self.assertEqual(calls, ["ops_health"])

        result = asyncio.run(
            registry.execute(
                "owner_read_command",
                {"command": "root_graph_observations"},
                self.tool_registry.ToolContext(is_owner=True),
            )
        )
        self.assertEqual(result.text, "read:root_graph_observations")
        self.assertEqual(calls, ["ops_health", "root_graph_observations"])

        result = asyncio.run(
            registry.execute(
                "owner_read_command",
                {"command": "vision_troubleshoot"},
                self.tool_registry.ToolContext(is_owner=True),
            )
        )
        self.assertEqual(result.text, "read:vision_troubleshoot")
        self.assertEqual(calls, ["ops_health", "root_graph_observations", "vision_troubleshoot"])

        result = asyncio.run(
            registry.execute(
                "owner_read_command",
                {"command": "memory_rag_troubleshoot"},
                self.tool_registry.ToolContext(is_owner=True),
            )
        )
        self.assertEqual(result.text, "read:memory_rag_troubleshoot")
        self.assertEqual(
            calls,
            [
                "ops_health",
                "root_graph_observations",
                "vision_troubleshoot",
                "memory_rag_troubleshoot",
            ],
        )

        with self.assertRaises(self.tool_registry.ToolExecutionError):
            asyncio.run(
                registry.execute(
                    "owner_read_command",
                    {"command": "clear_image_cache"},
                    self.tool_registry.ToolContext(is_owner=True),
                )
            )

    def test_read_only_runner_executes_semantic_agent_task_read(self):
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for task read")

        async def execute_agent_task_read(command, reference, context):
            calls.append((command, reference, context.query))
            return "Agent 审批状态：\n暂无待查看审批。"

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_agent_task_read=execute_agent_task_read,
            render_mode="concise",
        )
        state = self.main_agent.MainAgentState(
            query="帮我看看有没有待审批的东西",
            is_owner=True,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "")
        self.assertEqual(execution.result.requested_tool, "agent_task_read")
        self.assertEqual(execution.result.metadata["tool_arguments"]["command"], "list_approvals")
        self.assertEqual(calls, [("list_approvals", "", "帮我看看有没有待审批的东西")])
        self.assertIn("Agent 审批状态", execution.result.response_text)

    def test_semantic_task_read_runs_before_configured_llm_handler(self):
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for semantic task read")

        async def execute_agent_task_read(command, reference, _context):
            calls.append((command, reference))
            return "Agent 任务状态：\n暂无任务。"

        async def configured_llm_handler(_state):
            raise AssertionError("configured llm handler should not run for semantic task read")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_agent_task_read=execute_agent_task_read,
            call_main_agent=configured_llm_handler,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="看看现在任务表",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "")
        self.assertEqual(execution.result.requested_tool, "agent_task_read")
        self.assertEqual(calls, [("list_tasks", "")])

    def test_semantic_next_step_runs_agent_task_read_before_dev_context(self):
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for task collaboration next step")

        async def execute_agent_task_read(command, reference, _context):
            calls.append((command, reference))
            return "Agent 任务协作：下一步\n当前没有任务或审批记录。"

        async def configured_llm_handler(_state):
            raise AssertionError("configured llm handler should not run for semantic next step")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_agent_task_read=execute_agent_task_read,
            call_main_agent=configured_llm_handler,
            render_mode="concise",
        )

        for query in ("下一步", "现在卡在哪", "有什么待我确认"):
            with self.subTest(query=query):
                execution = asyncio.run(
                    runner.run(
                        self.main_agent.MainAgentState(
                            query=query,
                            is_owner=True,
                        )
                    )
                )

                self.assertEqual(execution.result.error, "")
                self.assertEqual(execution.result.requested_tool, "agent_task_read")
                self.assertEqual(
                    execution.result.metadata["tool_arguments"]["command"],
                    "next_step",
                )
                self.assertIn("Agent 任务协作", execution.result.response_text)

        self.assertEqual(calls, [("next_step", ""), ("next_step", ""), ("next_step", "")])

    def test_local_management_tool_result_bypasses_llm_summary(self):
        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run")

        async def execute_owner_read_command(_command, _context):
            return "当前角色卡内容：\n不要模仿这张角色卡的说话方式。"

        async def summarize_tool_result(_state):
            raise AssertionError("local management tools should not be summarized by llm")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_read_command=execute_owner_read_command,
            summarize_tool_result=summarize_tool_result,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="看看角色卡",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "")
        self.assertEqual(execution.result.requested_tool, "owner_read_command")
        self.assertEqual(
            execution.result.response_text,
            "当前角色卡内容：\n不要模仿这张角色卡的说话方式。",
        )

    def test_agent_task_read_tool_supports_latest_detail_reference(self):
        async def retrieve_dev_context(_query, _is_owner):
            return "dev context"

        async def execute_agent_task_read(command, reference, _context):
            return f"{command}:{reference}"

        registry = self.main_agent_bridge.create_read_only_main_agent_tool_registry(
            retrieve_dev_context,
            execute_agent_task_read=execute_agent_task_read,
        )

        self.assertEqual(
            registry.visible_tool_names(),
            ["dev_context", "agent_task_read"],
        )

        result = asyncio.run(
            registry.execute(
                "agent_task_read",
                {"command": "task_detail", "reference": "latest"},
                self.tool_registry.ToolContext(is_owner=True),
            )
        )
        self.assertEqual(result.text, "task_detail:latest")

        result = asyncio.run(
            registry.execute(
                "agent_task_read",
                {"command": "next_step"},
                self.tool_registry.ToolContext(is_owner=True),
            )
        )
        self.assertEqual(result.text, "next_step:")

        result = asyncio.run(
            registry.execute(
                "agent_task_read",
                {"command": "workbench"},
                self.tool_registry.ToolContext(is_owner=True),
            )
        )
        self.assertEqual(result.text, "workbench:")

        with self.assertRaises(self.tool_registry.ToolExecutionError):
            asyncio.run(
                registry.execute(
                    "agent_task_read",
                    {"command": "approval_approve"},
                    self.tool_registry.ToolContext(is_owner=True),
                )
            )

    def test_owner_read_classifier_covers_second_read_only_command_batch(self):
        cases = {
            "看看角色卡": "view_persona",
            "看看有哪些角色卡": "role_card_list",
            "查看长期记忆": "view_long_term_memory",
            "摘要状态": "summary_status",
            "看看群白名单": "group_whitelist",
            "语音状态怎么样": "tts_status",
            "RAG状态": "rag_status",
            "诊断一下 Ollama": "ops_health",
            "看一下视觉和记忆状态": "ops_health",
            "最近图片和 RAG 有没有问题": "ops_health",
            "做一次系统健康检查": "ops_health",
            "完整排查图片识别问题": "vision_troubleshoot",
            "排查识图为什么失败": "vision_troubleshoot",
            "完整排查记忆检索问题": "memory_rag_troubleshoot",
            "排查 MemoryRAG 为什么没有召回": "memory_rag_troubleshoot",
            "看看访问控制": "access_overview",
            "当前主模型是什么": "model_config_status",
            "看看项目文档索引": "rag_index_detail",
            "main agent 最近失败": "main_agent_observations",
            "RootGraph 最近观测": "root_graph_observations",
            "看看普通聊天路由": "root_graph_observations",
            "chat commit 状态": "root_graph_observations",
            "记忆检索 Route B 审批流": "memory_retrieval",
            "查一下记忆里有没有审批流": "memory_retrieval",
        }

        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(
                    self.main_agent_bridge.classify_owner_read_command(query),
                    expected,
                )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_read_command("帮我清空图片缓存"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_read_command("帮我选择角色卡"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_read_command("重建记忆索引"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_read_command("帮我添加事实记忆"),
            "",
        )

    def test_agent_task_read_classifier_accepts_task_card_wording(self):
        self.assertEqual(
            self.main_agent_bridge.classify_agent_task_read_command("下一步"),
            ("next_step", ""),
        )
        self.assertEqual(
            self.main_agent_bridge.classify_agent_task_read_command("现在卡在哪"),
            ("next_step", ""),
        )
        self.assertEqual(
            self.main_agent_bridge.classify_agent_task_read_command("看看任务工作台"),
            ("workbench", ""),
        )
        self.assertEqual(
            self.main_agent_bridge.classify_agent_task_read_command("打开任务看板"),
            ("workbench", ""),
        )
        self.assertEqual(
            self.main_agent_bridge.classify_agent_task_read_command("看看任务卡"),
            ("list_tasks", ""),
        )
        self.assertEqual(
            self.main_agent_bridge.classify_agent_task_read_command("查看任务列表"),
            ("list_tasks", ""),
        )

    def test_semantic_agent_task_command_runs_before_read_and_llm(self):
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for task command")

        async def execute_agent_task_read(_command, _reference, _context):
            raise AssertionError("task read should not run for approval confirmation")

        async def execute_agent_task_command(command, reference, goal, context):
            calls.append((command, reference, goal, context.query))
            return "已确认 Agent 审批 #42。\nApproval resume completed"

        async def configured_llm_handler(_state):
            raise AssertionError("configured llm handler should not run for task command")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_agent_task_read=execute_agent_task_read,
            execute_agent_task_command=execute_agent_task_command,
            call_main_agent=configured_llm_handler,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="帮我确认最新审批",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "")
        self.assertEqual(execution.result.requested_tool, "agent_task_command")
        self.assertEqual(execution.result.policy_decision, "allow")
        self.assertEqual(
            execution.result.metadata["tool_arguments"]["command"],
            "approve_approval",
        )
        self.assertEqual(calls, [("approve_approval", "latest", "", "帮我确认最新审批")])
        self.assertIn("已确认 Agent 审批", execution.result.response_text)

    def test_agent_task_command_tool_is_hidden_from_llm_contract(self):
        async def retrieve_dev_context(_query, _is_owner):
            return "dev context"

        async def execute_agent_task_command(_command, _reference, _goal, _context):
            return "ok"

        registry = self.main_agent_bridge.create_read_only_main_agent_tool_registry(
            retrieve_dev_context,
            execute_agent_task_command=execute_agent_task_command,
        )

        self.assertEqual(registry.visible_tool_names(), ["dev_context"])
        self.assertEqual(
            registry.require("agent_task_command").risk_level,
            self.policy_risk.RiskLevel.INTERNAL,
        )
        result = asyncio.run(
            registry.execute(
                "agent_task_command",
                {"command": "cancel_task", "reference": "latest"},
                self.tool_registry.ToolContext(is_owner=True),
            )
        )
        self.assertEqual(result.text, "ok")

    def test_agent_task_command_classifier_accepts_control_wording(self):
        cases = {
            "帮我确认最新审批": ("approve_approval", "latest", ""),
            "拒绝审批 #7": ("reject_approval", "7", ""),
            "取消最新任务": ("cancel_task", "latest", ""),
            "帮我创建一个任务：整理审批流": ("create_task", "", "整理审批流"),
            "把整理 Route B 加入任务": ("create_task", "", "整理 Route B"),
            "创建审批演练：写入版本日志": ("create_approval_drill", "", "写入版本日志"),
        }

        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(
                    self.main_agent_bridge.classify_agent_task_command(query),
                    expected,
                )
        self.assertIsNone(
            self.main_agent_bridge.classify_agent_task_command("看看任务卡")
        )
        self.assertIsNone(
            self.main_agent_bridge.classify_agent_task_command("有没有待审批")
        )

    def test_semantic_owner_write_requires_approval_before_execution(self):
        calls = []
        approvals = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for semantic write")

        def execute_owner_write_command(command, _context):
            calls.append(command)
            raise AssertionError("write command should not execute before approval")

        async def request_approval(state, risk_level, policy_reason):
            approvals.append(
                (
                    state.requested_tool,
                    state.metadata["tool_arguments"]["command"],
                    risk_level.value,
                    policy_reason,
                )
            )
            return "Agent 请求审批 #42\n/agent 确认 42\n/agent 拒绝 42"

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
            request_approval=request_approval,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="帮我清空图片缓存",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "approval_required")
        self.assertEqual(execution.result.requested_tool, "owner_write_command")
        self.assertEqual(execution.result.policy_decision, "require_approval")
        self.assertEqual(calls, [])
        self.assertEqual(
            approvals,
            [
                (
                    "owner_write_command",
                    "clear_image_cache",
                    "write_local",
                    "local writes require approval",
                )
            ],
        )
        self.assertIn("Agent 请求审批 #42", execution.result.response_text)

    def test_semantic_select_persona_requires_approval_and_keeps_target(self):
        calls = []
        approvals = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for semantic persona switch")

        def execute_owner_write_command(command, _context):
            calls.append(command)
            raise AssertionError("select_persona should not execute before approval")

        async def request_approval(state, risk_level, policy_reason):
            arguments = state.metadata["tool_arguments"]
            approvals.append(
                (
                    state.requested_tool,
                    arguments["command"],
                    arguments["target"],
                    risk_level.value,
                    policy_reason,
                )
            )
            return "Agent 请求审批 #43\n/agent 确认 43\n/agent 拒绝 43"

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
            request_approval=request_approval,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="帮我选择角色卡 moyan",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "approval_required")
        self.assertEqual(execution.result.requested_tool, "owner_write_command")
        self.assertEqual(execution.result.policy_decision, "require_approval")
        self.assertEqual(calls, [])
        self.assertEqual(
            execution.result.metadata["tool_arguments"],
            {
                "command": "select_persona",
                "query": "帮我选择角色卡 moyan",
                "target": "moyan",
            },
        )
        self.assertEqual(
            approvals,
            [
                (
                    "owner_write_command",
                    "select_persona",
                    "moyan",
                    "write_local",
                    "local writes require approval",
                )
            ],
        )
        self.assertIn("Agent 请求审批 #43", execution.result.response_text)

    def test_semantic_add_memory_requires_approval_and_keeps_content(self):
        calls = []
        approvals = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for semantic memory write")

        def execute_owner_write_command(command, _context):
            calls.append(command)
            raise AssertionError("memory writes should not execute before approval")

        async def request_approval(state, risk_level, policy_reason):
            arguments = state.metadata["tool_arguments"]
            approvals.append(
                (
                    state.requested_tool,
                    arguments["command"],
                    arguments["content"],
                    risk_level.value,
                    policy_reason,
                )
            )
            return "Agent 请求审批 #44\n/agent 确认 44\n/agent 拒绝 44"

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
            request_approval=request_approval,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="帮我添加事实记忆 主人喜欢先看结论",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "approval_required")
        self.assertEqual(execution.result.requested_tool, "owner_write_command")
        self.assertEqual(calls, [])
        self.assertEqual(
            execution.result.metadata["tool_arguments"],
            {
                "command": "add_fact_memory",
                "query": "帮我添加事实记忆 主人喜欢先看结论",
                "content": "主人喜欢先看结论",
            },
        )
        self.assertEqual(
            approvals,
            [
                (
                    "owner_write_command",
                    "add_fact_memory",
                    "主人喜欢先看结论",
                    "write_local",
                    "local writes require approval",
                )
            ],
        )
        self.assertIn("Agent 请求审批 #44", execution.result.response_text)

    def test_semantic_clear_session_summaries_requires_approval(self):
        calls = []
        approvals = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for semantic summary clear")

        def execute_owner_write_command(command, _context):
            calls.append(command)
            raise AssertionError("clear_session_summaries should not execute before approval")

        async def request_approval(state, risk_level, policy_reason):
            arguments = state.metadata["tool_arguments"]
            approvals.append(
                (
                    state.requested_tool,
                    arguments["command"],
                    risk_level.value,
                    policy_reason,
                )
            )
            return "Agent 请求审批 #45\n/agent 确认 45\n/agent 拒绝 45"

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
            request_approval=request_approval,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="帮我清空当前摘要",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "approval_required")
        self.assertEqual(execution.result.requested_tool, "owner_write_command")
        self.assertEqual(execution.result.policy_decision, "require_approval")
        self.assertEqual(calls, [])
        self.assertEqual(
            execution.result.metadata["tool_arguments"],
            {
                "command": "clear_session_summaries",
                "query": "帮我清空当前摘要",
            },
        )
        self.assertEqual(
            approvals,
            [
                (
                    "owner_write_command",
                    "clear_session_summaries",
                    "write_local",
                    "local writes require approval",
                )
            ],
        )
        self.assertIn("Agent 请求审批 #45", execution.result.response_text)

    def test_semantic_delete_session_summary_requires_approval_and_keeps_id(self):
        calls = []
        approvals = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for semantic summary delete")

        def execute_owner_write_command(command, _context):
            calls.append(command)
            raise AssertionError("delete_session_summary should not execute before approval")

        async def request_approval(state, risk_level, policy_reason):
            arguments = state.metadata["tool_arguments"]
            approvals.append(
                (
                    state.requested_tool,
                    arguments["command"],
                    arguments["summary_id"],
                    risk_level.value,
                    policy_reason,
                )
            )
            return "Agent 请求审批 #46\n/agent 确认 46\n/agent 拒绝 46"

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
            request_approval=request_approval,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="帮我删除摘要 123",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "approval_required")
        self.assertEqual(execution.result.requested_tool, "owner_write_command")
        self.assertEqual(execution.result.policy_decision, "require_approval")
        self.assertEqual(calls, [])
        self.assertEqual(
            execution.result.metadata["tool_arguments"],
            {
                "command": "delete_session_summary",
                "query": "帮我删除摘要 123",
                "summary_id": "123",
            },
        )
        self.assertEqual(
            approvals,
            [
                (
                    "owner_write_command",
                    "delete_session_summary",
                    "123",
                    "write_local",
                    "local writes require approval",
                )
            ],
        )
        self.assertIn("Agent 请求审批 #46", execution.result.response_text)

    def test_semantic_delete_session_summary_without_numeric_id_asks_owner(self):
        approvals = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for incomplete summary delete")

        def execute_owner_write_command(_command, _context):
            raise AssertionError("incomplete summary delete must not execute")

        async def request_approval(state, risk_level, policy_reason):
            approvals.append((state, risk_level, policy_reason))
            raise AssertionError("incomplete summary delete must not create approval")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
            request_approval=request_approval,
            render_mode="concise",
        )

        for query in ("帮我删除摘要", "帮我删除摘要 最新", "删除当前摘要"):
            with self.subTest(query=query):
                execution = asyncio.run(
                    runner.run(
                        self.main_agent.MainAgentState(
                            query=query,
                            is_owner=True,
                        )
                    )
                )

                self.assertEqual(execution.result.error, "")
                self.assertEqual(
                    execution.result.action,
                    self.main_agent.MainAgentAction.ASK_OWNER.value,
                )
                self.assertEqual(execution.result.requested_tool, "")
                self.assertIn("需要明确的数字摘要 ID", execution.result.response_text)
                self.assertIn("尚未创建审批", execution.result.response_text)
                self.assertEqual(approvals, [])

    def test_semantic_owner_write_missing_arguments_asks_owner_before_approval(self):
        approvals = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for incomplete owner write")

        def execute_owner_write_command(_command, _context):
            raise AssertionError("incomplete owner write must not execute")

        async def request_approval(state, risk_level, policy_reason):
            approvals.append((state, risk_level, policy_reason))
            raise AssertionError("incomplete owner write must not create approval")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
            request_approval=request_approval,
            render_mode="concise",
        )
        cases = {
            "帮我选择角色卡": "角色卡 key",
            "帮我使用角色卡": "角色卡 key",
            "帮我添加事实记忆": "事实记忆需要明确的记忆内容",
            "帮我添加偏好记忆": "偏好记忆需要明确的记忆内容",
            "帮我加入群白名单": "需要明确的数字 target",
            "帮我启用本群": "需要明确的数字 target",
            "帮我把张三加入黑名单": "需要明确的数字 target",
        }

        for query, expected_text in cases.items():
            with self.subTest(query=query):
                execution = asyncio.run(
                    runner.run(
                        self.main_agent.MainAgentState(
                            query=query,
                            is_owner=True,
                        )
                    )
                )

                self.assertEqual(execution.result.error, "")
                self.assertEqual(
                    execution.result.action,
                    self.main_agent.MainAgentAction.ASK_OWNER.value,
                )
                self.assertEqual(execution.result.requested_tool, "")
                self.assertIn(expected_text, execution.result.response_text)
                self.assertIn("尚未创建审批", execution.result.response_text)
                self.assertEqual(approvals, [])

    def test_semantic_owner_write_disallowed_batch_stops_before_approval(self):
        approvals = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for disallowed owner write")

        def execute_owner_write_command(_command, _context):
            raise AssertionError("disallowed owner write must not execute")

        async def request_approval(state, risk_level, policy_reason):
            approvals.append((state, risk_level, policy_reason))
            raise AssertionError("disallowed owner write must not create approval")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
            request_approval=request_approval,
            render_mode="concise",
        )

        for query in ("帮我清空全部摘要", "帮我清空全部上下文", "帮我删除长期记忆 12"):
            with self.subTest(query=query):
                execution = asyncio.run(
                    runner.run(
                        self.main_agent.MainAgentState(
                            query=query,
                            is_owner=True,
                        )
                    )
                )

                self.assertEqual(execution.result.error, "")
                self.assertEqual(
                    execution.result.action,
                    self.main_agent.MainAgentAction.ASK_OWNER.value,
                )
                self.assertEqual(execution.result.requested_tool, "")
                self.assertIn("当前不开放", execution.result.response_text)
                self.assertIn("尚未创建审批", execution.result.response_text)
                self.assertEqual(approvals, [])

    def test_llm_owner_write_delete_summary_without_id_is_rejected_before_approval(self):
        approvals = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for owner write request")

        def execute_owner_write_command(_command, _context):
            raise AssertionError("missing summary_id must not execute")

        async def request_approval(state, risk_level, policy_reason):
            approvals.append((state, risk_level, policy_reason))
            raise AssertionError("missing summary_id must not create approval")

        def call_main_agent(state):
            state.raw_action_request = self.main_agent_bridge.owner_write_command_action_json(
                "delete_session_summary",
                query=state.query,
                reason="llm planned delete summary without id",
            )
            return state

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
            request_approval=request_approval,
            call_main_agent=call_main_agent,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="planned owner write",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "need_argument")
        self.assertEqual(execution.result.requested_tool, "")
        self.assertIn("需要明确的数字 summary_id", execution.result.response_text)
        self.assertEqual(approvals, [])

    def test_semantic_access_list_write_requires_approval_and_keeps_target(self):
        calls = []
        approvals = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run for semantic access writes")

        def execute_owner_write_command(command, _context):
            calls.append(command)
            raise AssertionError("access writes should not execute before approval")

        async def request_approval(state, risk_level, policy_reason):
            arguments = state.metadata["tool_arguments"]
            approvals.append(
                (
                    state.requested_tool,
                    arguments["command"],
                    arguments["target"],
                    risk_level.value,
                    policy_reason,
                )
            )
            return "Agent 请求审批 #47\n/agent 确认 47\n/agent 拒绝 47"

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
            request_approval=request_approval,
            render_mode="concise",
        )

        execution = asyncio.run(
            runner.run(
                self.main_agent.MainAgentState(
                    query="帮我把群 123456 加入群白名单",
                    is_owner=True,
                )
            )
        )

        self.assertEqual(execution.result.error, "approval_required")
        self.assertEqual(execution.result.requested_tool, "owner_write_command")
        self.assertEqual(execution.result.policy_decision, "require_approval")
        self.assertEqual(calls, [])
        self.assertEqual(
            execution.result.metadata["tool_arguments"],
            {
                "command": "allow_group",
                "query": "帮我把群 123456 加入群白名单",
                "target": "123456",
            },
        )
        self.assertEqual(
            approvals,
            [
                (
                    "owner_write_command",
                    "allow_group",
                    "123456",
                    "write_local",
                    "local writes require approval",
                )
            ],
        )
        self.assertIn("Agent 请求审批 #47", execution.result.response_text)

    def test_owner_write_executor_passes_full_arguments_to_resume_tool(self):
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            return "dev context"

        def execute_owner_write_command(command, context):
            calls.append((command, dict(context.metadata["tool_arguments"])))
            return "已选择角色卡：moyan，墨言"

        registry = self.main_agent_bridge.create_read_only_main_agent_tool_registry(
            retrieve_dev_context,
            execute_owner_write_command=execute_owner_write_command,
        )

        result = asyncio.run(
            registry.execute(
                "owner_write_command",
                {
                    "command": "select_persona",
                    "query": "帮我选择角色卡 moyan",
                    "target": "moyan",
                },
                self.tool_registry.ToolContext(is_owner=True),
            )
        )

        self.assertEqual(result.text, "已选择角色卡：moyan，墨言")
        self.assertEqual(
            calls,
            [
                (
                    "select_persona",
                    {
                        "command": "select_persona",
                        "query": "帮我选择角色卡 moyan",
                        "target": "moyan",
                    },
                )
            ],
        )

    def test_owner_write_classifier_only_allows_first_safe_batch(self):
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我清空图片缓存"),
            "clear_image_cache",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我清空错误日志"),
            "clear_error_log",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我选择角色卡 moyan"),
            "select_persona",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我使用角色卡 moyan"),
            "select_persona",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我添加事实记忆 主人喜欢先看结论"),
            "add_fact_memory",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我添加偏好记忆 技术讨论先给结论"),
            "add_preference_memory",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我清空当前摘要"),
            "clear_session_summaries",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我删除摘要 123"),
            "delete_session_summary",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我把群 123456 加入群白名单"),
            "allow_group",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我把群 123456 移出群白名单"),
            "deny_group",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我把用户 10001 加入私聊白名单"),
            "allow_private",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我把用户 10001 移出私聊白名单"),
            "deny_private",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我把用户 10002 加入黑名单"),
            "block_user",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我解除拉黑 10002"),
            "unblock_user",
        )
        self.assertEqual(
            self.main_agent_bridge.extract_owner_persona_target("帮我选择角色卡 moyan"),
            "moyan",
        )
        self.assertEqual(
            self.main_agent_bridge.extract_owner_persona_target("帮我使用角色卡 moyan"),
            "moyan",
        )
        self.assertEqual(
            self.main_agent_bridge.extract_owner_fact_memory_content(
                "帮我添加事实记忆 主人喜欢先看结论"
            ),
            "主人喜欢先看结论",
        )
        self.assertEqual(
            self.main_agent_bridge.extract_owner_preference_memory_content(
                "帮我添加偏好记忆 技术讨论先给结论"
            ),
            "技术讨论先给结论",
        )
        self.assertEqual(
            self.main_agent_bridge.extract_owner_delete_summary_id("帮我删除摘要 123"),
            "123",
        )
        self.assertEqual(
            self.main_agent_bridge.extract_owner_delete_summary_id("把当前会话摘要 #456 删除"),
            "456",
        )
        self.assertEqual(
            self.main_agent_bridge.extract_owner_access_target(
                "allow_group",
                "帮我把群 123456 加入群白名单",
            ),
            "123456",
        )
        self.assertEqual(
            self.main_agent_bridge.extract_owner_access_target("unblock_user", "解除拉黑 10002"),
            "10002",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我清空全部上下文"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我加入群白名单"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我启用本群"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我把张三加入黑名单"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我选择角色卡"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我添加事实记忆"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我清空全部摘要"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我删除摘要"),
            "",
        )
        self.assertEqual(
            self.main_agent_bridge.classify_owner_write_command("帮我删除摘要 最新"),
            "",
        )

    def test_read_only_runner_can_render_llm_tool_summary(self):
        async def retrieve_dev_context(_query, _is_owner):
            return "DevContextGraph raw result"

        async def summarize_tool_result(state):
            state.response_text = f"自然总结：{state.tool_result}"
            return state

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            summarize_tool_result=summarize_tool_result,
            render_mode="concise",
        )
        state = self.main_agent.MainAgentState(
            query="recover project context",
            is_owner=True,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.response_text, "自然总结：DevContextGraph raw result")
        self.assertNotIn("/agent-debug", execution.result.response_text)

    def test_read_only_runner_falls_back_when_tool_summary_fails(self):
        async def retrieve_dev_context(_query, _is_owner):
            return "\n".join(
                [
                    "DevContextGraph dev-side context:",
                    "project docs: 1",
                    "1. docs/runlog.md#Current State",
                ]
            )

        async def summarize_tool_result(_state):
            raise RuntimeError("summary unavailable")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context,
            summarize_tool_result=summarize_tool_result,
            render_mode="concise",
        )
        state = self.main_agent.MainAgentState(
            query="recover project context",
            is_owner=True,
        )

        execution = asyncio.run(runner.run(state))

        self.assertIn("MainAgentGraph read-only summary", execution.result.response_text)
        self.assertIn("docs/runlog.md#Current State", execution.result.response_text)
        self.assertEqual(execution.result.metadata["tool_summary_error"], "summary unavailable")
        self.assertEqual(execution.result.metadata["tool_summary_error_type"], "RuntimeError")

    def test_read_only_runner_denies_non_owner_before_llm_or_tool(self):
        def fake_llm(_messages):
            raise AssertionError("llm should not run for non-owner")

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("tool should not run for non-owner")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            llm_call=fake_llm,
            retrieve_dev_context=retrieve_dev_context,
        )
        state = self.main_agent.MainAgentState(query="recover", is_owner=False)

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "permission_denied")
        self.assertIn("owner access is required", execution.result.response_text)
        self.assertEqual(
            execution.node_trace,
            (self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST,),
        )

    def test_read_only_runner_denies_group_before_llm_or_tool(self):
        def fake_llm(_messages):
            raise AssertionError("llm should not run for group")

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("tool should not run for group")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            llm_call=fake_llm,
            retrieve_dev_context=retrieve_dev_context,
        )
        state = self.main_agent.MainAgentState(query="recover", is_owner=True, is_group=True)

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "group_denied")
        self.assertIn("private-only", execution.result.response_text)
        self.assertEqual(
            execution.node_trace,
            (self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST,),
        )

    def test_read_only_runner_accepts_final_answer_without_tool_execution(self):
        def fake_llm(_messages):
            return '{"action":"final_answer","content":"already enough context"}'

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("tool should not run for final_answer")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            llm_call=fake_llm,
            retrieve_dev_context=retrieve_dev_context,
        )
        state = self.main_agent.MainAgentState(query="summarize", is_owner=True)

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "")
        self.assertEqual(execution.result.action, self.main_agent.MainAgentAction.FINAL_ANSWER.value)
        self.assertEqual(execution.result.response_text, "already enough context")
        self.assertEqual(execution.result.tool_result, "")

    def test_read_only_runner_rejects_fake_llm_shell_tool(self):
        def fake_llm(_messages):
            return '{"action":"tool_request","tool_name":"shell","arguments":{"query":"dir"}}'

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("tool should not run after invalid action")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            llm_call=fake_llm,
            retrieve_dev_context=retrieve_dev_context,
        )
        state = self.main_agent.MainAgentState(query="run dir", is_owner=True)

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "invalid_action_request")
        self.assertIn("unsupported tool", execution.result.response_text)
        self.assertEqual(
            execution.node_trace,
            (
                self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST,
                self.main_agent.MainAgentNode.BUILD_AGENT_CONTEXT,
                self.main_agent.MainAgentNode.CALL_MAIN_AGENT,
                self.main_agent.MainAgentNode.VALIDATE_ACTION_REQUEST,
            ),
        )

    def test_read_only_runner_catches_dev_context_tool_error(self):
        async def retrieve_dev_context(_query, _is_owner):
            raise RuntimeError("dev context unavailable")

        runner = self.main_agent_bridge.create_read_only_main_agent_runner(
            retrieve_dev_context=retrieve_dev_context
        )
        state = self.main_agent.MainAgentState(query="recover", is_owner=True)

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "tool_execution_failed")
        self.assertIn("read-only tool failed", execution.result.response_text)
        self.assertIn("dev context unavailable", execution.result.response_text)
        self.assertEqual(
            execution.node_trace,
            (
                self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST,
                self.main_agent.MainAgentNode.BUILD_AGENT_CONTEXT,
                self.main_agent.MainAgentNode.CALL_MAIN_AGENT,
                self.main_agent.MainAgentNode.VALIDATE_ACTION_REQUEST,
                self.main_agent.MainAgentNode.CHECK_TOOL_POLICY,
                self.main_agent.MainAgentNode.EXECUTE_TOOL,
            ),
        )

    def test_generic_policy_checker_turns_require_approval_into_interrupt(self):
        calls = []

        def call_agent(agent_state):
            agent_state.action = self.main_agent.MainAgentAction.TOOL_REQUEST.value
            agent_state.requested_tool = "write_file"
            agent_state.tool_query = "docs/example.md"
            return agent_state

        async def request_approval(agent_state, risk_level, policy_reason):
            calls.append((agent_state.requested_tool, risk_level.value, policy_reason))
            return "Agent 请求审批 #42\n/agent 确认 42\n/agent 拒绝 42"

        async def execute_tool(_agent_state):
            raise AssertionError("execute_tool should not run before approval")

        runner = self.main_agent.MainAgentGraphRunner(
            call_main_agent=call_agent,
            check_tool_policy=self.main_agent_bridge.create_tool_policy_checker(
                risk_level_for_tool=lambda _state: self.policy_risk.RiskLevel.WRITE_LOCAL,
                enable_local_write=True,
                request_approval=request_approval,
            ),
            execute_tool=execute_tool,
        )
        state = self.main_agent.MainAgentState(
            query="write docs/example.md",
            is_owner=True,
            is_group=False,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "approval_required")
        self.assertEqual(execution.result.policy_decision, "require_approval")
        self.assertEqual(execution.result.policy_reason, "local writes require approval")
        self.assertIn("Agent 请求审批 #42", execution.result.response_text)
        self.assertEqual(calls, [("write_file", "write_local", "local writes require approval")])
        self.assertTrue(execution.result.metadata["approval_required"])
        self.assertEqual(execution.result.metadata["approval_tool_name"], "write_file")
        self.assertEqual(execution.result.metadata["risk_level"], "write_local")
        self.assertEqual(
            execution.node_trace,
            (
                self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST,
                self.main_agent.MainAgentNode.BUILD_AGENT_CONTEXT,
                self.main_agent.MainAgentNode.CALL_MAIN_AGENT,
                self.main_agent.MainAgentNode.VALIDATE_ACTION_REQUEST,
                self.main_agent.MainAgentNode.CHECK_TOOL_POLICY,
            ),
        )

    def test_tool_registry_accepts_dry_run_only_when_registered(self):
        raw = {
            "action": "tool_request",
            "tool_name": "dry_run_write_file",
            "arguments": {
                "path": "docs/version-runlog.md",
                "content_summary": "append Route B dry-run note",
            },
        }

        with self.assertRaises(self.main_agent.MainAgentActionRequestError):
            self.main_agent.parse_main_agent_action_request(raw)

        registry = self.tool_registry.create_default_main_agent_tool_registry(
            include_dry_run_tools=True
        )
        action_request = self.main_agent.parse_main_agent_action_request(
            raw,
            tool_registry=registry,
        )

        self.assertEqual(action_request.tool_name, "dry_run_write_file")
        self.assertEqual(action_request.arguments["path"], "docs/version-runlog.md")
        self.assertEqual(registry.require("dry_run_write_file").risk_level.value, "write_local")

    def test_tool_registry_validates_required_and_unknown_arguments(self):
        registry = self.tool_registry.create_default_main_agent_tool_registry()

        with self.assertRaises(self.tool_registry.ToolArgumentError) as missing:
            registry.validate_arguments("dev_context", {})
        self.assertIn("requires arguments.query", str(missing.exception))

        with self.assertRaises(self.tool_registry.ToolArgumentError) as unknown:
            registry.validate_arguments(
                "dev_context",
                {"query": "recover context", "extra": "not allowed"},
            )
        self.assertIn("unsupported arguments: extra", str(unknown.exception))

        self.assertEqual(
            registry.validate_arguments("dev_context", {"query": "recover context"}),
            {"query": "recover context"},
        )

    def test_tool_registry_rejects_duplicate_registration(self):
        risk = self.policy_risk.RiskLevel.READ_LOCAL
        spec = self.tool_registry.ToolSpec(
            name="snapshot",
            description="Read a snapshot.",
            risk_level=risk,
        )
        registry = self.tool_registry.ToolRegistry([spec])

        with self.assertRaises(ValueError) as duplicate:
            registry.register(spec)
        self.assertIn("duplicate tool registered: snapshot", str(duplicate.exception))

    def test_tool_registry_hides_internal_dry_run_tool_from_llm_visible_list(self):
        registry = self.tool_registry.create_default_main_agent_tool_registry(
            include_dry_run_tools=True
        )

        self.assertEqual(registry.visible_tool_names(), ["dev_context"])
        self.assertFalse(registry.require("dev_context").approval_resume_enabled)
        self.assertTrue(registry.require("dry_run_write_file").requires_approval)
        self.assertFalse(registry.require("dry_run_write_file").llm_visible)
        self.assertTrue(registry.require("dry_run_write_file").approval_resume_enabled)

    def test_registry_backed_policy_interrupts_dry_run_write_before_execution(self):
        registry = self.tool_registry.create_default_main_agent_tool_registry(
            include_dry_run_tools=True
        )

        def call_agent(agent_state):
            agent_state.raw_action_request = {
                "action": "tool_request",
                "tool_name": "dry_run_write_file",
                "arguments": {
                    "path": "docs/version-runlog.md",
                    "content_summary": "append Route B dry-run note",
                },
            }
            return agent_state

        async def request_approval(agent_state, risk_level, policy_reason):
            return (
                f"approval for {agent_state.requested_tool} "
                f"{risk_level.value} {policy_reason}"
            )

        async def execute_tool(_agent_state):
            raise AssertionError("dry_run_write_file should stop at approval")

        runner = self.main_agent.MainAgentGraphRunner(
            call_main_agent=call_agent,
            validate_action_request=self.main_agent_bridge.create_main_agent_action_validator(
                registry
            ),
            check_tool_policy=self.main_agent_bridge.create_tool_policy_checker(
                risk_level_for_tool=lambda state: registry.require(state.requested_tool).risk_level,
                enable_local_write=True,
                request_approval=request_approval,
            ),
            execute_tool=execute_tool,
        )

        execution = asyncio.run(
            runner.run(self.main_agent.MainAgentState(query="dry-run write", is_owner=True))
        )

        self.assertEqual(execution.result.error, "approval_required")
        self.assertEqual(execution.result.policy_decision, "require_approval")
        self.assertIn("approval for dry_run_write_file", execution.result.response_text)
        self.assertEqual(execution.result.metadata["risk_level"], "write_local")

    def test_runtime_handler_dispatches_main_agent_intent_through_root_graph(self):
        state_mod = self.modules["state"]
        runtime_mod = self.modules["runtime"]
        calls = []

        async def retrieve_dev_context(query, is_owner):
            calls.append((query, is_owner))
            return "runtime dev context"

        handler = self.main_agent_bridge.create_read_only_main_agent_runtime_handler(
            retrieve_dev_context=retrieve_dev_context,
            render_mode="concise",
        )
        runtime_state = state_mod.RuntimeState(
            event=state_mod.EventContext(
                message_id="9001",
                raw_text="/agent recover",
                plain_text="recover",
            ),
            actor=state_mod.ActorContext(
                user_id="10001",
                role=state_mod.ActorRole.OWNER,
            ),
            session=state_mod.SessionContext(
                session_type=state_mod.SessionType.PRIVATE,
                session_key="private:10001",
            ),
            intent=state_mod.RuntimeIntent.MAIN_AGENT,
        )
        runner = runtime_mod.RootGraphRunner(
            handlers={state_mod.RuntimeIntent.MAIN_AGENT: handler}
        )

        response = asyncio.run(runner.run(runtime_state))

        self.assertTrue(response.should_reply)
        self.assertIn("MainAgentGraph read-only summary", response.text)
        self.assertIn("runtime dev context", runtime_state.artifacts["main_agent_graph"].get("tool_result", ""))
        self.assertEqual(calls, [("recover", True)])
        self.assertEqual(runtime_state.response, response.text)
        self.assertIsNone(runtime_state.error)
        self.assertEqual(runtime_state.artifacts["root_graph"]["route"], "main_agent")
        self.assertTrue(runtime_state.artifacts["root_graph"]["dispatched"])
        self.assertEqual(
            runtime_state.artifacts["main_agent_graph"]["node_trace"],
            tuple(node.value for node in self.main_agent.MAIN_AGENT_NODE_SEQUENCE),
        )
        self.assertIn("metadata", runtime_state.artifacts["main_agent_graph"])

    def test_runtime_handler_passes_qq_context_to_owner_read_tool(self):
        state_mod = self.modules["state"]
        runtime_mod = self.modules["runtime"]
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run")

        async def execute_owner_read_command(command, context):
            calls.append(
                {
                    "command": command,
                    "query": context.query,
                    "message_id": context.metadata["message_id"],
                    "session_key": context.metadata["session_key"],
                    "user_id": context.metadata["user_id"],
                    "actor_role": context.metadata["actor_role"],
                }
            )
            return "最近错误：\n暂无。"

        handler = self.main_agent_bridge.create_read_only_main_agent_runtime_handler(
            retrieve_dev_context=retrieve_dev_context,
            execute_owner_read_command=execute_owner_read_command,
            render_mode="concise",
        )
        runtime_state = state_mod.RuntimeState(
            event=state_mod.EventContext(
                message_id="9005",
                raw_text="/agent 帮我看一下最近错误",
                plain_text="帮我看一下最近错误",
            ),
            actor=state_mod.ActorContext(
                user_id="10001",
                role=state_mod.ActorRole.OWNER,
            ),
            session=state_mod.SessionContext(
                session_type=state_mod.SessionType.PRIVATE,
                session_key="private:10001",
            ),
            intent=state_mod.RuntimeIntent.MAIN_AGENT,
        )
        runner = runtime_mod.RootGraphRunner(
            handlers={state_mod.RuntimeIntent.MAIN_AGENT: handler}
        )

        response = asyncio.run(runner.run(runtime_state))

        self.assertTrue(response.should_reply)
        self.assertIn("最近错误", response.text)
        self.assertEqual(
            calls,
            [
                {
                    "command": "recent_errors",
                    "query": "帮我看一下最近错误",
                    "message_id": "9005",
                    "session_key": "private:10001",
                    "user_id": "10001",
                    "actor_role": "owner",
                }
            ],
        )

    def test_runtime_handler_dispatches_semantic_task_read_tool(self):
        state_mod = self.modules["state"]
        runtime_mod = self.modules["runtime"]
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("dev_context should not run")

        async def execute_agent_task_read(command, reference, context):
            calls.append(
                (
                    command,
                    reference,
                    context.metadata["session_key"],
                    context.metadata["user_id"],
                )
            )
            return "Agent 任务状态：\n暂无任务。"

        handler = self.main_agent_bridge.create_read_only_main_agent_runtime_handler(
            retrieve_dev_context=retrieve_dev_context,
            execute_agent_task_read=execute_agent_task_read,
            render_mode="concise",
        )
        runtime_state = state_mod.RuntimeState(
            event=state_mod.EventContext(
                message_id="9006",
                raw_text="/agent 看看现在任务表",
                plain_text="看看现在任务表",
            ),
            actor=state_mod.ActorContext(
                user_id="10001",
                role=state_mod.ActorRole.OWNER,
            ),
            session=state_mod.SessionContext(
                session_type=state_mod.SessionType.PRIVATE,
                session_key="private:10001",
            ),
            intent=state_mod.RuntimeIntent.MAIN_AGENT,
        )
        runner = runtime_mod.RootGraphRunner(
            handlers={state_mod.RuntimeIntent.MAIN_AGENT: handler}
        )

        response = asyncio.run(runner.run(runtime_state))

        self.assertTrue(response.should_reply)
        self.assertIn("Agent 任务状态", response.text)
        self.assertEqual(calls, [("list_tasks", "", "private:10001", "10001")])

    def test_agent_command_adapter_feeds_root_main_agent_dispatch(self):
        adapters = self.modules["adapters"]
        state_mod = self.modules["state"]
        runtime_mod = self.modules["runtime"]
        calls = []

        async def retrieve_dev_context(query, is_owner):
            calls.append((query, is_owner))
            return "command adapter context"

        runtime_state = adapters.runtime_state_from_main_agent_command(
            "/agent recover through adapter",
            user_id="10001",
            actor_role=state_mod.ActorRole.OWNER,
            session_type=state_mod.SessionType.PRIVATE,
            session_key="private:10001",
            message_id="9003",
        )
        self.assertIsNotNone(runtime_state)
        assert runtime_state is not None
        handler = self.main_agent_bridge.create_read_only_main_agent_runtime_handler(
            retrieve_dev_context=retrieve_dev_context
        )
        runner = runtime_mod.RootGraphRunner(
            handlers={state_mod.RuntimeIntent.MAIN_AGENT: handler}
        )

        response = asyncio.run(runner.run(runtime_state))

        self.assertTrue(response.should_reply)
        self.assertIn("command adapter context", response.text)
        self.assertEqual(calls, [("recover through adapter", True)])
        self.assertEqual(runtime_state.artifacts["root_graph"]["route"], "main_agent")

    def test_bare_agent_command_is_rejected_as_empty_query_without_tool_call(self):
        adapters = self.modules["adapters"]
        state_mod = self.modules["state"]
        runtime_mod = self.modules["runtime"]

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("tool should not run for a bare /agent command")

        runtime_state = adapters.runtime_state_from_main_agent_command(
            "/agent",
            user_id="10001",
            actor_role=state_mod.ActorRole.OWNER,
            session_type=state_mod.SessionType.PRIVATE,
            session_key="private:10001",
            message_id="9004",
        )
        self.assertIsNotNone(runtime_state)
        assert runtime_state is not None
        self.assertEqual(runtime_state.event.raw_text, "/agent")
        self.assertEqual(runtime_state.event.plain_text, "")

        handler = self.main_agent_bridge.create_read_only_main_agent_runtime_handler(
            retrieve_dev_context=retrieve_dev_context
        )
        runner = runtime_mod.RootGraphRunner(
            handlers={state_mod.RuntimeIntent.MAIN_AGENT: handler}
        )

        response = asyncio.run(runner.run(runtime_state))

        self.assertTrue(response.should_reply)
        self.assertIn("Please provide a MainAgentGraph query", response.text)
        self.assertEqual(runtime_state.error, "validation_failed")
        self.assertEqual(
            runtime_state.artifacts["main_agent_graph"]["node_trace"],
            (self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST.value,),
        )

    def test_runtime_handler_denies_non_owner_before_tool(self):
        state_mod = self.modules["state"]
        runtime_mod = self.modules["runtime"]

        async def retrieve_dev_context(_query, _is_owner):
            raise AssertionError("tool should not run for non-owner")

        handler = self.main_agent_bridge.create_read_only_main_agent_runtime_handler(
            retrieve_dev_context=retrieve_dev_context
        )
        runtime_state = state_mod.RuntimeState(
            event=state_mod.EventContext(
                message_id="9002",
                raw_text="/agent recover",
                plain_text="recover",
            ),
            actor=state_mod.ActorContext(
                user_id="20002",
                role=state_mod.ActorRole.USER,
            ),
            session=state_mod.SessionContext(
                session_type=state_mod.SessionType.PRIVATE,
                session_key="private:20002",
            ),
            intent=state_mod.RuntimeIntent.MAIN_AGENT,
        )
        runner = runtime_mod.RootGraphRunner(
            handlers={state_mod.RuntimeIntent.MAIN_AGENT: handler}
        )

        response = asyncio.run(runner.run(runtime_state))

        self.assertTrue(response.should_reply)
        self.assertIn("owner access is required", response.text)
        self.assertEqual(runtime_state.error, "permission_denied")
        self.assertNotIn("main_agent_graph", runtime_state.artifacts)
        self.assertEqual(runtime_state.artifacts["policy"]["decision"], "denied")
        self.assertEqual(runtime_state.artifacts["root_graph"]["route"], "ignore")
        self.assertFalse(runtime_state.artifacts["root_graph"]["dispatched"])


if __name__ == "__main__":
    unittest.main()
