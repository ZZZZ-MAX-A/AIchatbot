from __future__ import annotations

import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class AccountPersonaSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.config_module = load_module("src.plugins.ai_chat.config", AI_CHAT_ROOT / "config.py")
        cls.module = load_module("src.plugins.ai_chat.account_persona_settings", AI_CHAT_ROOT / "account_persona_settings.py")
        cls.maintenance = load_module("src.plugins.ai_chat.persona_maintenance", AI_CHAT_ROOT / "persona_maintenance.py")
        cls.fastapi = load_module("src.plugins.ai_chat.owner_console_fastapi_app", AI_CHAT_ROOT / "owner_console_fastapi_app.py")

    def config(self, **overrides):
        values = {
            "BOT_OWNER_QQ": "1000000001",
            "BOT_PERSONA_BINDINGS": "2000000001=aike:aike;3000000001=linyin:linyin",
            "ENABLE_PERSONA_ROUTING_V2": "true", "ENABLE_PERSONA_MEMORY_V2": "true",
            "PERSONA_ROUTING_V2_BOT_IDS": "3000000001", "PERSONA_MEMORY_V2_BOT_IDS": "3000000001",
            "AIKE_LLM_API_KEY": "SECRET-DEFAULT", "AIKE_LLM_MODEL": "default-model",
            "ENABLE_PERSONA_LLM_ROUTING": "true", "PERSONA_LLM_ROLE_CARD_KEYS": "linyin",
            "PERSONA_LLM_API_KEY": "SECRET-PERSONA", "PERSONA_LLM_BASE_URL": "https://persona.example/v1",
            "PERSONA_LLM_MODEL": "persona-model", "ENABLE_PERSONA_VISION_ROUTING": "true",
            "PERSONA_VISION_ROLE_CARD_KEYS": "linyin", "PERSONA_VISION_MODEL": "vision-persona",
            "ALIYUN_BAILIAN_API_KEY": "SECRET-VISION", "ALIYUN_BAILIAN_BASE_URL": "https://ws-test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
            "ENABLE_LOCAL_STICKERS": "true", "ENABLE_UNKNOWN_SLANG_TOOL": "true",
            "ENABLE_TTS": "true", "TTS_VOICE": "test-aike", "TTS_EMOTION": "affection",
            "ENABLE_LINYIN_TTS": "true", "LINYIN_TTS_VOICE": "test-linyin", "LINYIN_TTS_EMOTION": "soft",
            "ENABLE_SHARED_SCENE_HUB": "true", "SHARED_SCENE_GROUP_ID": "4000000001",
            "SHARED_SCENE_AIKE_BOT_ID": "2000000001", "SHARED_SCENE_LINYIN_BOT_ID": "3000000001",
        }
        values.update(overrides)
        return self.config_module.load_config(values)

    def profiles(self, config=None, available=frozenset({"aike", "linyin"})):
        with patch.object(self.module, "available_bound_role_card_keys", return_value=available):
            return self.module.build_account_persona_profiles(config or self.config())

    @staticmethod
    def wav():
        data = io.BytesIO()
        with wave.open(data, "wb") as writer:
            writer.setnchannels(1); writer.setsampwidth(2); writer.setframerate(16000)
            writer.writeframes(b"\0\0" * 1600)
        return data.getvalue()

    def test_account_identity_models_memory_and_voice_are_separate(self):
        aike, linyin = self.profiles()
        self.assertEqual((aike["bot_self_id"], aike["persona_name"]), ("2000000001", "爱可"))
        self.assertEqual(aike["chat_model"]["model_name"], "default-model")
        self.assertEqual(linyin["chat_model"]["model_name"], "persona-model")
        self.assertEqual(aike["vision_model"]["model_name"], "qwen3.7-flash")
        self.assertEqual(linyin["vision_model"]["model_name"], "vision-persona")
        self.assertEqual(aike["memory"]["database"], "data/chatbot.db")
        self.assertEqual(linyin["memory"]["database"], "data/persona-memory/linyin.db")
        self.assertEqual(aike["voice"]["voice_id"], "test-aike")
        self.assertEqual(linyin["voice"]["voice_id"], "test-linyin")

    def test_displayed_reasoning_matches_chat_and_scene_overrides(self):
        aike, linyin = self.profiles(self.config(AIKE_LLM_REASONING_EFFORT="max"))
        self.assertEqual(aike["chat_model"]["reasoning_effort"], "max")
        self.assertEqual(aike["chat_model"]["reasoning_effort_source"], "AIKE_LLM_REASONING_EFFORT")
        self.assertEqual(aike["scene"]["actor_model"]["reasoning_effort"], "max")
        self.assertIsNone(linyin["chat_model"]["reasoning_effort"])
        self.assertEqual(linyin["scene"]["actor_model"]["reasoning_effort"], "low")
        self.assertEqual(linyin["scene"]["actor_model"]["reasoning_effort_source"], "SceneHub 演员配置")
        self.assertEqual(aike["vision_model"]["provider"], "aliyun_bailian")
        self.assertNotIn("reasoning_effort", aike["vision_model"])

    def test_capability_difference_is_explicit_and_scene_exception_preserved(self):
        aike, linyin = self.profiles()
        a = {item["key"]: item for item in aike["capabilities"]}
        b = {item["key"]: item for item in linyin["capabilities"]}
        self.assertEqual(a["encyclopedia"]["state"], "enabled")
        self.assertEqual(a["stickers"]["state"], "enabled")
        self.assertEqual(b["encyclopedia"]["state"], "enabled")
        self.assertIn("仅生成一次", b["encyclopedia"]["detail"])
        self.assertEqual(b["stickers"]["state"], "enabled")
        self.assertEqual(b["group_auto_reply"]["state"], "unsupported")
        self.assertEqual(a.keys(), b.keys())
        self.assertEqual(linyin["scene"]["actor_model"]["model_name"], "default-model")

    def test_missing_role_does_not_report_borrowed_model_or_database(self):
        aike, linyin = self.profiles(available={"aike"})
        self.assertTrue(aike["ready"])
        self.assertFalse(linyin["ready"])
        self.assertEqual(linyin["memory"]["database"], "")
        self.assertEqual(linyin["chat_model"]["model_name"], "")
        self.assertFalse(linyin["voice"]["sample_available"])
        self.assertTrue(all(item["state"] == "blocked" for item in linyin["capabilities"]))

    def test_both_personas_support_classifier_and_attachments_in_v2(self):
        rows = self.profiles(self.config(
            PERSONA_ROUTING_V2_BOT_IDS='2000000001,3000000001',
            PERSONA_MEMORY_V2_BOT_IDS='2000000001,3000000001',
            ENABLE_CHAT_STICKER_ATTACHMENTS='true', ENABLE_REMOTE_STICKER_CLASSIFIER='true',
            STICKER_CLASSIFIER_API_KEY='unit-key', STICKER_CLASSIFIER_BASE_URL='https://unit.invalid',
            STICKER_CLASSIFIER_MODEL='unit-classifier',
        ))
        a, b = [{item['key']: item for item in row['capabilities']} for row in rows]
        self.assertEqual(a['sticker_classifier']['state'], 'enabled')
        self.assertEqual(a['sticker_attachments']['state'], 'enabled')
        self.assertEqual(b['sticker_classifier']['state'], 'enabled')
        self.assertEqual(b['sticker_attachments']['state'], 'enabled')
        self.assertNotIn('当前不调度', a['sticker_classifier']['detail'])

    def test_sticker_attachment_configuration_matches_runtime_validation(self):
        row = self.profiles(self.config(
            ENABLE_CHAT_STICKER_ATTACHMENTS='true', ENABLE_REMOTE_STICKER_CLASSIFIER='true',
            STICKER_CLASSIFIER_API_KEY='unit-key', STICKER_CLASSIFIER_BASE_URL='http://unit.invalid',
            STICKER_CLASSIFIER_MODEL='unit-classifier',
        ))[0]
        capabilities = {item['key']: item for item in row['capabilities']}
        self.assertEqual(capabilities['sticker_classifier']['state'], 'incomplete')
        self.assertEqual(capabilities['sticker_attachments']['state'], 'incomplete')

    def test_incomplete_vision_is_not_reported_as_chat_model(self):
        row = self.profiles(self.config(PERSONA_VISION_MODEL=""))[1]
        self.assertFalse(row["vision_model"]["configured"])
        self.assertEqual(row["chat_model"]["model_name"], "persona-model")

    def test_deepseek_vision_display_matches_independent_runtime_route(self):
        aike, linyin = self.profiles(self.config(
            AIKE_LLM_BASE_URL="https://api.deepseek.com", PERSONA_VISION_MODEL="deepseek-flash",
            PERSONA_VISION_MAX_TOKENS="4096", PERSONA_VISION_REASONING_EFFORT="max",
        ))
        model = linyin["vision_model"]
        self.assertEqual(model["model_name"], "deepseek-flash")
        self.assertEqual(model["provider"], "persona_deepseek")
        self.assertEqual(model["max_tokens"], 4096)
        self.assertEqual(model["reasoning_effort"], "max")
        self.assertTrue(model["configured"])
        self.assertEqual(linyin["chat_model"]["model_name"], "persona-model")
        self.assertEqual(aike["vision_model"]["provider"], "aliyun_bailian")
        blank = self.profiles(self.config(PERSONA_VISION_MODEL="deepseek-flash", PERSONA_VISION_API_KEY=""))[1]
        self.assertFalse(blank["vision_model"]["configured"])
        self.assertEqual(blank["vision_model"]["provider"], "persona_deepseek")

    def test_invalid_bailian_contract_is_visible(self):
        row = self.profiles(self.config(ALIYUN_BAILIAN_BASE_URL="https://invalid.example"))[0]
        self.assertFalse(row["vision_model"]["configured"])

    def test_swapped_scene_accounts_are_not_reported_as_ready(self):
        rows = self.profiles(self.config(SHARED_SCENE_AIKE_BOT_ID="3000000001", SHARED_SCENE_LINYIN_BOT_ID="2000000001"))
        for row in rows:
            scene = next(item for item in row["capabilities"] if item["key"] == "scene")
            self.assertEqual(scene["state"], "incomplete")
            self.assertFalse(row["scene"]["actor_model"]["configured"])

    def test_profile_has_no_secrets_prompt_or_mainagent_configuration(self):
        encoded = json.dumps(self.profiles())
        for value in ("SECRET-DEFAULT", "SECRET-PERSONA", "SECRET-VISION", "main_agent_model", "prompts/", "voice-samples/"):
            self.assertNotIn(value, encoded)

    def test_settings_does_not_create_missing_databases(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(self.module, "PROJECT_ROOT", Path(temp)):
            self.profiles()
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_each_account_reads_its_own_sample_even_when_voice_reply_disabled(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); content = self.wav()
            (root / "test-aike.wav").write_bytes(content)
            (root / "test-linyin.wav").write_bytes(content)
            with patch.object(self.module, "VOICE_SAMPLE_ROOT", root), patch.object(self.module, "available_bound_role_card_keys", return_value={"aike", "linyin"}):
                self.assertEqual(self.module.read_account_voice_sample(self.config(ENABLE_TTS="false"), "2000000001"), content)
                self.assertEqual(self.module.read_account_voice_sample(self.config(), "3000000001"), content)
                (root / "test-linyin.wav").unlink()
                with self.assertRaises((ValueError, OSError)):
                    self.module.read_account_voice_sample(self.config(), "3000000001")

    def test_unknown_account_and_bad_voice_identifier_are_rejected(self):
        with patch.object(self.module, "available_bound_role_card_keys", return_value={"aike", "linyin"}):
            for config, account in [(self.config(), "9999999999"), (self.config(TTS_VOICE="../test-linyin"), "2000000001")]:
                with self.assertRaises(ValueError): self.module.read_account_voice_sample(config, account)

    def test_missing_or_corrupt_audio_never_falls_back(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(self.module, "VOICE_SAMPLE_ROOT", Path(temp)):
            (Path(temp) / "test-linyin.wav").write_bytes(b"not a wave" * 10)
            self.assertFalse(self.module.voice_sample_available("test-linyin"))
            self.assertFalse(self.module.voice_sample_available("test-aike"))

    def test_truncated_wave_is_not_offered_for_playback(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(self.module, "VOICE_SAMPLE_ROOT", Path(temp)):
            (Path(temp) / "test-aike.wav").write_bytes(self.wav()[:-10])
            self.assertFalse(self.module.voice_sample_available("test-aike"))

    def test_invalid_binding_cannot_read_sample_even_if_file_exists(self):
        with patch.object(self.module, "available_bound_role_card_keys", return_value={"aike"}):
            with self.assertRaises(ValueError):
                self.module.read_account_voice_sample(self.config(), "3000000001")

    def test_preview_requires_settings_session_header_and_loopback(self):
        with patch.object(self.fastapi, "load_config", return_value=self.config()), patch.object(self.maintenance, "role_card_by_key", return_value=object()), patch.object(self.module, "available_bound_role_card_keys", return_value={"aike", "linyin"}), patch.object(self.module, "read_account_voice_sample", return_value=self.wav()) as read:
            client = TestClient(self.fastapi.create_owner_console_fastapi_app(), base_url="http://127.0.0.1")
            path = "/api/v1/owner-console/settings/accounts/2000000001/voice-sample"
            header = {"X-Owner-Console-Action": "persona-voice-sample-v1"}
            self.assertEqual(client.get(path, headers=header).status_code, 403)
            self.assertEqual(client.get("/api/v1/owner-console/settings").status_code, 200)
            self.assertEqual(client.get(path).status_code, 403)
            self.assertEqual(client.get(path, headers={**header, "Host": "outside.example"}).status_code, 403)
            self.assertEqual(client.get(path, headers={**header, "Sec-Fetch-Site": "cross-site"}).status_code, 403)
            response = client.get(path, headers=header)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.content, self.wav())
            self.assertIn("no-store", response.headers["cache-control"])
            self.assertEqual(read.call_count, 1)


if __name__ == "__main__":
    unittest.main()
