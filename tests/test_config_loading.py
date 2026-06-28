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
        self.assertTrue(config.main_agent_owner_only)
        self.assertFalse(config.main_agent_allow_group)
        self.assertTrue(config.main_agent_require_approval_for_writes)
        self.assertFalse(config.enable_agent_web)
        self.assertFalse(config.enable_agent_local_write)
        self.assertFalse(config.enable_agent_external_write)
        self.assertFalse(config.enable_agent_shell)
        self.assertEqual(config.main_llm_base_url, "https://api.openai.com/v1")
        self.assertEqual(config.main_llm_model, "gpt-4.1-mini")
        self.assertEqual(config.chat_llm_base_url, "https://api.deepseek.com")
        self.assertEqual(config.chat_llm_model, "deepseek-v4-flash")
        self.assertEqual(config.chat_llm_timeout_seconds, config.ai_timeout_seconds)

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

    def test_boolean_numeric_and_csv_env_values_are_parsed(self):
        config = self.load_with_env(
            {
                "ENABLE_MAIN_AGENT": "yes",
                "MAIN_AGENT_OWNER_ONLY": "false",
                "MAIN_AGENT_ALLOW_GROUP": "on",
                "MAIN_AGENT_MAX_STEPS": "9",
                "MAIN_AGENT_REQUIRE_APPROVAL_FOR_WRITES": "0",
                "ENABLE_AGENT_WEB": "true",
                "ENABLE_AGENT_LOCAL_WRITE": "1",
                "ENABLE_AGENT_EXTERNAL_WRITE": "yes",
                "ENABLE_AGENT_SHELL": "on",
                "AI_TEMPERATURE": "0.25",
                "PRIVATE_WHITELIST": "10001, 10002,10001,,",
                "GROUP_WHITELIST": "42, 43",
                "USER_BLACKLIST": "90001,90002",
            }
        )

        self.assertTrue(config.enable_main_agent)
        self.assertFalse(config.main_agent_owner_only)
        self.assertTrue(config.main_agent_allow_group)
        self.assertEqual(config.main_agent_max_steps, 9)
        self.assertFalse(config.main_agent_require_approval_for_writes)
        self.assertTrue(config.enable_agent_web)
        self.assertTrue(config.enable_agent_local_write)
        self.assertTrue(config.enable_agent_external_write)
        self.assertTrue(config.enable_agent_shell)
        self.assertEqual(config.ai_temperature, 0.25)
        self.assertEqual(config.private_whitelist, frozenset({"10001", "10002"}))
        self.assertEqual(config.group_whitelist, frozenset({"42", "43"}))
        self.assertEqual(config.user_blacklist, frozenset({"90001", "90002"}))


if __name__ == "__main__":
    unittest.main()
