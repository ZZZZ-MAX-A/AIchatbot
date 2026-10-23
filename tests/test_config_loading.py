from __future__ import annotations

import os
from pathlib import Path
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

    def test_aike_reasoning_effort_is_validated_without_exposing_invalid_value(self):
        for value in ("low", "high", "max"):
            with self.subTest(value=value):
                config = self.load_with_env({"AIKE_LLM_REASONING_EFFORT": value})
                self.assertEqual(config.aike_llm_reasoning_effort, value)
        with self.assertRaises(self.config_module.ConfigValidationError) as caught:
            self.load_with_env({"AIKE_LLM_REASONING_EFFORT": "SECRET-TYPO"})
        self.assertIn("AIKE_LLM_REASONING_EFFORT", str(caught.exception))
        self.assertNotIn("SECRET-TYPO", str(caught.exception))

    def test_deepseek_vision_inherits_aike_connection_and_keeps_persona_chat(self):
        config = self.load_with_env({
            "AIKE_LLM_API_KEY": "TEST-DS-KEY", "AIKE_LLM_BASE_URL": "https://api.deepseek.com",
            "AIKE_LLM_MODEL": "deepseek-flash", "AIKE_LLM_REASONING_EFFORT": "low",
            "PERSONA_LLM_API_KEY": "TEST-GROK-KEY", "PERSONA_LLM_BASE_URL": "https://grok.example/v1",
            "PERSONA_LLM_MODEL": "grok-4.6", "PERSONA_VISION_MODEL": "deepseek-flash",
        })
        self.assertEqual(config.persona_vision_api_key, "TEST-DS-KEY")
        self.assertEqual(config.persona_vision_base_url, "https://api.deepseek.com")
        self.assertEqual(config.persona_vision_model, "deepseek-flash")
        self.assertEqual(config.persona_vision_max_tokens, 4096)
        self.assertEqual(config.persona_vision_reasoning_effort, "high")
        self.assertEqual(config.aike_llm_reasoning_effort, "low")
        self.assertEqual(config.persona_llm_model, "grok-4.6")
        self.assertEqual(config.persona_llm_api_key, "TEST-GROK-KEY")

    def test_deepseek_vision_explicit_blank_and_independent_override_are_preserved(self):
        common = {"AIKE_LLM_API_KEY": "TEST-DS-KEY", "PERSONA_LLM_API_KEY": "TEST-GROK-KEY",
                  "PERSONA_VISION_MODEL": "deepseek-flash"}
        blank = self.load_with_env({**common, "PERSONA_VISION_API_KEY": "", "PERSONA_VISION_BASE_URL": ""})
        self.assertEqual(blank.persona_vision_api_key, "")
        self.assertEqual(blank.persona_vision_base_url, "")
        override = self.load_with_env({**common, "PERSONA_VISION_API_KEY": "TEST-OTHER-DS-KEY",
            "PERSONA_VISION_BASE_URL": "https://ds.example/v1", "PERSONA_VISION_MAX_TOKENS": "8192",
            "PERSONA_VISION_REASONING_EFFORT": "high"})
        self.assertEqual(override.persona_vision_api_key, "TEST-OTHER-DS-KEY")
        self.assertEqual(override.persona_vision_base_url, "https://ds.example/v1")
        self.assertEqual(override.persona_vision_max_tokens, 8192)
        self.assertEqual(override.persona_vision_reasoning_effort, "high")

    def test_grok_vision_defaults_keep_existing_budget_and_connection(self):
        config = self.load_with_env({"PERSONA_LLM_API_KEY": "TEST-GROK-KEY",
            "PERSONA_LLM_BASE_URL": "https://grok.example/v1", "PERSONA_VISION_MODEL": "grok-4.6"})
        self.assertEqual(config.persona_vision_api_key, "TEST-GROK-KEY")
        self.assertEqual(config.persona_vision_base_url, "https://grok.example/v1")
        self.assertEqual(config.persona_vision_max_tokens, 400)

    def test_defaults_keep_main_agent_disabled_and_chat_model_on_legacy_provider(self):
        config = self.load_with_env({})

        self.assertFalse(config.enable_main_agent)
        self.assertEqual(config.bot_timezone, "Asia/Shanghai")
        self.assertEqual(config.aike_llm_reasoning_effort, "high")
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
        self.assertFalse(config.enable_local_stickers)
        self.assertEqual(config.local_sticker_root.name, "stickers")
        self.assertEqual(config.local_sticker_max_file_bytes, 2_097_152)
        self.assertEqual(config.local_sticker_max_dynamic_file_bytes, 5_242_880)
        self.assertEqual(config.local_sticker_min_dimension, 32)
        self.assertEqual(config.local_sticker_max_dimension, 2048)
        self.assertEqual(config.local_sticker_max_pixels, 4_194_304)
        self.assertEqual(config.local_sticker_max_animation_frames, 120)
        self.assertEqual(config.local_sticker_max_animation_duration_ms, 10_000)
        self.assertEqual(config.local_sticker_min_frame_duration_ms, 20)
        self.assertEqual(config.local_sticker_max_animation_decoded_pixels, 60_000_000)
        self.assertEqual(config.local_sticker_preview_cooldown_seconds, 3)
        self.assertFalse(config.enable_chat_sticker_intent_shadow)
        self.assertFalse(config.enable_chat_sticker_attachments)
        self.assertFalse(config.enable_remote_sticker_classifier)
        self.assertEqual(config.sticker_classifier_api_key, "")
        self.assertEqual(config.sticker_classifier_base_url, "")
        self.assertEqual(config.sticker_classifier_model, "")
        self.assertEqual(config.sticker_classifier_timeout_seconds, 8)
        self.assertEqual(config.sticker_classifier_max_input_chars, 2400)
        self.assertTrue(config.chat_sticker_owner_private_only)
        self.assertEqual(config.chat_sticker_cooldown_seconds, 120)
        self.assertEqual(config.chat_sticker_min_messages_between, 4)
        self.assertEqual(config.chat_sticker_max_per_hour, 6)
        self.assertEqual(config.chat_sticker_max_per_reply, 1)
        self.assertEqual(config.chat_sticker_min_intent_confidence, 0.82)
        self.assertNotIn(str(config.local_sticker_root), repr(config))
        self.assertEqual(config.main_llm_base_url, "https://api.openai.com/v1")
        self.assertEqual(config.main_llm_model, "gpt-4.1-mini")
        self.assertEqual(config.chat_llm_base_url, "https://api.deepseek.com")
        self.assertEqual(config.chat_llm_model, "deepseek-v4-flash")
        self.assertEqual(config.chat_llm_timeout_seconds, 60)
        self.assertTrue(config.enable_unknown_slang_tool)
        self.assertEqual(config.summary_llm_api_key, "")
        self.assertEqual(config.summary_llm_base_url, "https://api.deepseek.com")
        self.assertEqual(config.summary_llm_model, "deepseek-v4-flash")
        self.assertEqual(config.summary_llm_timeout_seconds, 60)
        self.assertFalse(config.enable_persona_llm_routing)
        self.assertEqual(config.persona_llm_role_card_keys, frozenset())
        self.assertEqual(config.persona_llm_provider, "openai")
        self.assertEqual(config.persona_llm_api_key, "")
        self.assertEqual(config.persona_llm_base_url, "")
        self.assertEqual(config.persona_llm_model, "")
        self.assertEqual(
            config.persona_llm_timeout_seconds,
            60,
        )
        self.assertEqual(config.persona_llm_num_ctx, 4096)
        self.assertEqual(config.persona_llm_max_tokens, 640)
        self.assertEqual(config.persona_llm_keep_alive_seconds, 0)
        self.assertFalse(config.enable_persona_vision_routing)
        self.assertEqual(config.persona_vision_role_card_keys, frozenset())
        self.assertEqual(config.persona_vision_api_key, "")
        self.assertEqual(config.persona_vision_base_url, "")
        self.assertEqual(config.persona_vision_model, "")
        self.assertEqual(
            config.persona_vision_timeout_seconds,
            60,
        )
        self.assertEqual(
            config.persona_vision_private_image_wait_seconds,
            -1,
        )
        self.assertFalse(config.enable_chat_weather)
        self.assertEqual(config.chat_weather_mode, "off")
        self.assertEqual(config.chat_weather_provider, "open_meteo")
        self.assertEqual(config.chat_weather_default_location, "")
        self.assertEqual(config.chat_weather_default_latitude, 0.0)
        self.assertEqual(config.chat_weather_default_longitude, 0.0)
        self.assertEqual(config.chat_weather_timeout_seconds, 5.0)
        self.assertEqual(config.vision_provider, "aliyun_bailian")
        self.assertEqual(config.vision_cloud_model, "qwen3.7-flash")
        self.assertEqual(config.aliyun_bailian_base_url, "")
        self.assertEqual(config.aliyun_bailian_api_key, "")
        self.assertFalse(config.enable_linyin_tts)
        self.assertEqual(config.linyin_tts_voice, "")
        self.assertEqual(config.linyin_tts_emotion, "")
        self.assertFalse(config.enable_image_gen)
        self.assertEqual(config.image_gen_api_key, "")
        self.assertEqual(config.image_gen_base_url, "")
        self.assertEqual(config.image_gen_model, "grok-imagine-image-quality")
        self.assertEqual(config.image_edit_model, "grok-imagine-image-quality")
        self.assertEqual(config.image_gen_timeout_seconds, 120)
        self.assertEqual(config.image_gen_max_prompt_chars, 1000)
        self.assertEqual(config.image_gen_max_input_bytes, 10_485_760)
        self.assertEqual(config.image_gen_max_output_bytes, 10_485_760)
        self.assertEqual(config.image_gen_pending_edit_seconds, 120)
        self.assertEqual(config.image_gen_cooldown_seconds, 30)
        self.assertEqual(config.image_gen_max_requests_per_hour, 10)
        self.assertFalse(config.enable_qwen_space_edit)
        self.assertEqual(
            config.qwen_space_base_url,
            "https://prithivmlmods-qwen-image-edit-2511-loras-fast.hf.space",
        )
        self.assertEqual(config.qwen_space_hf_token, "")
        self.assertEqual(config.qwen_space_submit_timeout_seconds, 60)
        self.assertEqual(config.qwen_space_infer_timeout_seconds, 180)
        self.assertEqual(config.qwen_space_download_timeout_seconds, 300)
        self.assertEqual(config.qwen_space_download_retries, 2)
        self.assertEqual(config.qwen_space_result_ttl_seconds, 1800)
        self.assertEqual(config.qwen_space_max_side, 1024)
        self.assertEqual(config.qwen_space_jpeg_quality, 90)
        self.assertEqual(config.vision_trusted_local_roots, ())
        self.assertFalse(config.enable_memory_rag)
        self.assertFalse(config.enable_project_doc_rag)
        self.assertEqual(config.memory_rag_embedding_provider, "ollama")
        self.assertEqual(config.memory_rag_embedding_model, "bge-m3")
        self.assertEqual(config.memory_rag_embedding_base_url, "http://127.0.0.1:11434")
        self.assertEqual(config.memory_rag_embedding_num_gpu, -1)
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
        self.assertFalse(config.persona_routing.routing_v2_enabled)
        self.assertFalse(config.persona_routing.memory_v2_enabled)
        self.assertEqual(config.persona_routing.routing_v2_bot_ids, frozenset())
        self.assertEqual(config.persona_routing.memory_v2_bot_ids, frozenset())
        self.assertEqual(config.persona_routing.legacy_persona_id, "aike")
        self.assertEqual(config.persona_routing.legacy_role_card_key, "aike")
        self.assertEqual(config.persona_routing.bindings, ())
        self.assertEqual(config.persona_routing.binding_errors, ())
        self.assertEqual(config.max_private_message_length, 150)
        self.assertEqual(config.owner_max_private_message_length, 0)
        self.assertFalse(config.enable_shared_scene_hub)
        self.assertEqual(config.shared_scene_group_id, "")
        self.assertEqual(config.shared_scene_aike_bot_id, "")
        self.assertEqual(config.shared_scene_linyin_bot_id, "")
        self.assertEqual(config.scene_director_provider, "qwen")
        self.assertEqual(config.scene_director_api_key, "")
        self.assertEqual(config.scene_director_base_url, "")
        self.assertEqual(config.scene_director_model, "")
        self.assertEqual(config.scene_director_timeout_seconds, 15)
        self.assertEqual(config.scene_director_circuit_seconds, 120)
        self.assertEqual(config.scene_max_context_events, 20)
        self.assertEqual(config.scene_director_context_events, 6)
        self.assertEqual(config.scene_max_reply_sentences, 3)
        self.assertEqual(config.scene_max_reply_chars, 160)
        self.assertEqual(config.scene_actor_max_tokens, 256)
        self.assertEqual(config.scene_private_context_max_messages, 12)
        self.assertEqual(config.scene_private_context_max_summaries, 2)
        self.assertEqual(config.scene_private_context_max_gap_summaries, 1)
        self.assertEqual(config.scene_private_context_max_manual_memories, 8)
        self.assertEqual(config.scene_private_context_max_chars, 2400)
        self.assertEqual(config.scene_member_cache_seconds, 30)
        self.assertEqual(config.scene_max_pending_turns, 1)
        self.assertEqual(config.tts_max_chars, 260)
        self.assertEqual(config.tts_max_total_seconds, 60)

    def test_aike_llm_configuration_is_independent_from_chat_llm(self):
        config = self.load_with_env(
            {
                "AIKE_LLM_API_KEY": "aike-key",
                "AIKE_LLM_BASE_URL": "https://aike.example/v1",
                "AIKE_LLM_MODEL": "aike-chat",
                "AIKE_LLM_TIMEOUT_SECONDS": "33",
            }
        )

        self.assertEqual(config.aike_llm_api_key, "aike-key")
        self.assertEqual(config.aike_llm_base_url, "https://aike.example/v1")
        self.assertEqual(config.aike_llm_model, "aike-chat")
        self.assertEqual(config.aike_llm_timeout_seconds, 33)
        self.assertEqual(config.chat_llm_api_key, "")
        self.assertEqual(config.chat_llm_base_url, "https://api.deepseek.com")
        self.assertEqual(config.chat_llm_model, "deepseek-v4-flash")
        self.assertEqual(config.chat_llm_timeout_seconds, 60)

    def test_unknown_slang_tool_can_be_disabled(self):
        config = self.load_with_env({"ENABLE_UNKNOWN_SLANG_TOOL": "false"})

        self.assertFalse(config.enable_unknown_slang_tool)

    def test_owner_private_message_limit_can_be_reenabled_explicitly(self):
        config = self.load_with_env({"OWNER_MAX_PRIVATE_MESSAGE_LENGTH": "500"})

        self.assertEqual(config.owner_max_private_message_length, 500)

    def test_persona_v2_configuration_is_explicit_and_observe_only(self):
        config = self.load_with_env(
            {
                "ENABLE_PERSONA_ROUTING_V2": "true",
                "ENABLE_PERSONA_MEMORY_V2": "true",
                "PERSONA_ROUTING_V2_BOT_IDS": "10001,20002",
                "PERSONA_MEMORY_V2_BOT_IDS": "20002",
                "LEGACY_PERSONA_ID": "aike",
                "LEGACY_ROLE_CARD_KEY": "aike",
                "BOT_PERSONA_BINDINGS": (
                    "10001=aike:aike;20002=luna:luna-card"
                ),
            }
        )

        settings = config.persona_routing
        self.assertTrue(settings.routing_v2_enabled)
        self.assertTrue(settings.memory_v2_enabled)
        self.assertEqual(settings.routing_v2_bot_ids, {"10001", "20002"})
        self.assertEqual(settings.memory_v2_bot_ids, {"20002"})
        self.assertEqual(
            [(item.bot_self_id, item.persona_id, item.role_card_key) for item in settings.bindings],
            [
                ("10001", "aike", "aike"),
                ("20002", "luna", "luna-card"),
            ],
        )
        self.assertEqual(settings.binding_errors, ())

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

    def test_summary_llm_is_independent_from_chat_llm_credentials(self):
        config = self.load_with_env(
            {
                "AIKE_LLM_API_KEY": "aike-key",
                "CHAT_LLM_API_KEY": "chat-key",
                "SUMMARY_LLM_API_KEY": "summary-key",
                "SUMMARY_LLM_BASE_URL": "https://summary.example/v1",
                "SUMMARY_LLM_MODEL": "summary-model",
                "SUMMARY_LLM_TIMEOUT_SECONDS": "33",
            }
        )

        self.assertEqual(config.summary_llm_api_key, "summary-key")
        self.assertEqual(config.summary_llm_base_url, "https://summary.example/v1")
        self.assertEqual(config.summary_llm_model, "summary-model")
        self.assertEqual(config.summary_llm_timeout_seconds, 33)
        self.assertNotIn("summary-key", repr(config))

    def test_persona_llm_route_is_explicit_and_keeps_secret_out_of_repr(self):
        config = self.load_with_env(
            {
                "ENABLE_PERSONA_LLM_ROUTING": "true",
                "PERSONA_LLM_ROLE_CARD_KEYS": "linyin",
                "PERSONA_LLM_PROVIDER": "ollama",
                "PERSONA_LLM_API_KEY": "persona-secret",
                "PERSONA_LLM_BASE_URL": "http://127.0.0.1:11434",
                "PERSONA_LLM_MODEL": "persona-model",
                "PERSONA_LLM_TIMEOUT_SECONDS": "75",
                "PERSONA_LLM_NUM_CTX": "4096",
                "PERSONA_LLM_MAX_TOKENS": "640",
                "PERSONA_LLM_KEEP_ALIVE_SECONDS": "0",
                "ENABLE_PERSONA_VISION_ROUTING": "true",
                "PERSONA_VISION_ROLE_CARD_KEYS": "linyin",
                "PERSONA_VISION_API_KEY": "vision-secret",
                "PERSONA_VISION_BASE_URL": "https://vision.example/v1",
                "PERSONA_VISION_MODEL": "persona-vision-model",
                "PERSONA_VISION_TIMEOUT_SECONDS": "80",
            }
        )

        self.assertTrue(config.enable_persona_llm_routing)
        self.assertEqual(config.persona_llm_role_card_keys, {"linyin"})
        self.assertEqual(config.persona_llm_provider, "ollama")
        self.assertEqual(config.persona_llm_api_key, "persona-secret")
        self.assertEqual(config.persona_llm_base_url, "http://127.0.0.1:11434")
        self.assertEqual(config.persona_llm_model, "persona-model")
        self.assertEqual(config.persona_llm_timeout_seconds, 75)
        self.assertEqual(config.persona_llm_num_ctx, 4096)
        self.assertEqual(config.persona_llm_max_tokens, 640)
        self.assertEqual(config.persona_llm_keep_alive_seconds, 0)
        self.assertTrue(config.enable_persona_vision_routing)
        self.assertEqual(config.persona_vision_role_card_keys, {"linyin"})
        self.assertEqual(config.persona_vision_api_key, "vision-secret")
        self.assertEqual(
            config.persona_vision_base_url,
            "https://vision.example/v1",
        )
        self.assertEqual(config.persona_vision_model, "persona-vision-model")
        self.assertEqual(config.persona_vision_timeout_seconds, 80)
        self.assertNotIn("persona-secret", repr(config))
        self.assertNotIn("vision-secret", repr(config))

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
                "ALIYUN_BAILIAN_BASE_URL": (
                    "https://ws-unit123.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
                ),
                "ALIYUN_BAILIAN_API_KEY": "bailian-secret",
                "USERPROFILE": "D:\\Users\\unit",
                "VISION_TRUSTED_LOCAL_ROOTS": (
                    "%USERPROFILE%\\NapCat Cache;relative-vision-cache"
                ),
                "ENABLE_LOCAL_STICKERS": "true",
                "LOCAL_STICKER_MAX_FILE_BYTES": "1024",
                "LOCAL_STICKER_MAX_DYNAMIC_FILE_BYTES": "2048",
                "LOCAL_STICKER_MIN_DIMENSION": "16",
                "LOCAL_STICKER_MAX_DIMENSION": "512",
                "LOCAL_STICKER_MAX_PIXELS": "262144",
                "LOCAL_STICKER_MAX_ANIMATION_FRAMES": "40",
                "LOCAL_STICKER_MAX_ANIMATION_DURATION_MS": "5000",
                "LOCAL_STICKER_MIN_FRAME_DURATION_MS": "25",
                "LOCAL_STICKER_MAX_ANIMATION_DECODED_PIXELS": "1000000",
                "LOCAL_STICKER_PREVIEW_COOLDOWN_SECONDS": "4",
                "ENABLE_CHAT_STICKER_INTENT_SHADOW": "true",
                "ENABLE_CHAT_STICKER_ATTACHMENTS": "true",
                "ENABLE_REMOTE_STICKER_CLASSIFIER": "true",
                "STICKER_CLASSIFIER_API_KEY": "classifier-secret",
                "STICKER_CLASSIFIER_BASE_URL": "https://classifier.example/v1",
                "STICKER_CLASSIFIER_MODEL": "classifier-model",
                "STICKER_CLASSIFIER_TIMEOUT_SECONDS": "6",
                "STICKER_CLASSIFIER_MAX_INPUT_CHARS": "1800",
                "CHAT_STICKER_OWNER_PRIVATE_ONLY": "false",
                "CHAT_STICKER_COOLDOWN_SECONDS": "90",
                "CHAT_STICKER_MIN_MESSAGES_BETWEEN": "3",
                "CHAT_STICKER_MAX_PER_HOUR": "5",
                "CHAT_STICKER_MAX_PER_REPLY": "1",
                "CHAT_STICKER_MIN_INTENT_CONFIDENCE": "0.88",
                "ENABLE_CHAT_WEATHER": "true",
                "CHAT_WEATHER_MODE": "owner_auto",
                "CHAT_WEATHER_PROVIDER": "open_meteo",
                "CHAT_WEATHER_DEFAULT_LOCATION": "萍乡",
                "CHAT_WEATHER_DEFAULT_LATITUDE": "27.62",
                "CHAT_WEATHER_DEFAULT_LONGITUDE": "113.85",
                "CHAT_WEATHER_TIMEOUT_SECONDS": "2.5",
                "ENABLE_MEMORY_RAG": "true",
                "ENABLE_PROJECT_DOC_RAG": "yes",
                "MEMORY_RAG_EMBEDDING_PROVIDER": "unit",
                "MEMORY_RAG_EMBEDDING_MODEL": "toy",
                "MEMORY_RAG_EMBEDDING_BASE_URL": "http://127.0.0.1:9999",
                "MEMORY_RAG_EMBEDDING_DIMENSION": "3",
                "MEMORY_RAG_EMBEDDING_TIMEOUT_SECONDS": "7",
                "MEMORY_RAG_EMBEDDING_NUM_GPU": "0",
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
                "ENABLE_LINYIN_TTS": "true",
                "LINYIN_TTS_VOICE": "zh_kelin_raw_20260625",
                "LINYIN_TTS_EMOTION": "neutral",
                "ENABLE_IMAGE_GEN": "true",
                "IMAGE_GEN_API_KEY": "image-secret",
                "IMAGE_GEN_BASE_URL": "https://image.example/v1/",
                "IMAGE_GEN_MODEL": "unit-generate",
                "IMAGE_GEN_TIMEOUT_SECONDS": "95",
                "IMAGE_GEN_MAX_PROMPT_CHARS": "800",
                "IMAGE_GEN_MAX_INPUT_BYTES": "5000000",
                "IMAGE_GEN_MAX_OUTPUT_BYTES": "6000000",
                "IMAGE_GEN_PENDING_EDIT_SECONDS": "150",
                "IMAGE_GEN_COOLDOWN_SECONDS": "20",
                "IMAGE_GEN_MAX_REQUESTS_PER_HOUR": "7",
                "ENABLE_QWEN_SPACE_EDIT": "true",
                "QWEN_SPACE_BASE_URL": "https://qwen-space.example",
                "QWEN_SPACE_HF_TOKEN": "hf-unit-secret",
                "QWEN_SPACE_SUBMIT_TIMEOUT_SECONDS": "50",
                "QWEN_SPACE_INFER_TIMEOUT_SECONDS": "170",
                "QWEN_SPACE_DOWNLOAD_TIMEOUT_SECONDS": "280",
                "QWEN_SPACE_DOWNLOAD_RETRIES": "1",
                "QWEN_SPACE_RESULT_TTL_SECONDS": "1200",
                "QWEN_SPACE_MAX_SIDE": "960",
                "QWEN_SPACE_JPEG_QUALITY": "88",
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
        self.assertEqual(config.vision_provider, "aliyun_bailian")
        self.assertEqual(config.vision_cloud_model, "qwen3.7-flash")
        self.assertEqual(
            config.aliyun_bailian_base_url,
            "https://ws-unit123.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        )
        self.assertEqual(config.aliyun_bailian_api_key, "bailian-secret")
        self.assertNotIn("bailian-secret", repr(config))
        self.assertEqual(
            config.vision_trusted_local_roots,
            (
                Path("D:/Users/unit/NapCat Cache").resolve(strict=False),
                (self.config_module.PROJECT_ROOT / "relative-vision-cache").resolve(
                    strict=False
                ),
            ),
        )
        self.assertNotIn("NapCat Cache", repr(config))
        self.assertTrue(config.enable_local_stickers)
        self.assertEqual(config.local_sticker_max_file_bytes, 1024)
        self.assertEqual(config.local_sticker_max_dynamic_file_bytes, 2048)
        self.assertEqual(config.local_sticker_min_dimension, 16)
        self.assertEqual(config.local_sticker_max_dimension, 512)
        self.assertEqual(config.local_sticker_max_pixels, 262144)
        self.assertEqual(config.local_sticker_max_animation_frames, 40)
        self.assertEqual(config.local_sticker_max_animation_duration_ms, 5000)
        self.assertEqual(config.local_sticker_min_frame_duration_ms, 25)
        self.assertEqual(config.local_sticker_max_animation_decoded_pixels, 1_000_000)
        self.assertEqual(config.local_sticker_preview_cooldown_seconds, 4)
        self.assertTrue(config.enable_chat_sticker_intent_shadow)
        self.assertTrue(config.enable_chat_sticker_attachments)
        self.assertTrue(config.enable_remote_sticker_classifier)
        self.assertEqual(config.sticker_classifier_api_key, "classifier-secret")
        self.assertEqual(
            config.sticker_classifier_base_url,
            "https://classifier.example/v1",
        )
        self.assertEqual(config.sticker_classifier_model, "classifier-model")
        self.assertEqual(config.sticker_classifier_timeout_seconds, 6)
        self.assertEqual(config.sticker_classifier_max_input_chars, 1800)
        self.assertNotIn("classifier-secret", repr(config))
        self.assertFalse(config.chat_sticker_owner_private_only)
        self.assertEqual(config.chat_sticker_cooldown_seconds, 90)
        self.assertEqual(config.chat_sticker_min_messages_between, 3)
        self.assertEqual(config.chat_sticker_max_per_hour, 5)
        self.assertEqual(config.chat_sticker_max_per_reply, 1)
        self.assertEqual(config.chat_sticker_min_intent_confidence, 0.88)
        self.assertTrue(config.enable_linyin_tts)
        self.assertEqual(config.linyin_tts_voice, "zh_kelin_raw_20260625")
        self.assertEqual(config.linyin_tts_emotion, "neutral")
        self.assertTrue(config.enable_image_gen)
        self.assertEqual(config.image_gen_api_key, "image-secret")
        self.assertEqual(config.image_gen_base_url, "https://image.example/v1/")
        self.assertEqual(config.image_gen_model, "unit-generate")
        self.assertEqual(config.image_edit_model, "unit-generate")
        self.assertEqual(config.image_gen_timeout_seconds, 95)
        self.assertEqual(config.image_gen_max_prompt_chars, 800)
        self.assertEqual(config.image_gen_max_input_bytes, 5_000_000)
        self.assertEqual(config.image_gen_max_output_bytes, 6_000_000)
        self.assertEqual(config.image_gen_pending_edit_seconds, 150)
        self.assertEqual(config.image_gen_cooldown_seconds, 20)
        self.assertEqual(config.image_gen_max_requests_per_hour, 7)
        self.assertNotIn("image-secret", repr(config))
        self.assertTrue(config.enable_qwen_space_edit)
        self.assertEqual(config.qwen_space_base_url, "https://qwen-space.example")
        self.assertEqual(config.qwen_space_hf_token, "hf-unit-secret")
        self.assertEqual(config.qwen_space_submit_timeout_seconds, 50)
        self.assertEqual(config.qwen_space_infer_timeout_seconds, 170)
        self.assertEqual(config.qwen_space_download_timeout_seconds, 280)
        self.assertEqual(config.qwen_space_download_retries, 1)
        self.assertEqual(config.qwen_space_result_ttl_seconds, 1200)
        self.assertEqual(config.qwen_space_max_side, 960)
        self.assertEqual(config.qwen_space_jpeg_quality, 88)
        self.assertNotIn("hf-unit-secret", repr(config))
        self.assertTrue(config.enable_chat_weather)
        self.assertEqual(config.chat_weather_mode, "owner_auto")
        self.assertEqual(config.chat_weather_provider, "open_meteo")
        self.assertEqual(config.chat_weather_default_location, "萍乡")
        self.assertEqual(config.chat_weather_default_latitude, 27.62)
        self.assertEqual(config.chat_weather_default_longitude, 113.85)
        self.assertEqual(config.chat_weather_timeout_seconds, 2.5)
        self.assertTrue(config.enable_memory_rag)
        self.assertTrue(config.enable_project_doc_rag)
        self.assertEqual(config.memory_rag_embedding_provider, "unit")
        self.assertEqual(config.memory_rag_embedding_num_gpu, 0)
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

    def test_image_gen_endpoint_can_explicitly_reuse_persona_channel(self):
        config = self.load_with_env(
            {
                "PERSONA_LLM_API_KEY": "persona-image-secret",
                "PERSONA_LLM_BASE_URL": "https://persona-image.example/v1",
            }
        )

        self.assertEqual(config.image_gen_api_key, "persona-image-secret")
        self.assertEqual(
            config.image_gen_base_url,
            "https://persona-image.example/v1",
        )
        self.assertNotIn("persona-image-secret", repr(config))

    def test_invalid_local_sticker_limits_fail_closed(self):
        config = self.load_with_env(
            {
                "ENABLE_LOCAL_STICKERS": "true",
                "LOCAL_STICKER_MAX_FILE_BYTES": "invalid",
                "LOCAL_STICKER_MAX_DYNAMIC_FILE_BYTES": "invalid",
                "LOCAL_STICKER_MIN_DIMENSION": "invalid",
                "LOCAL_STICKER_MAX_DIMENSION": "invalid",
                "LOCAL_STICKER_MAX_PIXELS": "invalid",
                "LOCAL_STICKER_MAX_ANIMATION_FRAMES": "invalid",
                "LOCAL_STICKER_MAX_ANIMATION_DURATION_MS": "invalid",
                "LOCAL_STICKER_MIN_FRAME_DURATION_MS": "invalid",
                "LOCAL_STICKER_MAX_ANIMATION_DECODED_PIXELS": "invalid",
                "LOCAL_STICKER_PREVIEW_COOLDOWN_SECONDS": "invalid",
                "CHAT_STICKER_COOLDOWN_SECONDS": "invalid",
                "CHAT_STICKER_MIN_MESSAGES_BETWEEN": "invalid",
                "CHAT_STICKER_MAX_PER_HOUR": "invalid",
                "CHAT_STICKER_MAX_PER_REPLY": "invalid",
                "CHAT_STICKER_MIN_INTENT_CONFIDENCE": "invalid",
            }
        )

        self.assertTrue(config.enable_local_stickers)
        self.assertEqual(config.local_sticker_max_file_bytes, 0)
        self.assertEqual(config.local_sticker_max_dynamic_file_bytes, 0)
        self.assertEqual(config.local_sticker_min_dimension, 0)
        self.assertEqual(config.local_sticker_max_dimension, 0)
        self.assertEqual(config.local_sticker_max_pixels, 0)
        self.assertEqual(config.local_sticker_max_animation_frames, 0)
        self.assertEqual(config.local_sticker_max_animation_duration_ms, 0)
        self.assertEqual(config.local_sticker_min_frame_duration_ms, 0)
        self.assertEqual(config.local_sticker_max_animation_decoded_pixels, 0)
        self.assertEqual(config.local_sticker_preview_cooldown_seconds, 0)
        self.assertEqual(config.chat_sticker_cooldown_seconds, 0)
        self.assertEqual(config.chat_sticker_min_messages_between, 0)
        self.assertEqual(config.chat_sticker_max_per_hour, 0)
        self.assertEqual(config.chat_sticker_max_per_reply, 0)
        self.assertEqual(config.chat_sticker_min_intent_confidence, 0.0)

    def test_invalid_remote_sticker_classifier_limits_fail_closed(self):
        config = self.load_with_env(
            {
                "ENABLE_REMOTE_STICKER_CLASSIFIER": "true",
                "STICKER_CLASSIFIER_TIMEOUT_SECONDS": "invalid",
                "STICKER_CLASSIFIER_MAX_INPUT_CHARS": "invalid",
            }
        )

        self.assertTrue(config.enable_remote_sticker_classifier)
        self.assertEqual(config.sticker_classifier_timeout_seconds, 0)
        self.assertEqual(config.sticker_classifier_max_input_chars, 0)

    def test_invalid_chat_weather_configuration_fails_closed(self):
        config = self.load_with_env(
            {
                "ENABLE_CHAT_WEATHER": "true",
                "CHAT_WEATHER_MODE": "not-a-mode",
                "CHAT_WEATHER_DEFAULT_LATITUDE": "invalid",
                "CHAT_WEATHER_DEFAULT_LONGITUDE": "invalid",
                "CHAT_WEATHER_TIMEOUT_SECONDS": "invalid",
            }
        )

        self.assertTrue(config.enable_chat_weather)
        self.assertEqual(config.chat_weather_mode, "off")
        self.assertEqual(config.chat_weather_default_latitude, 0.0)
        self.assertEqual(config.chat_weather_default_longitude, 0.0)
        self.assertEqual(config.chat_weather_timeout_seconds, 0.0)

    def test_scene_hub_configuration_is_explicit_secret_safe_and_fail_closed(self):
        config = self.load_with_env(
            {
                "ENABLE_SHARED_SCENE_HUB": "true",
                "SHARED_SCENE_GROUP_ID": "30003",
                "SHARED_SCENE_AIKE_BOT_ID": "20001",
                "SHARED_SCENE_LINYIN_BOT_ID": "20002",
                "SCENE_DIRECTOR_PROVIDER": "DEEPSEEK",
                "SCENE_DIRECTOR_API_KEY": "director-secret",
                "SCENE_DIRECTOR_BASE_URL": "https://director.example/v1",
                "SCENE_DIRECTOR_MODEL": "deepseek-chat",
                "SCENE_DIRECTOR_TIMEOUT_SECONDS": "invalid",
                "SCENE_DIRECTOR_CIRCUIT_SECONDS": "invalid",
                "SCENE_MAX_CONTEXT_EVENTS": "invalid",
                "SCENE_DIRECTOR_CONTEXT_EVENTS": "invalid",
                "SCENE_MAX_REPLY_SENTENCES": "invalid",
                "SCENE_MAX_REPLY_CHARS": "invalid",
                "SCENE_ACTOR_MAX_TOKENS": "invalid",
                "SCENE_PRIVATE_CONTEXT_MAX_MESSAGES": "invalid",
                "SCENE_PRIVATE_CONTEXT_MAX_SUMMARIES": "invalid",
                "SCENE_PRIVATE_CONTEXT_MAX_GAP_SUMMARIES": "invalid",
                "SCENE_PRIVATE_CONTEXT_MAX_MANUAL_MEMORIES": "invalid",
                "SCENE_PRIVATE_CONTEXT_MAX_CHARS": "invalid",
                "SCENE_MEMBER_CACHE_SECONDS": "invalid",
                "SCENE_MAX_PENDING_TURNS": "invalid",
            }
        )

        self.assertTrue(config.enable_shared_scene_hub)
        self.assertEqual(config.scene_director_provider, "deepseek")
        self.assertEqual(config.scene_director_api_key, "director-secret")
        self.assertNotIn("director-secret", repr(config))
        self.assertNotIn("30003", repr(config))
        self.assertNotIn("20001", repr(config))
        self.assertNotIn("20002", repr(config))
        self.assertEqual(config.scene_director_timeout_seconds, 0)
        self.assertEqual(config.scene_director_circuit_seconds, 0)
        self.assertEqual(config.scene_max_context_events, 0)
        self.assertEqual(config.scene_director_context_events, 0)
        self.assertEqual(config.scene_max_reply_sentences, 0)
        self.assertEqual(config.scene_max_reply_chars, 0)
        self.assertEqual(config.scene_actor_max_tokens, 0)
        self.assertEqual(config.scene_private_context_max_messages, 0)
        self.assertEqual(config.scene_private_context_max_summaries, 0)
        self.assertEqual(config.scene_private_context_max_gap_summaries, 0)
        self.assertEqual(config.scene_private_context_max_manual_memories, 0)
        self.assertEqual(config.scene_private_context_max_chars, 0)
        self.assertEqual(config.scene_member_cache_seconds, 0)
        self.assertEqual(config.scene_max_pending_turns, 0)



    def test_chat_bubble_split_defaults_off(self):
        config = self.load_with_env({})
        self.assertFalse(config.enable_chat_bubble_split)
        self.assertTrue(config.chat_bubble_split_owner_private_only)
        self.assertEqual(config.chat_bubble_min_delay_ms, 700)
        self.assertEqual(config.chat_bubble_max_delay_ms, 1200)
        self.assertEqual(config.chat_bubble_max_bubbles, 3)

    def test_chat_bubble_split_can_be_enabled(self):
        config = self.load_with_env(
            {
                'ENABLE_CHAT_BUBBLE_SPLIT': 'true',
                'CHAT_BUBBLE_MIN_DELAY_MS': '800',
            }
        )
        self.assertTrue(config.enable_chat_bubble_split)
        self.assertEqual(config.chat_bubble_min_delay_ms, 800)



    def test_chat_reunion_defaults(self):
        config = self.load_with_env({})
        self.assertTrue(config.enable_chat_reunion)
        self.assertTrue(config.chat_reunion_owner_private_only)
        self.assertEqual(config.chat_reunion_min_gap_hours, 3)

    def test_chat_reunion_can_be_disabled(self):
        config = self.load_with_env({'ENABLE_CHAT_REUNION': 'false'})
        self.assertFalse(config.enable_chat_reunion)


if __name__ == "__main__":
    unittest.main()
