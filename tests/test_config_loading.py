from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from pure_ai_chat_loader import load_pure_lc_modules


class ConfigLoadingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_pure_lc_modules()
        cls.config_module = cls.modules["config"]

    def load_with_env(self, env: dict[str, str]):
        with patch.dict(os.environ, env, clear=True):
            return self.config_module.load_config()

    def test_defaults_keep_main_agent_disabled_and_chat_model_on_legacy_provider(self):
        config = self.load_with_env({})

        self.assertFalse(config.enable_main_agent)
        self.assertEqual(config.bot_timezone, "Asia/Shanghai")
        self.assertFalse(config.main_agent_use_llm)
        self.assertTrue(config.main_agent_owner_only)
        self.assertFalse(config.main_agent_allow_group)
        self.assertTrue(config.main_agent_require_approval_for_writes)
        self.assertFalse(config.enable_agent_web)
        self.assertEqual(config.tavily_api_key, "")
        self.assertEqual(config.tavily_timeout_seconds, 10)
        self.assertFalse(config.enable_agent_local_write)
        self.assertFalse(config.enable_agent_external_write)
        self.assertFalse(config.enable_agent_shell)
        self.assertFalse(config.enable_chat_graph_runtime)
        self.assertEqual(config.main_llm_base_url, "https://api.openai.com/v1")
        self.assertEqual(config.main_llm_model, "gpt-4.1-mini")
        self.assertEqual(config.chat_llm_base_url, "https://api.deepseek.com")
        self.assertEqual(config.chat_llm_model, "deepseek-v4-flash")
        self.assertEqual(config.chat_llm_timeout_seconds, config.ai_timeout_seconds)
        self.assertFalse(config.enable_memory_rag)
        self.assertFalse(config.enable_project_doc_rag)
        self.assertEqual(config.memory_rag_embedding_provider, "ollama")
        self.assertEqual(config.memory_rag_embedding_model, "bge-m3")
        self.assertEqual(config.memory_rag_embedding_base_url, "http://127.0.0.1:11434")
        self.assertEqual(config.memory_rag_top_k, 5)
        self.assertEqual(config.memory_rag_min_score, 0.55)
        self.assertEqual(config.project_doc_rag_top_k, 4)
        self.assertEqual(config.project_doc_rag_min_score, 0.50)
        self.assertTrue(config.memory_rag_include_manual_facts)
        self.assertTrue(config.memory_rag_include_manual_preferences)
        self.assertTrue(config.memory_rag_include_session_summaries)
        self.assertFalse(config.memory_rag_include_short_messages)
        self.assertFalse(config.memory_rag_include_gap_scene_summaries)
        self.assertTrue(config.memory_rag_owner_only_debug)
        self.assertFalse(config.memory_rag_inject_in_chat)

    def test_chat_llm_falls_back_to_legacy_openai_compatible_settings(self):
        config = self.load_with_env(
            {
                "OPENAI_API_KEY": "legacy-key",
                "OPENAI_BASE_URL": "https://legacy.example/v1",
                "OPENAI_MODEL": "legacy-chat",
                "AI_TIMEOUT_SECONDS": "33",
            }
        )

        self.assertEqual(config.chat_llm_api_key, "legacy-key")
        self.assertEqual(config.chat_llm_base_url, "https://legacy.example/v1")
        self.assertEqual(config.chat_llm_model, "legacy-chat")
        self.assertEqual(config.chat_llm_timeout_seconds, 33)

    def test_chat_llm_overrides_do_not_change_main_llm_settings(self):
        config = self.load_with_env(
            {
                "MAIN_LLM_API_KEY": "main-key",
                "MAIN_LLM_BASE_URL": "https://main.example/v1",
                "MAIN_LLM_MODEL": "main-model",
                "MAIN_LLM_TIMEOUT_SECONDS": "44",
                "CHAT_LLM_API_KEY": "chat-key",
                "CHAT_LLM_BASE_URL": "https://chat.example/v1",
                "CHAT_LLM_MODEL": "chat-model",
                "CHAT_LLM_TIMEOUT_SECONDS": "22",
            }
        )

        self.assertEqual(config.main_llm_api_key, "main-key")
        self.assertEqual(config.main_llm_base_url, "https://main.example/v1")
        self.assertEqual(config.main_llm_model, "main-model")
        self.assertEqual(config.main_llm_timeout_seconds, 44)
        self.assertEqual(config.chat_llm_api_key, "chat-key")
        self.assertEqual(config.chat_llm_base_url, "https://chat.example/v1")
        self.assertEqual(config.chat_llm_model, "chat-model")
        self.assertEqual(config.chat_llm_timeout_seconds, 22)
        config_repr = repr(config)
        self.assertNotIn("main-key", config_repr)
        self.assertNotIn("chat-key", config_repr)

    def test_invalid_tavily_timeout_loads_fail_closed_sentinel(self):
        config = self.load_with_env(
            {
                "ENABLE_AGENT_WEB": "true",
                "TAVILY_API_KEY": "tvly-unit-secret",
                "TAVILY_TIMEOUT_SECONDS": "not-a-number",
            }
        )

        self.assertTrue(config.enable_agent_web)
        self.assertEqual(config.tavily_timeout_seconds, 0)
        self.assertNotIn("tvly-unit-secret", repr(config))

    def test_bot_timezone_is_fixed_to_supported_china_standard_time(self):
        configured = self.load_with_env({"BOT_TIMEZONE": "Asia/Shanghai"})
        self.assertEqual(configured.bot_timezone, "Asia/Shanghai")

        with self.assertRaisesRegex(ValueError, "unsupported bot timezone"):
            self.load_with_env({"BOT_TIMEZONE": "UTC"})

    def test_boolean_numeric_and_csv_env_values_are_parsed(self):
        config = self.load_with_env(
            {
                "ENABLE_MAIN_AGENT": "yes",
                "MAIN_AGENT_USE_LLM": "true",
                "MAIN_AGENT_OWNER_ONLY": "false",
                "MAIN_AGENT_ALLOW_GROUP": "on",
                "MAIN_AGENT_MAX_STEPS": "9",
                "MAIN_AGENT_REQUIRE_APPROVAL_FOR_WRITES": "0",
                "ENABLE_AGENT_WEB": "true",
                "TAVILY_API_KEY": "tvly-unit-secret",
                "TAVILY_TIMEOUT_SECONDS": "7",
                "ENABLE_AGENT_LOCAL_WRITE": "1",
                "ENABLE_AGENT_EXTERNAL_WRITE": "yes",
                "ENABLE_AGENT_SHELL": "on",
                "ENABLE_CHAT_GRAPH_RUNTIME": "true",
                "ENABLE_MEMORY_RAG": "true",
                "ENABLE_PROJECT_DOC_RAG": "yes",
                "MEMORY_RAG_EMBEDDING_PROVIDER": "unit",
                "MEMORY_RAG_EMBEDDING_MODEL": "toy",
                "MEMORY_RAG_EMBEDDING_BASE_URL": "http://127.0.0.1:9999",
                "MEMORY_RAG_EMBEDDING_DIMENSION": "3",
                "MEMORY_RAG_EMBEDDING_TIMEOUT_SECONDS": "7",
                "MEMORY_RAG_TOP_K": "6",
                "MEMORY_RAG_MIN_SCORE": "0.45",
                "MEMORY_RAG_MAX_CONTEXT_CHARS": "700",
                "PROJECT_DOC_RAG_TOP_K": "8",
                "PROJECT_DOC_RAG_MIN_SCORE": "0.40",
                "PROJECT_DOC_RAG_MAX_CONTEXT_CHARS": "900",
                "MEMORY_RAG_INCLUDE_MANUAL_FACTS": "0",
                "MEMORY_RAG_INCLUDE_MANUAL_PREFERENCES": "false",
                "MEMORY_RAG_INCLUDE_SESSION_SUMMARIES": "off",
                "MEMORY_RAG_INCLUDE_SHORT_MESSAGES": "on",
                "MEMORY_RAG_INCLUDE_GAP_SCENE_SUMMARIES": "1",
                "MEMORY_RAG_OWNER_ONLY_DEBUG": "no",
                "MEMORY_RAG_INJECT_IN_CHAT": "yes",
                "AI_TEMPERATURE": "0.25",
                "PRIVATE_WHITELIST": "10001, 10002,10001,,",
                "GROUP_WHITELIST": "42, 43",
                "USER_BLACKLIST": "90001,90002",
            }
        )

        self.assertTrue(config.enable_main_agent)
        self.assertTrue(config.main_agent_use_llm)
        self.assertFalse(config.main_agent_owner_only)
        self.assertTrue(config.main_agent_allow_group)
        self.assertEqual(config.main_agent_max_steps, 9)
        self.assertFalse(config.main_agent_require_approval_for_writes)
        self.assertTrue(config.enable_agent_web)
        self.assertEqual(config.tavily_api_key, "tvly-unit-secret")
        self.assertEqual(config.tavily_timeout_seconds, 7)
        self.assertNotIn("tvly-unit-secret", repr(config))
        self.assertTrue(config.enable_agent_local_write)
        self.assertTrue(config.enable_agent_external_write)
        self.assertTrue(config.enable_agent_shell)
        self.assertTrue(config.enable_chat_graph_runtime)
        self.assertTrue(config.enable_memory_rag)
        self.assertTrue(config.enable_project_doc_rag)
        self.assertEqual(config.memory_rag_embedding_provider, "unit")
        self.assertEqual(config.memory_rag_embedding_model, "toy")
        self.assertEqual(config.memory_rag_embedding_base_url, "http://127.0.0.1:9999")
        self.assertEqual(config.memory_rag_embedding_dimension, 3)
        self.assertEqual(config.memory_rag_embedding_timeout_seconds, 7)
        self.assertEqual(config.memory_rag_top_k, 6)
        self.assertEqual(config.memory_rag_min_score, 0.45)
        self.assertEqual(config.memory_rag_max_context_chars, 700)
        self.assertEqual(config.project_doc_rag_top_k, 8)
        self.assertEqual(config.project_doc_rag_min_score, 0.40)
        self.assertEqual(config.project_doc_rag_max_context_chars, 900)
        self.assertFalse(config.memory_rag_include_manual_facts)
        self.assertFalse(config.memory_rag_include_manual_preferences)
        self.assertFalse(config.memory_rag_include_session_summaries)
        self.assertTrue(config.memory_rag_include_short_messages)
        self.assertTrue(config.memory_rag_include_gap_scene_summaries)
        self.assertFalse(config.memory_rag_owner_only_debug)
        self.assertTrue(config.memory_rag_inject_in_chat)
        self.assertEqual(config.ai_temperature, 0.25)
        self.assertEqual(config.private_whitelist, frozenset({"10001", "10002"}))
        self.assertEqual(config.group_whitelist, frozenset({"42", "43"}))
        self.assertEqual(config.user_blacklist, frozenset({"90001", "90002"}))


if __name__ == "__main__":
    unittest.main()
