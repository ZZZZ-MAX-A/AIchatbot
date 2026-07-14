from __future__ import annotations

import asyncio
import types
import unittest

from pure_ai_chat_loader import load_pure_graph_modules, load_pure_lc_modules


class GraphContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.chat = cls.modules["chat"]
        cls.diagnostics = cls.modules["diagnostics"]
        cls.dev_context = cls.modules["dev_context"]
        cls.main_agent = cls.modules["main_agent"]
        cls.memory = cls.modules["memory"]
        cls.retrieval = cls.modules["retrieval"]
        cls.notification = cls.modules["notification"]
        cls.root = cls.modules["root"]
        cls.vision = cls.modules["vision"]
        cls.voice = cls.modules["voice"]

    def test_root_node_sequence_keeps_policy_before_dispatch(self):
        sequence = self.root.ROOT_NODE_SEQUENCE

        self.assertEqual(sequence[0], self.root.RootNode.NORMALIZE_EVENT)
        self.assertLess(
            sequence.index(self.root.RootNode.HARD_POLICY_GATE),
            sequence.index(self.root.RootNode.DISPATCH_CAPABILITY),
        )
        self.assertEqual(sequence[-1], self.root.RootNode.RENDER_RESPONSE)

    def test_chat_node_sequence_keeps_prompt_before_agent_and_persist_after_agent(self):
        sequence = self.chat.CHAT_NODE_SEQUENCE

        self.assertLess(
            sequence.index(self.chat.ChatNode.BUILD_PROMPT_CONTEXT),
            sequence.index(self.chat.ChatNode.CALL_CHAT_AGENT),
        )
        self.assertLess(
            sequence.index(self.chat.ChatNode.CALL_CHAT_AGENT),
            sequence.index(self.chat.ChatNode.MAYBE_VOICE_RESPONSE),
        )
        self.assertLess(
            sequence.index(self.chat.ChatNode.MAYBE_VOICE_RESPONSE),
            sequence.index(self.chat.ChatNode.PERSIST_TURN),
        )
        self.assertLess(
            sequence.index(self.chat.ChatNode.PERSIST_TURN),
            sequence.index(self.chat.ChatNode.UPDATE_TRIAL_ACCOUNTING),
        )
        self.assertLess(
            sequence.index(self.chat.ChatNode.UPDATE_TRIAL_ACCOUNTING),
            sequence.index(self.chat.ChatNode.UPDATE_TTS_CANDIDATE),
        )
        self.assertLess(
            sequence.index(self.chat.ChatNode.UPDATE_TTS_CANDIDATE),
            sequence.index(self.chat.ChatNode.SCHEDULE_COMPRESSION),
        )
        self.assertLess(
            sequence.index(self.chat.ChatNode.SCHEDULE_COMPRESSION),
            sequence.index(self.chat.ChatNode.RENDER_RESPONSE),
        )

    def test_memory_context_and_persist_sequences_are_separated(self):
        context_sequence = self.memory.MEMORY_CONTEXT_NODE_SEQUENCE
        persist_sequence = self.memory.MEMORY_PERSIST_NODE_SEQUENCE

        self.assertIn(self.memory.MemoryNode.BUILD_HISTORY, context_sequence)
        self.assertIn(self.memory.MemoryNode.BUILD_MANUAL_MEMORY_CONTEXT, context_sequence)
        self.assertIn(self.memory.MemoryNode.RETRIEVE_SEMANTIC_MEMORY, context_sequence)
        self.assertNotIn(self.memory.MemoryNode.SAVE_USER_MESSAGE, context_sequence)
        self.assertLess(
            context_sequence.index(self.memory.MemoryNode.ENSURE_GAP_SCENE),
            context_sequence.index(self.memory.MemoryNode.BUILD_HISTORY),
        )
        self.assertLess(
            context_sequence.index(self.memory.MemoryNode.BUILD_MANUAL_MEMORY_CONTEXT),
            context_sequence.index(self.memory.MemoryNode.RETRIEVE_SEMANTIC_MEMORY),
        )
        self.assertLess(
            context_sequence.index(self.memory.MemoryNode.RETRIEVE_SEMANTIC_MEMORY),
            context_sequence.index(self.memory.MemoryNode.BUILD_HISTORY),
        )
        self.assertEqual(
            persist_sequence,
            (
                self.memory.MemoryNode.SAVE_USER_MESSAGE,
                self.memory.MemoryNode.SAVE_ASSISTANT_MESSAGE,
                self.memory.MemoryNode.SCHEDULE_COMPRESSION,
            ),
        )

    def test_memory_admin_sequence_validates_before_execute_and_render(self):
        sequence = self.memory.MEMORY_ADMIN_NODE_SEQUENCE

        self.assertEqual(sequence[0], self.memory.MemoryAdminNode.VALIDATE_ADMIN_REQUEST)
        self.assertLess(
            sequence.index(self.memory.MemoryAdminNode.VALIDATE_ADMIN_REQUEST),
            sequence.index(self.memory.MemoryAdminNode.EXECUTE_ADMIN_OPERATION),
        )
        self.assertLess(
            sequence.index(self.memory.MemoryAdminNode.EXECUTE_ADMIN_OPERATION),
            sequence.index(self.memory.MemoryAdminNode.RENDER_ADMIN_REPLY),
        )
        self.assertEqual(sequence[-1], self.memory.MemoryAdminNode.RENDER_ADMIN_REPLY)

    def test_memory_retrieval_sequence_validates_before_execute_and_render(self):
        sequence = self.retrieval.MEMORY_RETRIEVAL_NODE_SEQUENCE

        self.assertEqual(sequence[0], self.retrieval.MemoryRetrievalNode.VALIDATE_RETRIEVAL_REQUEST)
        self.assertLess(
            sequence.index(self.retrieval.MemoryRetrievalNode.VALIDATE_RETRIEVAL_REQUEST),
            sequence.index(self.retrieval.MemoryRetrievalNode.EXECUTE_RETRIEVAL_OPERATION),
        )
        self.assertLess(
            sequence.index(self.retrieval.MemoryRetrievalNode.EXECUTE_RETRIEVAL_OPERATION),
            sequence.index(self.retrieval.MemoryRetrievalNode.RENDER_RETRIEVAL_REPLY),
        )
        self.assertEqual(sequence[-1], self.retrieval.MemoryRetrievalNode.RENDER_RETRIEVAL_REPLY)

    def test_dev_context_sequence_validates_before_retrieve_and_render(self):
        sequence = self.dev_context.DEV_CONTEXT_NODE_SEQUENCE

        self.assertEqual(sequence[0], self.dev_context.DevContextNode.VALIDATE_CONTEXT_REQUEST)
        self.assertLess(
            sequence.index(self.dev_context.DevContextNode.VALIDATE_CONTEXT_REQUEST),
            sequence.index(self.dev_context.DevContextNode.RETRIEVE_COMBINED_CONTEXT),
        )
        self.assertLess(
            sequence.index(self.dev_context.DevContextNode.RETRIEVE_COMBINED_CONTEXT),
            sequence.index(self.dev_context.DevContextNode.RENDER_CONTEXT_ARTIFACT),
        )
        self.assertEqual(sequence[-1], self.dev_context.DevContextNode.RENDER_CONTEXT_ARTIFACT)

    def test_main_agent_sequence_checks_policy_before_execute_and_render(self):
        sequence = self.main_agent.MAIN_AGENT_NODE_SEQUENCE

        self.assertEqual(sequence[0], self.main_agent.MainAgentNode.VALIDATE_AGENT_REQUEST)
        self.assertLess(
            sequence.index(self.main_agent.MainAgentNode.BUILD_AGENT_CONTEXT),
            sequence.index(self.main_agent.MainAgentNode.CALL_MAIN_AGENT),
        )
        self.assertLess(
            sequence.index(self.main_agent.MainAgentNode.CALL_MAIN_AGENT),
            sequence.index(self.main_agent.MainAgentNode.VALIDATE_ACTION_REQUEST),
        )
        self.assertLess(
            sequence.index(self.main_agent.MainAgentNode.VALIDATE_ACTION_REQUEST),
            sequence.index(self.main_agent.MainAgentNode.CHECK_TOOL_POLICY),
        )
        self.assertLess(
            sequence.index(self.main_agent.MainAgentNode.CHECK_TOOL_POLICY),
            sequence.index(self.main_agent.MainAgentNode.EXECUTE_TOOL),
        )
        self.assertLess(
            sequence.index(self.main_agent.MainAgentNode.EXECUTE_TOOL),
            sequence.index(self.main_agent.MainAgentNode.RENDER_AGENT_RESPONSE),
        )
        self.assertEqual(sequence[-1], self.main_agent.MainAgentNode.RENDER_AGENT_RESPONSE)

    def test_vision_node_sequence_describes_before_returning_artifact(self):
        sequence = self.vision.VISION_NODE_SEQUENCE

        self.assertEqual(sequence[0], self.vision.VisionNode.EXTRACT_IMAGE_URLS)
        self.assertLess(
            sequence.index(self.vision.VisionNode.APPLY_IMAGE_CACHE_POLICY),
            sequence.index(self.vision.VisionNode.DESCRIBE_IMAGES),
        )
        self.assertLess(
            sequence.index(self.vision.VisionNode.CHECK_VISION_ACCESS),
            sequence.index(self.vision.VisionNode.DESCRIBE_IMAGES),
        )
        self.assertLess(
            sequence.index(self.vision.VisionNode.DESCRIBE_IMAGES),
            sequence.index(self.vision.VisionNode.SANITIZE_IMAGE_CONTEXT),
        )
        self.assertLess(
            sequence.index(self.vision.VisionNode.SANITIZE_IMAGE_CONTEXT),
            sequence.index(self.vision.VisionNode.RETURN_IMAGE_ARTIFACT),
        )

    def test_voice_node_sequence_checks_policy_before_generating_audio(self):
        sequence = self.voice.VOICE_NODE_SEQUENCE

        self.assertLess(
            sequence.index(self.voice.VoiceNode.CHECK_VOICE_POLICY),
            sequence.index(self.voice.VoiceNode.GENERATE_TTS),
        )
        self.assertEqual(sequence[-1], self.voice.VoiceNode.SEND_PRIVATE_RECORD)

    def test_diagnostics_node_sequence_reads_before_rendering(self):
        sequence = self.diagnostics.DIAGNOSTICS_NODE_SEQUENCE

        self.assertEqual(sequence[0], self.diagnostics.DiagnosticsNode.READ_CONFIG_SNAPSHOT)
        self.assertLess(
            sequence.index(self.diagnostics.DiagnosticsNode.CHECK_TTS_HEALTH),
            sequence.index(self.diagnostics.DiagnosticsNode.RENDER_DIAGNOSTIC_REPLY),
        )
        self.assertLess(
            sequence.index(self.diagnostics.DiagnosticsNode.READ_RECENT_ERRORS),
            sequence.index(self.diagnostics.DiagnosticsNode.RENDER_DIAGNOSTIC_REPLY),
        )
        self.assertEqual(sequence[-1], self.diagnostics.DiagnosticsNode.RENDER_DIAGNOSTIC_REPLY)

    def test_diagnostics_views_have_explicit_minimal_node_sequences(self):
        node = self.diagnostics.DiagnosticsNode
        view = self.diagnostics.DiagnosticsView
        expected = {
            view.FULL: self.diagnostics.DIAGNOSTICS_NODE_SEQUENCE,
            view.CONFIG: (node.READ_CONFIG_SNAPSHOT, node.RENDER_DIAGNOSTIC_REPLY),
            view.VISION: (
                node.READ_CONFIG_SNAPSHOT,
                node.READ_IMAGE_CACHE_STATS,
                node.RENDER_DIAGNOSTIC_REPLY,
            ),
            view.RECENT_ERRORS: (node.READ_RECENT_ERRORS, node.RENDER_DIAGNOSTIC_REPLY),
            view.IMAGE_CACHE: (
                node.READ_CONFIG_SNAPSHOT,
                node.READ_IMAGE_CACHE_STATS,
                node.RENDER_DIAGNOSTIC_REPLY,
            ),
            view.MEMORY: (node.READ_MEMORY_STATS, node.RENDER_DIAGNOSTIC_REPLY),
            view.TTS: (
                node.READ_CONFIG_SNAPSHOT,
                node.CHECK_TTS_HEALTH,
                node.RENDER_DIAGNOSTIC_REPLY,
            ),
        }

        self.assertEqual(set(expected), set(view))
        for selected_view, sequence in expected.items():
            with self.subTest(view=selected_view):
                self.assertEqual(
                    self.diagnostics.diagnostics_node_sequence_for_view(selected_view),
                    sequence,
                )
                self.assertEqual(sequence[-1], node.RENDER_DIAGNOSTIC_REPLY)

    def test_notification_node_sequence_checks_before_sending_owner_message(self):
        sequence = self.notification.NOTIFICATION_NODE_SEQUENCE

        self.assertEqual(sequence[0], self.notification.NotificationNode.CHECK_NOTIFICATION_POLICY)
        self.assertLess(
            sequence.index(self.notification.NotificationNode.CHECK_NOTIFICATION_POLICY),
            sequence.index(self.notification.NotificationNode.SEND_OWNER_PRIVATE_MESSAGE),
        )
        self.assertLess(
            sequence.index(self.notification.NotificationNode.VALIDATE_NOTIFICATION_CONTENT),
            sequence.index(self.notification.NotificationNode.CHECK_NOTIFICATION_COOLDOWN),
        )
        self.assertLess(
            sequence.index(self.notification.NotificationNode.CHECK_NOTIFICATION_COOLDOWN),
            sequence.index(self.notification.NotificationNode.FORMAT_OWNER_NOTIFICATION),
        )
        self.assertLess(
            sequence.index(self.notification.NotificationNode.FORMAT_OWNER_NOTIFICATION),
            sequence.index(self.notification.NotificationNode.SEND_OWNER_PRIVATE_MESSAGE),
        )
        self.assertEqual(sequence[-1], self.notification.NotificationNode.RENDER_SOURCE_REPLY)

    def test_vision_artifact_from_context_freezes_descriptions(self):
        context = self.vision.VisionContext(
            has_image=True,
            has_image_context=True,
            image_urls=["https://example.test/image.png"],
            descriptions=["before"],
            context_text="context",
        )

        artifact = self.vision.vision_artifact_from_context(context)
        context.descriptions.append("after")

        self.assertEqual(artifact.descriptions, ("before",))
        self.assertEqual(artifact.context_text, "context")
        self.assertTrue(artifact.has_image_context)


class LangChainModelFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_lc_modules()
        cls.models = cls.modules["models"]

    def setUp(self) -> None:
        self.calls = []
        self.original_chat_openai = self.models._chat_openai

        def fake_chat_openai(**kwargs):
            self.calls.append(kwargs)
            return {"factory": "chat_openai", "kwargs": kwargs}

        self.models._chat_openai = fake_chat_openai

    def tearDown(self) -> None:
        self.models._chat_openai = self.original_chat_openai

    def test_build_main_llm_uses_main_agent_model_settings(self):
        config = types.SimpleNamespace(
            main_llm_api_key="main-key",
            main_llm_base_url="https://main.example/v1",
            main_llm_model="gpt-main",
            main_llm_timeout_seconds=31,
        )

        llm = self.models.build_main_llm(config)

        self.assertEqual(llm["factory"], "chat_openai")
        self.assertEqual(
            self.calls,
            [
                {
                    "api_key": "main-key",
                    "base_url": "https://main.example/v1",
                    "model": "gpt-main",
                    "timeout": 31,
                }
            ],
        )

    def test_build_chat_llm_uses_chat_agent_model_settings(self):
        config = types.SimpleNamespace(
            chat_llm_api_key="chat-key",
            chat_llm_base_url="https://chat.example/v1",
            chat_llm_model="deepseek-chat",
            chat_llm_timeout_seconds=17,
        )

        llm = self.models.build_chat_llm(config)

        self.assertEqual(llm["factory"], "chat_openai")
        self.assertEqual(
            self.calls,
            [
                {
                    "api_key": "chat-key",
                    "base_url": "https://chat.example/v1",
                    "model": "deepseek-chat",
                    "timeout": 17,
                }
            ],
        )


class LangChainMainAgentAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_lc_modules()
        cls.lc_main_agent = cls.modules["main_agent"]
        cls.graph_main_agent = cls.modules["graph_main_agent"]

    def test_invoke_main_llm_prefers_async_invoke(self):
        calls = []

        class FakeLLM:
            async def ainvoke(self, messages):
                calls.append(("ainvoke", messages))
                return {"content": '{"action":"final_answer","content":"async"}'}

            def invoke(self, _messages):
                raise AssertionError("invoke should not run when ainvoke exists")

        response = asyncio.run(
            self.lc_main_agent.invoke_main_llm(
                FakeLLM(),
                [{"role": "user", "content": "hello"}],
            )
        )

        self.assertEqual(response["content"], '{"action":"final_answer","content":"async"}')
        self.assertEqual(calls[0][0], "ainvoke")
        self.assertIsInstance(calls[0][1], tuple)
        self.assertEqual(calls[0][1][0]["content"], "hello")

    def test_invoke_main_llm_uses_sync_invoke_fallback(self):
        calls = []

        class FakeLLM:
            def invoke(self, messages):
                calls.append(messages)
                return {"content": '{"action":"final_answer","content":"sync"}'}

        response = asyncio.run(
            self.lc_main_agent.invoke_main_llm(
                FakeLLM(),
                [{"role": "user", "content": "hello"}],
            )
        )

        self.assertEqual(response["content"], '{"action":"final_answer","content":"sync"}')
        self.assertEqual(calls[0][0]["role"], "user")

    def test_create_main_llm_call_builds_model_from_config_when_not_provided(self):
        calls = []
        original_build_main_llm = self.lc_main_agent.build_main_llm

        class FakeLLM:
            def invoke(self, messages):
                calls.append(("invoke", messages))
                return {"content": '{"action":"final_answer","content":"built"}'}

        def fake_build_main_llm(config):
            calls.append(("build", config.main_llm_model))
            return FakeLLM()

        self.lc_main_agent.build_main_llm = fake_build_main_llm
        try:
            config = types.SimpleNamespace(main_llm_model="main-model")
            llm_call = self.lc_main_agent.create_main_llm_call(config)
            response = asyncio.run(llm_call([{"role": "user", "content": "hello"}]))
        finally:
            self.lc_main_agent.build_main_llm = original_build_main_llm

        self.assertEqual(response["content"], '{"action":"final_answer","content":"built"}')
        self.assertEqual(calls[0], ("build", "main-model"))
        self.assertEqual(calls[1][0], "invoke")

    def test_lc_call_handler_integrates_real_wrapper_with_main_agent_graph(self):
        state = self.graph_main_agent.MainAgentState(
            query="recover context",
            metadata={"agent_context": "read-only context"},
        )
        calls = []

        class FakeLLM:
            def invoke(self, messages):
                calls.append(messages)
                return {
                    "content": self_graph.dev_context_tool_action_json(
                        "recover context",
                        reason="need context",
                    )
                }

        self_graph = self.graph_main_agent

        def validate_action(agent_state):
            action_request = self_graph.parse_main_agent_action_request(
                agent_state.raw_action_request
            )
            self_graph.apply_action_request_to_state(agent_state, action_request)
            return agent_state

        runner = self_graph.MainAgentGraphRunner(
            call_main_agent=self.lc_main_agent.create_main_agent_lc_call_handler(
                types.SimpleNamespace(main_llm_model="unused"),
                llm=FakeLLM(),
            ),
            validate_action_request=validate_action,
        )

        execution = asyncio.run(runner.run(state))

        self.assertIn("read-only context", calls[0][1]["content"])
        self.assertEqual(execution.result.action, self_graph.MainAgentAction.TOOL_REQUEST.value)
        self.assertEqual(execution.result.requested_tool, self_graph.MainAgentToolName.DEV_CONTEXT.value)

    def test_lc_call_handler_uses_supplied_runtime_tool_registry(self):
        graph_modules = load_pure_graph_modules()
        bridge = graph_modules["main_agent_bridge"]
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            return "context"

        registry = bridge.create_read_only_main_agent_tool_registry(
            retrieve_dev_context,
            execute_owner_write_command=lambda _command, _context: "unused",
        )

        class FakeLLM:
            def invoke(self, messages):
                calls.append(messages)
                return {"content": '{"action":"final_answer","content":"ok"}'}

        handler = self.lc_main_agent.create_main_agent_lc_call_handler(
            types.SimpleNamespace(main_llm_model="unused"),
            llm=FakeLLM(),
            tool_registry=registry,
        )
        state = self.graph_main_agent.MainAgentState(query="帮我写一份 TXT")

        asyncio.run(handler(state))

        system_prompt = calls[0][0]["content"]
        self.assertIn('tool_name "owner_write_command"', system_prompt)
        self.assertIn("create_txt_document", system_prompt)
        self.assertIn("create_word_document", system_prompt)
        self.assertIn("create_presentation", system_prompt)
        self.assertIn('"title": "..."', system_prompt)
        self.assertIn('"content": "..."', system_prompt)
        self.assertNotIn('"path": "..."', system_prompt)

    def test_lc_call_handler_exposes_document_delivery_tool_when_registered(self):
        graph_modules = load_pure_graph_modules()
        bridge = graph_modules["main_agent_bridge"]
        calls = []

        async def retrieve_dev_context(_query, _is_owner):
            return "context"

        registry = bridge.create_read_only_main_agent_tool_registry(
            retrieve_dev_context,
            execute_document_delivery_command=lambda _command, _context: "unused",
        )

        class FakeLLM:
            def invoke(self, messages):
                calls.append(messages)
                return {"content": '{"action":"final_answer","content":"ok"}'}

        handler = self.lc_main_agent.create_main_agent_lc_call_handler(
            types.SimpleNamespace(main_llm_model="unused"),
            llm=FakeLLM(),
            tool_registry=registry,
        )
        state = self.graph_main_agent.MainAgentState(query="生成并发送 TXT")

        asyncio.run(handler(state))

        system_prompt = calls[0][0]["content"]
        self.assertIn('tool_name "document_delivery_command"', system_prompt)
        self.assertIn("create_and_send_txt_document", system_prompt)
        self.assertIn("create_and_send_word_document", system_prompt)
        self.assertIn("create_and_send_presentation", system_prompt)
        self.assertIn('"title": "..."', system_prompt)
        self.assertIn('"content": "..."', system_prompt)
        self.assertNotIn('"path": "..."', system_prompt)

    def test_lc_tool_summary_handler_integrates_real_wrapper(self):
        state = self.graph_main_agent.MainAgentState(
            query="recover context",
            tool_query="recover context",
            tool_result="DevContextGraph result",
            metadata={"agent_context": "read-only context"},
        )
        calls = []

        class FakeLLM:
            def invoke(self, messages):
                calls.append(messages)
                return {"content": "自然总结。"}

        handler = self.lc_main_agent.create_main_agent_tool_summary_lc_handler(
            types.SimpleNamespace(main_llm_model="unused"),
            llm=FakeLLM(),
        )
        result = asyncio.run(handler(state))

        self.assertEqual(result.response_text, "自然总结。")
        self.assertIn("DevContextGraph result", calls[0][1]["content"])

    def test_invoke_main_llm_rejects_non_invokable_object(self):
        with self.assertRaises(self.lc_main_agent.MainAgentLLMInvocationError):
            asyncio.run(self.lc_main_agent.invoke_main_llm(object(), []))


if __name__ == "__main__":
    unittest.main()
