from __future__ import annotations

import asyncio
import unittest

from pure_ai_chat_loader import load_pure_graph_modules


class RootGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.state = cls.modules["state"]
        cls.root = cls.modules["root"]
        cls.runtime = cls.modules["runtime"]

    def make_runtime_state(self, *, intent=None, response: str | None = None):
        return self.state.RuntimeState(
            event=self.state.EventContext(
                message_id="9001",
                raw_text="hello",
                plain_text="hello",
            ),
            actor=self.state.ActorContext(
                user_id="10001",
                role=self.state.ActorRole.OWNER,
            ),
            session=self.state.SessionContext(
                session_type=self.state.SessionType.PRIVATE,
                session_key="private:10001",
            ),
            intent=intent,
            response=response,
        )

    def test_root_graph_runner_dispatches_chat_intent_to_registered_handler(self):
        calls = []
        state = self.make_runtime_state(intent=self.state.RuntimeIntent.CHAT)

        async def chat_handler(runtime_state):
            calls.append(runtime_state)
            return self.runtime.RuntimeResponse("chat reply")

        runner = self.runtime.RootGraphRunner(
            handlers={self.state.RuntimeIntent.CHAT: chat_handler}
        )

        response = asyncio.run(runner.run(state))

        self.assertEqual(response.text, "chat reply")
        self.assertTrue(response.should_reply)
        self.assertEqual(calls, [state])
        self.assertEqual(
            state.artifacts["root_graph"]["node_trace"],
            tuple(node.value for node in self.root.ROOT_NODE_SEQUENCE),
        )
        self.assertEqual(state.artifacts["root_graph"]["route"], "chat")
        self.assertTrue(state.artifacts["root_graph"]["dispatched"])

    def test_root_graph_runner_ignores_missing_intent_without_dispatching(self):
        state = self.make_runtime_state(intent=None)
        runner = self.runtime.RootGraphRunner(
            handlers={
                self.state.RuntimeIntent.CHAT: lambda _: self.runtime.RuntimeResponse("unused")
            }
        )

        response = asyncio.run(runner.run(state))

        self.assertFalse(response.should_reply)
        self.assertEqual(response.text, "")
        self.assertEqual(state.artifacts["root_graph"]["route"], "ignore")
        self.assertFalse(state.artifacts["root_graph"]["dispatched"])

    def test_agent_runtime_uses_root_runner_and_preserves_existing_response_fallback(self):
        state = self.make_runtime_state(
            intent=self.state.RuntimeIntent.CHAT,
            response="already rendered",
        )

        response = asyncio.run(self.runtime.AgentRuntime().run(state))

        self.assertEqual(response.text, "already rendered")
        self.assertTrue(response.should_reply)
        self.assertEqual(state.artifacts["root_graph"]["route"], "chat")


class ChatGraphRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.contracts = cls.modules["contracts"]
        cls.state = cls.modules["state"]
        cls.chat = cls.modules["chat"]
        cls.adapters = cls.modules["adapters"]

    def make_chat_state(self, *, semantic_voice: bool = False, text: str = "hello"):
        request = self.contracts.ChatRequest(
            key="private:10001",
            text=text,
            image_context=self.contracts.ChatImageContext(urls=[], has_context=False),
        )
        runtime = self.adapters.runtime_state_from_chat_request(
            request,
            user_id="10001",
            actor_role=self.state.ActorRole.OWNER,
            session_type=self.state.SessionType.PRIVATE,
            message_id="9001",
        )
        options = self.contracts.ChatOptions(
            semantic_voice=semantic_voice,
            semantic_goal="say it aloud" if semantic_voice else "",
            tts_refresh_cache=semantic_voice,
        )
        return self.adapters.chat_state_from_chat_request(runtime, request, options)

    def test_chat_graph_runner_calls_agent_persists_turn_and_renders_result(self):
        state = self.make_chat_state()
        persisted = self.modules["memory"].PersistedTurn(
            session_key="private:10001",
            user_content="hello",
            assistant_content="reply",
            message_type="private",
            user_id="10001",
            group_id=None,
        )
        agent_calls = []
        persist_calls = []

        async def call_chat_agent(chat_state):
            agent_calls.append(chat_state)
            return self.contracts.ChatRuntimeResult(
                reply="reply",
                stored_assistant="reply",
            )

        async def persist_turn(chat_state, runtime_result):
            persist_calls.append((chat_state, runtime_result))
            return persisted

        runner = self.chat.ChatGraphRunner(
            call_chat_agent,
            persist_turn=persist_turn,
        )

        execution = asyncio.run(runner.run(state))

        self.assertEqual(agent_calls, [state])
        self.assertEqual(len(persist_calls), 1)
        self.assertEqual(execution.node_trace, self.chat.CHAT_NODE_SEQUENCE)
        self.assertEqual(execution.result.reply, "reply")
        self.assertTrue(execution.result.should_reply_text)
        self.assertIs(execution.result.persisted_turn, persisted)
        self.assertEqual(execution.state.runtime.response, "reply")
        self.assertEqual(execution.state.runtime.artifacts["chat_graph"]["status"], "complete")
        self.assertEqual(
            execution.state.runtime.artifacts["chat_graph"]["node_trace"],
            tuple(node.value for node in self.chat.CHAT_NODE_SEQUENCE),
        )

    def test_chat_graph_runner_suppresses_text_reply_for_semantic_voice_mode(self):
        state = self.make_chat_state(semantic_voice=True)

        async def call_chat_agent(_):
            return self.contracts.ChatRuntimeResult(
                reply="spoken reply",
                stored_assistant="spoken reply",
                voice_text="spoken reply",
            )

        execution = asyncio.run(self.chat.ChatGraphRunner(call_chat_agent).run(state))

        self.assertFalse(execution.result.should_reply_text)
        self.assertEqual(execution.result.voice_text, "spoken reply")
        self.assertEqual(execution.state.voice_text, "spoken reply")

    def test_chat_graph_runner_rejects_empty_input_before_agent_call(self):
        state = self.make_chat_state(text="")

        async def call_chat_agent(_):
            raise AssertionError("agent should not be called")

        execution = asyncio.run(self.chat.ChatGraphRunner(call_chat_agent).run(state))

        self.assertFalse(execution.result.should_reply_text)
        self.assertEqual(execution.result.reply, "")
        self.assertEqual(execution.node_trace, (self.chat.ChatNode.VALIDATE_INPUT,))
        self.assertEqual(execution.state.runtime.error, "chat input is empty")
        self.assertEqual(execution.state.runtime.artifacts["chat_graph"]["status"], "invalid")


if __name__ == "__main__":
    unittest.main()
