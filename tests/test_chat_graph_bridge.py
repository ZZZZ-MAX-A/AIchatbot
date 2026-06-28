from __future__ import annotations

import asyncio
import unittest

from pure_ai_chat_loader import load_pure_graph_modules


class ChatGraphBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.bridge = cls.modules["bridge"]
        cls.contracts = cls.modules["contracts"]
        cls.state = cls.modules["state"]
        cls.adapters = cls.modules["adapters"]
        cls.chat = cls.modules["chat"]

    def make_inputs(self, *, semantic_voice: bool = False):
        request = self.contracts.ChatRequest(
            key="private:10001",
            text="hello",
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
        state = self.adapters.chat_state_from_chat_request(runtime, request, options)
        prompt_context = self.contracts.ChatPromptContext(
            history=[{"role": "system", "content": "policy"}],
            user_id="10001",
            group_id=None,
        )
        user_content = self.contracts.ChatUserContent(
            original="hello",
            for_llm="hello for llm",
            stored="hello stored",
        )
        return request, options, state, prompt_context, user_content

    def test_run_chat_graph_tail_calls_agent_and_builds_persisted_turn(self):
        request, options, state, prompt_context, user_content = self.make_inputs()
        calls = []

        async def call_chat_agent(chat_state):
            calls.append(chat_state)
            return self.contracts.ChatRuntimeResult(
                reply="reply",
                stored_assistant="stored reply",
            )

        result = asyncio.run(
            self.bridge.run_chat_graph_tail(
                state,
                request=request,
                options=options,
                prompt_context=prompt_context,
                user_content=user_content,
                message_type="private",
                call_chat_agent=call_chat_agent,
                llm_user_content="wrapped user",
            )
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.runtime_result.reply, "reply")
        self.assertEqual(result.execution.result.reply, "reply")
        self.assertTrue(result.execution.result.should_reply_text)
        self.assertEqual(result.execution.state.llm_user_content, "wrapped user")
        self.assertEqual(result.execution.state.runtime.artifacts["chat_graph"]["status"], "complete")
        persisted = result.execution.result.persisted_turn
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.session_key, "private:10001")
        self.assertEqual(persisted.user_content, "hello stored")
        self.assertEqual(persisted.assistant_content, "stored reply")
        self.assertEqual(persisted.message_type, "private")
        self.assertEqual(calls[0].llm_user_content, "wrapped user")

    def test_run_chat_graph_tail_returns_none_when_agent_returns_none(self):
        request, options, state, prompt_context, user_content = self.make_inputs()

        async def call_chat_agent(_):
            return None

        result = asyncio.run(
            self.bridge.run_chat_graph_tail(
                state,
                request=request,
                options=options,
                prompt_context=prompt_context,
                user_content=user_content,
                message_type="private",
                call_chat_agent=call_chat_agent,
            )
        )

        self.assertIsNone(result)

    def test_run_chat_graph_tail_preserves_semantic_voice_result_shape(self):
        request, options, state, prompt_context, user_content = self.make_inputs(semantic_voice=True)

        async def call_chat_agent(_):
            return self.contracts.ChatRuntimeResult(
                reply="spoken",
                stored_assistant="spoken",
                voice_text="spoken",
            )

        result = asyncio.run(
            self.bridge.run_chat_graph_tail(
                state,
                request=request,
                options=options,
                prompt_context=prompt_context,
                user_content=user_content,
                message_type="private",
                call_chat_agent=call_chat_agent,
            )
        )

        self.assertIsNotNone(result)
        self.assertFalse(result.execution.result.should_reply_text)
        self.assertEqual(result.execution.result.voice_text, "spoken")

    def test_run_chat_graph_session_builds_prompt_inside_graph(self):
        request, options, state, _, _ = self.make_inputs()
        calls = []

        async def resolve_image_context(chat_state):
            calls.append(("resolve", chat_state.text))
            return self.adapters.chat_state_with_vision_result(
                chat_state,
                descriptions=["image description"],
                context_text="image context",
            )

        async def build_prompt_context(chat_state):
            calls.append(("prompt", tuple(chat_state.vision.descriptions)))
            prompt_context = self.contracts.ChatPromptContext(
                history=[{"role": "system", "content": "policy"}],
                user_id="10001",
                group_id=None,
            )
            user_content = self.contracts.ChatUserContent(
                original="hello",
                for_llm="hello for llm",
                stored="hello stored",
            )
            prompted = self.adapters.chat_state_with_prompt_context(
                chat_state,
                prompt_context,
                user_content,
                llm_user_content="wrapped user",
            )
            return self.bridge.ChatGraphPromptBundle(
                state=prompted,
                prompt_context=prompt_context,
                user_content=user_content,
            )

        async def call_chat_agent(chat_state, prompt_context, user_content):
            calls.append(("agent", chat_state.llm_user_content, prompt_context.user_id, user_content.stored))
            return self.contracts.ChatRuntimeResult(
                reply="reply",
                stored_assistant="stored reply",
            )

        result = asyncio.run(
            self.bridge.run_chat_graph_session(
                state,
                request=request,
                options=options,
                message_type="private",
                call_chat_agent=call_chat_agent,
                build_prompt_context=build_prompt_context,
                resolve_image_context=resolve_image_context,
            )
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            calls,
            [
                ("resolve", "hello"),
                ("prompt", ("image description",)),
                ("agent", "wrapped user", "10001", "hello stored"),
            ],
        )
        self.assertEqual(result.runtime_result.reply, "reply")
        self.assertEqual(result.prompt_context.user_id, "10001")
        self.assertEqual(result.user_content.stored, "hello stored")
        persisted = result.execution.result.persisted_turn
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.assistant_content, "stored reply")

    def test_run_chat_graph_session_returns_none_when_prompt_build_stops(self):
        request, options, state, _, _ = self.make_inputs()
        agent_called = False

        async def build_prompt_context(_):
            return None

        async def call_chat_agent(*_):
            nonlocal agent_called
            agent_called = True
            return self.contracts.ChatRuntimeResult("reply", "reply")

        result = asyncio.run(
            self.bridge.run_chat_graph_session(
                state,
                request=request,
                options=options,
                message_type="private",
                call_chat_agent=call_chat_agent,
                build_prompt_context=build_prompt_context,
            )
        )

        self.assertIsNone(result)
        self.assertFalse(agent_called)

    def test_run_chat_graph_session_marks_agent_exception_committed(self):
        request, options, state, _, _ = self.make_inputs()

        async def build_prompt_context(chat_state):
            prompt_context = self.contracts.ChatPromptContext(
                history=[{"role": "system", "content": "policy"}],
                user_id="10001",
                group_id=None,
            )
            user_content = self.contracts.ChatUserContent(
                original="hello",
                for_llm="hello for llm",
                stored="hello stored",
            )
            prompted = self.adapters.chat_state_with_prompt_context(
                chat_state,
                prompt_context,
                user_content,
                llm_user_content="wrapped user",
            )
            return self.bridge.ChatGraphPromptBundle(
                state=prompted,
                prompt_context=prompt_context,
                user_content=user_content,
            )

        async def call_chat_agent(*_):
            raise RuntimeError("agent failed")

        with self.assertRaises(self.bridge.ChatGraphSessionCommittedError) as raised:
            asyncio.run(
                self.bridge.run_chat_graph_session(
                    state,
                    request=request,
                    options=options,
                    message_type="private",
                    call_chat_agent=call_chat_agent,
                    build_prompt_context=build_prompt_context,
                )
            )

        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
        self.assertEqual(str(raised.exception.__cause__), "agent failed")


if __name__ == "__main__":
    unittest.main()
