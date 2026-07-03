from __future__ import annotations

import asyncio
import unittest

from pure_ai_chat_loader import load_pure_graph_modules


class MainAgentReadOnlyBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.main_agent = cls.modules["main_agent"]
        cls.main_agent_bridge = cls.modules["main_agent_bridge"]
        cls.policy_risk = cls.modules["policy_risk"]
        cls.tool_registry = cls.modules["tool_registry"]

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
        self.assertTrue(registry.require("dry_run_write_file").requires_approval)
        self.assertFalse(registry.require("dry_run_write_file").llm_visible)

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
        self.assertEqual(
            runtime_state.artifacts["main_agent_graph"]["node_trace"],
            (self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST.value,),
        )


if __name__ == "__main__":
    unittest.main()
