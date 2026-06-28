from __future__ import annotations

import types
import unittest

from pure_ai_chat_loader import load_pure_graph_modules, load_pure_lc_modules


class GraphContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_graph_modules()
        cls.chat = cls.modules["chat"]
        cls.memory = cls.modules["memory"]
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
        self.assertNotIn(self.memory.MemoryNode.SAVE_USER_MESSAGE, context_sequence)
        self.assertEqual(
            persist_sequence,
            (
                self.memory.MemoryNode.SAVE_USER_MESSAGE,
                self.memory.MemoryNode.SAVE_ASSISTANT_MESSAGE,
                self.memory.MemoryNode.SCHEDULE_COMPRESSION,
            ),
        )

    def test_vision_node_sequence_describes_before_returning_artifact(self):
        sequence = self.vision.VISION_NODE_SEQUENCE

        self.assertEqual(sequence[0], self.vision.VisionNode.EXTRACT_IMAGE_URLS)
        self.assertLess(
            sequence.index(self.vision.VisionNode.DESCRIBE_IMAGES),
            sequence.index(self.vision.VisionNode.RETURN_IMAGE_ARTIFACT),
        )

    def test_voice_node_sequence_checks_policy_before_generating_audio(self):
        sequence = self.voice.VOICE_NODE_SEQUENCE

        self.assertLess(
            sequence.index(self.voice.VoiceNode.CHECK_VOICE_POLICY),
            sequence.index(self.voice.VoiceNode.GENERATE_TTS),
        )
        self.assertEqual(sequence[-1], self.voice.VoiceNode.SEND_PRIVATE_RECORD)

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


if __name__ == "__main__":
    unittest.main()
