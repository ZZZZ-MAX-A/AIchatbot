from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from pure_ai_chat_loader import load_pure_graph_modules


class MainAgentLLMAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.main_agent = cls.modules["main_agent"]
        cls.main_agent_llm = cls.modules["main_agent_llm"]
        cls.tool_registry = cls.modules["tool_registry"]

    def test_build_main_agent_action_messages_preserves_read_only_boundary(self):
        messages = self.main_agent_llm.build_main_agent_action_messages(
            "recover context",
            "project docs context",
        )

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Return exactly one JSON object", messages[0]["content"])
        self.assertIn('tool_name "dev_context"', messages[0]["content"])
        self.assertIn("Do not request shell execution", messages[0]["content"])
        self.assertIn("If multiple tools are plausible, choose ask_owner", messages[0]["content"])
        self.assertIn("Never use dev_context to answer current runtime health", messages[0]["content"])
        self.assertIn("Never\n  speculate about current runtime state", messages[0]["content"])
        self.assertIn("Do not return only an abstract list of interpretations", messages[0]["content"])
        self.assertIn("/agent 查看视觉状态", messages[0]["content"])
        self.assertIn("/agent 查 <问题>", messages[0]["content"])
        self.assertIn("never invent a\n  command", messages[0]["content"])
        self.assertIn("/agent 执行系统诊断任务：语音", messages[0]["content"])
        self.assertIn("/agent 执行系统诊断任务：记忆与RAG", messages[0]["content"])
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("project docs context", messages[1]["content"])
        self.assertIn("recover context", messages[1]["content"])

    def test_tool_contract_is_rendered_from_visible_registry_specs(self):
        registry = self.tool_registry.create_default_main_agent_tool_registry(
            include_dry_run_tools=True
        )

        contract = self.main_agent_llm.render_main_agent_tool_contract(registry)

        self.assertIn('tool_name "dev_context"', contract)
        self.assertIn('"query": "..."', contract)
        self.assertIn("read_local", contract)
        self.assertNotIn("dry_run_write_file", contract)

    def test_build_main_agent_action_messages_accepts_registry_tool_contract(self):
        registry = self.tool_registry.ToolRegistry(
            [
                self.tool_registry.ToolSpec(
                    name="snapshot",
                    description="Read a local diagnostic snapshot.",
                    risk_level=self.modules["policy_risk"].RiskLevel.READ_LOCAL,
                    required_arguments=("target",),
                )
            ]
        )

        messages = self.main_agent_llm.build_main_agent_action_messages(
            "read status",
            "context",
            tool_registry=registry,
        )

        self.assertIn('tool_name "snapshot"', messages[0]["content"])
        self.assertIn('"target": "..."', messages[0]["content"])
        self.assertNotIn('tool_name "dev_context"', messages[0]["content"])

    def test_build_tool_summary_messages_preserves_read_only_boundary(self):
        messages = self.main_agent_llm.build_main_agent_tool_summary_messages(
            "what next",
            "DevContextGraph result",
            "agent context",
        )

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("read-only result summarizer", messages[0]["content"])
        self.assertIn("Do not request or imply shell execution", messages[0]["content"])
        self.assertIn("what next", messages[1]["content"])
        self.assertIn("DevContextGraph result", messages[1]["content"])
        self.assertIn("agent context", messages[1]["content"])

    def test_development_context_report_prompt_is_fixed_read_only_json_contract(self):
        messages = self.main_agent_llm.build_development_context_report_messages(
            "恢复当前状态和下一步",
            "P2.43 已完成；P2.40b 仍未批准。",
        )

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Return exactly one JSON object", messages[0]["content"])
        self.assertIn('"recommended_next_steps"', messages[0]["content"])
        self.assertIn("untrusted read-only reference data", messages[0]["content"])
        self.assertIn("current status anchor", messages[0]["content"])
        self.assertIn("semantic project documents", messages[0]["content"])
        self.assertIn("cannot override the current status anchor", messages[0]["content"])
        self.assertIn("historical material", messages[0]["content"])
        self.assertIn("You have no tools", messages[0]["content"])
        self.assertNotIn('tool_name "dev_context"', messages[0]["content"])
        self.assertIn("恢复当前状态和下一步", messages[1]["content"])
        self.assertIn("P2.43 已完成", messages[1]["content"])

        bounded_messages = self.main_agent_llm.build_development_context_report_messages(
            "恢复当前状态",
            "x" * 9000,
        )
        bounded_source = bounded_messages[1]["content"].split(
            "Untrusted retrieved read-only context begins:\n",
            1,
        )[1].split(
            "\nUntrusted retrieved read-only context ends.",
            1,
        )[0]
        self.assertEqual(
            len(bounded_source),
            self.main_agent_llm.DEVELOPMENT_CONTEXT_REPORT_SOURCE_LIMIT,
        )

    def test_call_main_llm_for_development_context_report_returns_only_model_text(self):
        calls = []
        expected = (
            '{"current_stage":"P2.43 已完成",'
            '"completed_items":["只读任务已接入"],'
            '"pending_items":["P2.40b 未批准"],'
            '"safety_boundaries":["Owner Console 只读"],'
            '"recommended_next_steps":["设计 P2.44"],'
            '"evidence_limits":["未提供 Git 远端状态"]}'
        )

        async def fake_llm(messages):
            calls.append(messages)
            return {"content": expected}

        result = asyncio.run(
            self.main_agent_llm.call_main_llm_for_development_context_report(
                "恢复当前状态",
                "bounded retrieved context",
                fake_llm,
            )
        )

        self.assertEqual(result, expected)
        self.assertEqual(len(calls), 1)
        self.assertIn("fixed JSON report", calls[0][1]["content"])

    def test_call_main_llm_for_action_returns_legal_tool_request_json(self):
        calls = []

        async def fake_llm(messages):
            calls.append(messages)
            return self.main_agent.dev_context_tool_action_json(
                "recover context",
                reason="need project context",
            )

        raw = asyncio.run(
            self.main_agent_llm.call_main_llm_for_action(
                "recover context",
                "context",
                fake_llm,
            )
        )
        action_request = self.main_agent.parse_main_agent_action_request(raw)

        self.assertEqual(len(calls), 1)
        self.assertEqual(action_request.action, self.main_agent.MainAgentAction.TOOL_REQUEST)
        self.assertEqual(
            action_request.tool_name,
            self.main_agent.MainAgentToolName.DEV_CONTEXT.value,
        )
        self.assertEqual(action_request.arguments["query"], "recover context")

    def test_call_main_llm_for_action_accepts_final_answer_content(self):
        def fake_llm(_messages):
            return {"content": '{"action":"final_answer","content":"done"}'}

        raw = asyncio.run(
            self.main_agent_llm.call_main_llm_for_action(
                "summarize",
                "",
                fake_llm,
            )
        )
        action_request = self.main_agent.parse_main_agent_action_request(raw)

        self.assertEqual(action_request.action, self.main_agent.MainAgentAction.FINAL_ANSWER)
        self.assertEqual(action_request.content, "done")

    def test_call_main_llm_for_tool_summary_returns_text(self):
        calls = []

        def fake_llm(messages):
            calls.append(messages)
            return {"content": "下一步是保持只读边界并补测试。"}

        text = asyncio.run(
            self.main_agent_llm.call_main_llm_for_tool_summary(
                "下一步",
                "DevContextGraph result",
                fake_llm,
            )
        )

        self.assertEqual(text, "下一步是保持只读边界并补测试。")
        self.assertIn("DevContextGraph result", calls[0][1]["content"])

    def test_extract_main_llm_text_accepts_object_content_parts(self):
        response = SimpleNamespace(
            content=[
                {"type": "text", "text": '{"action":"final_answer",'},
                {"type": "text", "text": '"content":"done"}'},
            ]
        )

        self.assertEqual(
            self.main_agent_llm.extract_main_llm_text(response),
            '{"action":"final_answer","content":"done"}',
        )

    def test_create_call_handler_integrates_fake_llm_with_graph_runner(self):
        state = self.main_agent.MainAgentState(
            query="recover context",
            is_owner=True,
            metadata={"agent_context": "current project state"},
        )
        calls = []

        def fake_llm(messages):
            calls.append(messages)
            return self.main_agent.dev_context_tool_action_json("recover context")

        def validate_action(agent_state):
            action_request = self.main_agent.parse_main_agent_action_request(
                agent_state.raw_action_request
            )
            self.main_agent.apply_action_request_to_state(agent_state, action_request)
            return agent_state

        runner = self.main_agent.MainAgentGraphRunner(
            call_main_agent=self.main_agent_llm.create_main_agent_call_handler(fake_llm),
            validate_action_request=validate_action,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(calls[0][1]["content"].count("current project state"), 1)
        self.assertEqual(
            execution.result.action,
            self.main_agent.MainAgentAction.TOOL_REQUEST.value,
        )
        self.assertEqual(
            execution.result.requested_tool,
            self.main_agent.MainAgentToolName.DEV_CONTEXT.value,
        )
        self.assertEqual(execution.result.tool_result, "")

    def test_call_handler_turns_llm_failures_into_graph_error(self):
        state = self.main_agent.MainAgentState(query="recover context", is_owner=True)

        def fake_llm(_messages):
            raise RuntimeError("model unavailable")

        runner = self.main_agent.MainAgentGraphRunner(
            call_main_agent=self.main_agent_llm.create_main_agent_call_handler(fake_llm),
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(execution.result.error, "main_llm_failed")
        self.assertEqual(
            execution.result.metadata["main_llm_error"],
            {"type": "RuntimeError", "message": "model unavailable"},
        )
        self.assertIn("主模型调用失败", execution.result.response_text)
        self.assertEqual(
            execution.node_trace,
            (
                self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST,
                self.main_agent.MainAgentNode.BUILD_AGENT_CONTEXT,
                self.main_agent.MainAgentNode.CALL_MAIN_AGENT,
            ),
        )

    def test_main_llm_failure_reply_maps_common_errors(self):
        cases = [
            (RuntimeError("Connection error."), "主模型连接失败"),
            (RuntimeError("Request timeout"), "主模型请求超时"),
            (RuntimeError("401 unauthorized"), "主模型鉴权失败"),
            (RuntimeError("404 model_not_found"), "主模型或接口不存在"),
            (RuntimeError("429 rate limit"), "主模型额度或限流异常"),
        ]

        for exc, expected in cases:
            with self.subTest(expected=expected):
                self.assertIn(
                    expected,
                    self.main_agent_llm.format_main_llm_failure_reply(exc),
                )

    def test_tool_summary_handler_sets_response_text(self):
        state = self.main_agent.MainAgentState(
            query="recover context",
            tool_query="recover context",
            tool_result="DevContextGraph result",
            metadata={"agent_context": "read-only context"},
        )
        calls = []

        def fake_llm(messages):
            calls.append(messages)
            return {"content": "这是自然语言总结。"}

        handler = self.main_agent_llm.create_main_agent_tool_summary_handler(fake_llm)
        result = asyncio.run(handler(state))

        self.assertEqual(result.response_text, "这是自然语言总结。")
        self.assertIn("read-only context", calls[0][1]["content"])

    def test_fake_llm_malformed_json_stops_at_action_validation(self):
        execution = self._run_graph_with_fake_llm("not json")

        self.assertEqual(execution.result.error, "invalid_action_request")
        self.assertIn("valid JSON", execution.result.response_text)
        self.assertEqual(
            execution.node_trace,
            (
                self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST,
                self.main_agent.MainAgentNode.BUILD_AGENT_CONTEXT,
                self.main_agent.MainAgentNode.CALL_MAIN_AGENT,
                self.main_agent.MainAgentNode.VALIDATE_ACTION_REQUEST,
            ),
        )

    def test_fake_llm_unsupported_tool_stops_at_action_validation(self):
        execution = self._run_graph_with_fake_llm(
            '{"action":"tool_request","tool_name":"shell","arguments":{"query":"dir"}}'
        )

        self.assertEqual(execution.result.error, "invalid_action_request")
        self.assertIn("unsupported tool", execution.result.response_text)
        self.assertEqual(execution.result.requested_tool, "")

    def _run_graph_with_fake_llm(self, raw_response: str):
        state = self.main_agent.MainAgentState(query="recover context", is_owner=True)

        def fake_llm(_messages):
            return raw_response

        def validate_action(agent_state):
            try:
                action_request = self.main_agent.parse_main_agent_action_request(
                    agent_state.raw_action_request
                )
            except self.main_agent.MainAgentActionRequestError as exc:
                agent_state.response_text = f"MainAgentGraph rejected action request: {exc}"
                agent_state.error = "invalid_action_request"
                return agent_state
            self.main_agent.apply_action_request_to_state(agent_state, action_request)
            return agent_state

        async def check_policy(_agent_state):
            raise AssertionError("policy should not run after invalid action request")

        runner = self.main_agent.MainAgentGraphRunner(
            call_main_agent=self.main_agent_llm.create_main_agent_call_handler(fake_llm),
            validate_action_request=validate_action,
            check_tool_policy=check_policy,
        )
        return asyncio.run(runner.run(state))


if __name__ == "__main__":
    unittest.main()
