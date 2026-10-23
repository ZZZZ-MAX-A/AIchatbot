from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import ast
import json
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import patch

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


ROOT = AI_CHAT_ROOT.parents[2]


class ConfigurationGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.config = load_module("src.plugins.ai_chat.config", AI_CHAT_ROOT / "config.py")
        cls.report = load_module("src.plugins.ai_chat.configuration_report", AI_CHAT_ROOT / "configuration_report.py")

    def test_invalid_protection_booleans_stop_loading_and_hide_values(self):
        for name in ("MAIN_AGENT_OWNER_ONLY", "MAIN_AGENT_REQUIRE_APPROVAL_FOR_WRITES", "CHAT_STICKER_OWNER_PRIVATE_ONLY"):
            with self.subTest(name=name):
                with self.assertRaises(self.config.ConfigValidationError) as caught:
                    self.config.load_config({name: "SECRET-TYPO"})
                self.assertIn(name, str(caught.exception))
                self.assertNotIn("SECRET-TYPO", str(caught.exception))

    def test_errors_are_aggregated_and_do_not_leak_values(self):
        with self.assertRaises(self.config.ConfigValidationError) as caught:
            self.config.load_config({"MAX_CONTEXT_MESSAGES": "SECRET-NUMBER", "AI_TEMPERATURE": "nan", "ENABLE_MAIN_AGENT": "typo"})
        self.assertEqual({issue.key for issue in caught.exception.issues}, {"MAX_CONTEXT_MESSAGES", "AI_TEMPERATURE", "ENABLE_MAIN_AGENT"})
        self.assertNotIn("SECRET-NUMBER", str(caught.exception))

    def test_capability_sentinels_still_load_but_are_reported(self):
        config = self.config.load_config({"TAVILY_TIMEOUT_SECONDS": "bad", "LOCAL_STICKER_MAX_FILE_BYTES": "bad", "CHAT_WEATHER_TIMEOUT_SECONDS": "inf"})
        self.assertEqual(config.tavily_timeout_seconds, 0)
        self.assertEqual(config.local_sticker_max_file_bytes, 0)
        self.assertEqual(config.chat_weather_timeout_seconds, 0)
        self.assertEqual(len(config.configuration_issues), 3)
        self.assertTrue(all(item.severity == "warning" for item in config.configuration_issues))

    def test_blank_credentials_do_not_inherit_old_names(self):
        config = self.config.load_config({"OPENAI_API_KEY": "OLD-SECRET", "AIKE_LLM_API_KEY": ""})
        self.assertEqual(config.aike_llm_api_key, "")
        self.assertEqual(dict(config.configuration_sources)["AIKE_LLM_API_KEY"], "explicit_empty")
        self.assertTrue(any(item.code == "legacy_ignored" for item in config.configuration_issues))
        self.assertNotIn("OLD-SECRET", repr(config.configuration_issues))

    def test_legacy_only_config_stays_explicitly_unconfigured(self):
        config = self.config.load_config({"OPENAI_API_KEY": "OLD-SECRET", "OPENAI_MODEL": "old-model"})
        self.assertEqual(config.aike_llm_api_key, "")
        self.assertNotEqual(config.aike_llm_model, "old-model")
        self.assertEqual(len(config.configuration_issues), 2)

    def test_unset_inherits_persona_and_explicit_blank_prevents_inheritance(self):
        common = {"PERSONA_LLM_API_KEY": "TEST-PERSONA", "PERSONA_LLM_MODEL": "test-model"}
        inherited = self.config.load_config(common)
        blank = self.config.load_config({**common, "PERSONA_VISION_API_KEY": "", "IMAGE_GEN_API_KEY": ""})
        self.assertEqual(inherited.persona_vision_api_key, "TEST-PERSONA")
        self.assertEqual(blank.persona_vision_api_key, "")
        self.assertEqual(blank.image_gen_api_key, "")

    def test_snapshot_does_not_mutate_environment_and_isolates_parallel_reads(self):
        before = dict(os.environ)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(self.config.load_config, [{"AIKE_LLM_MODEL": "first"}, {"AIKE_LLM_MODEL": "second"}]))
        self.assertEqual([item.aike_llm_model for item in results], ["first", "second"])
        self.assertEqual(dict(os.environ), before)
        self.assertTrue(all(item.configuration_snapshot_kind == "explicit_mapping" for item in results))

    def test_loading_does_not_reread_dotenv_or_hot_reload(self):
        with patch.object(self.config, "load_dotenv") as dotenv:
            self.config.load_config({})
            self.config.load_config({})
        dotenv.assert_not_called()

    def test_blank_numeric_uses_default_but_blank_bool_is_invalid(self):
        self.assertEqual(self.config.load_config({"MAX_CONTEXT_MESSAGES": ""}).max_context_messages, self.config.load_config({}).max_context_messages)
        with self.assertRaises(self.config.ConfigValidationError):
            self.config.load_config({"MAIN_AGENT_OWNER_ONLY": ""})

    def test_invalid_port_is_a_named_error(self):
        for value in ("bad", "0", "65536"):
            with self.subTest(value=value), self.assertRaisesRegex(self.config.ConfigValidationError, "PORT"):
                self.config.load_config({"PORT": value})

    def test_cloud_vision_does_not_require_ollama_but_embedding_does(self):
        config = self.config.load_config({"ENABLE_VISION": "true", "ALIYUN_BAILIAN_API_KEY": "TEST-KEY", "ALIYUN_BAILIAN_BASE_URL": "https://cloud.example/v1"})
        report = self.report.build_configuration_report(config)
        self.assertFalse(report["ollama_required"])
        self.assertTrue(report["vision"]["configured"])
        rag = self.report.build_configuration_report(self.config.load_config({"ENABLE_MEMORY_RAG": "true"}))
        self.assertEqual(rag["ollama_dependencies"], [{"purpose": "embedding", "loopback": True}])

    def test_optional_native_persona_dependency_is_distinct(self):
        config = self.config.load_config({"ENABLE_PERSONA_LLM_ROUTING": "true", "PERSONA_LLM_ROLE_CARD_KEYS": "test-role", "PERSONA_LLM_PROVIDER": "ollama", "PERSONA_LLM_BASE_URL": "http://127.0.0.1:11434", "PERSONA_LLM_MODEL": "test-model"})
        report = self.report.build_configuration_report(config)
        self.assertTrue(report["persona_local_ollama"])
        self.assertTrue(report["persona_chat"][0]["configured"])
        remote = self.config.load_config({"ENABLE_MEMORY_RAG": "true", "MEMORY_RAG_EMBEDDING_BASE_URL": "https://remote.example"})
        self.assertFalse(self.report.build_configuration_report(remote)["ollama_auto_ensure"])

    def test_report_exposes_no_credentials_identifiers_or_urls(self):
        config = self.config.load_config({"BOT_OWNER_QQ": "1234567890", "AIKE_LLM_API_KEY": "TEST-SECRET", "AIKE_LLM_BASE_URL": "https://user:pass@example/v1?token=hidden"})
        encoded = json.dumps(self.report.build_configuration_report(config))
        for value in ("TEST-SECRET", "1234567890", "user:pass", "token=hidden"):
            self.assertNotIn(value, encoded)

    def test_templates_are_identical_and_cover_loaded_keys(self):
        root = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertEqual(root, (ROOT / "config/.env.example").read_text(encoding="utf-8"))
        tree = ast.parse((AI_CHAT_ROOT / "config.py").read_text(encoding="utf-8"))
        readers = {"_env_get", "_bool_env", "_int_env", "_float_env", "_security_int_env", "_security_float_env", "_csv_env", "_trusted_path_roots_env", "_timezone_env", "_chat_weather_mode_env"}
        loaded = {node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in readers and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)}
        keys = re.findall(r"^([A-Z][A-Z0-9_]*)=", root, re.M)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertFalse(loaded - set(keys), loaded - set(keys))

    def test_preflight_cli_imports_no_bot_sdk_or_database_and_never_probes(self):
        code = "import sys,json;sys.path.insert(0,'scripts');from check_configuration import load_configuration_modules;c,r=load_configuration_modules();cfg=c.load_config({});assert not any(n in sys.modules for n in ['nonebot','openai','sqlite3']);print(json.dumps(r.build_configuration_report(cfg)))"
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["external_probes_executed"])
        self.assertFalse(report["database_opened"])

    def test_reliability_uses_configured_port_and_only_required_local_dependencies(self):
        with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
            spec = importlib.util.spec_from_file_location("configuration_reliability_test", ROOT / "scripts/reliability_inspection.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        config = self.config.load_config({
            "PORT": "8123", "AIKE_LLM_API_KEY": "TEST-KEY",
            "ENABLE_VISION": "true", "ALIYUN_BAILIAN_API_KEY": "TEST-CLOUD",
            "ALIYUN_BAILIAN_BASE_URL": "https://cloud.example/v1",
            "ENABLE_MEMORY_RAG": "true", "MEMORY_RAG_EMBEDDING_BASE_URL": "http://127.0.0.1:11555",
        })
        with (
            patch.object(module, "load_configuration_modules", return_value=(self.config, self.report)),
            patch.object(self.config, "load_config", return_value=config),
            patch.object(module, "tcp_reachable", return_value=True) as connect,
            patch.object(module, "database_readable", return_value=True),
        ):
            text = module.build_local_state_report()
        self.assertEqual([call.args for call in connect.call_args_list], [("127.0.0.1", 8123), ("127.0.0.1", 11555)])
        self.assertIn("aliyun_bailian", text)
        self.assertNotIn("视觉已开启但 Ollama 不可达", text)

    def test_invalid_reliability_config_never_opens_ports_or_database(self):
        with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
            spec = importlib.util.spec_from_file_location("configuration_invalid_reliability_test", ROOT / "scripts/reliability_inspection.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        issue = self.config.ConfigIssue("ENABLE_MAIN_AGENT", "invalid_boolean", "invalid boolean", "error")
        with (
            patch.object(module, "load_configuration_modules", return_value=(self.config, self.report)),
            patch.object(self.config, "load_config", side_effect=self.config.ConfigValidationError((issue,))),
            patch.object(module, "tcp_reachable") as connect,
            patch.object(module, "database_readable") as database,
        ):
            text = module.build_local_state_report()
        connect.assert_not_called()
        database.assert_not_called()
        self.assertIn("ENABLE_MAIN_AGENT", text)


if __name__ == "__main__":
    unittest.main()
