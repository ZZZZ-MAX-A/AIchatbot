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
