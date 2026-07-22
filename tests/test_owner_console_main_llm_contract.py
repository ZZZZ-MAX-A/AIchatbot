from __future__ import annotations

import json
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class OwnerConsoleMainLlmContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.contract = load_module(
            "src.plugins.ai_chat.owner_console_main_llm_contract",
            AI_CHAT_ROOT / "owner_console_main_llm_contract.py",
        )

    @staticmethod
    def config(**overrides):
        values = {
            "main_llm_api_key": "test-key",
            "main_llm_base_url": "https://main.example/v1",
            "main_llm_model": "main-test-model",
            "enable_main_agent": True,
            "main_agent_use_llm": True,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def expected_text(self) -> str:
        return json.dumps(
            self.contract.MAIN_LLM_CONTRACT_EXPECTED_RESPONSE,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def test_fixed_executor_calls_one_unbound_model_with_only_registered_messages(self):
        calls: list[object] = []

        class FakeModel:
            def invoke(_self, messages):
                calls.append(messages)
                return SimpleNamespace(
                    content=self.expected_text(),
                    usage_metadata={
                        "input_tokens": 51,
                        "output_tokens": 42,
                        "total_tokens": 93,
                    },
                    tool_calls=[],
                    invalid_tool_calls=[],
                )

        clock = iter((1_000_000_000, 1_125_000_000))
        executor = self.contract.MainLlmContractExecutor(
            config_provider=self.config,
            model_factory=lambda _config: FakeModel(),
            monotonic_ns=lambda: next(clock),
        )

        evidence = executor()

        self.assertEqual(len(calls), 1)
        self.assertEqual(
            calls[0],
            self.contract.MAIN_LLM_CONTRACT_MESSAGES,
        )
        self.assertTrue(evidence.contract_valid)
        self.assertTrue(evidence.usage_metadata_available)
        self.assertEqual(evidence.input_tokens, 51)
        self.assertEqual(evidence.output_tokens, 42)
        self.assertEqual(evidence.total_tokens, 93)
        self.assertFalse(evidence.tool_calls_present)
        self.assertEqual(evidence.elapsed_ms, 125)
        self.assertTrue(evidence.runtime_feature_enabled)

    def test_contract_rejects_extra_duplicate_or_wrong_fields_and_tool_calls(self):
        contract = self.contract
        wrong_payloads = (
            "not-json",
            '```json\n{"status":"ok"}\n```',
            self.expected_text()[:-1] + ',"extra":true}',
            self.expected_text().replace('"sum":42', '"sum":43'),
            (
                '{"contract_version":"main_llm.fixed.v1",'
                '"probe_id":"p2_49c","marker":"amber-17",'
                '"sum":42,"sum":42,"status":"ok"}'
            ),
        )
        for text in wrong_payloads:
            with self.subTest(text=text):
                self.assertFalse(
                    contract._contract_valid(text, tool_calls_present=False)
                )
        self.assertFalse(
            contract._contract_valid(
                self.expected_text(),
                tool_calls_present=True,
            )
        )

    def test_content_parts_and_legacy_token_usage_are_supported_without_content_leak(self):
        response = SimpleNamespace(
            content=[
                {"type": "text", "text": self.expected_text()[:40]},
                {"type": "text", "text": self.expected_text()[40:]},
            ],
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 44,
                    "completion_tokens": 38,
                    "total_tokens": 82,
                }
            },
            additional_kwargs={},
        )
        clock = iter((5_000_000_000, 5_010_000_000))
        evidence = self.contract.MainLlmContractExecutor(
            config_provider=self.config,
            model_factory=lambda _config: SimpleNamespace(
                invoke=lambda _messages: response
            ),
            monotonic_ns=lambda: next(clock),
        )()

        self.assertTrue(evidence.contract_valid)
        self.assertEqual(
            (evidence.input_tokens, evidence.output_tokens, evidence.total_tokens),
            (44, 38, 82),
        )
        rendered = repr(evidence)
        self.assertNotIn("amber-17", rendered)
        self.assertNotIn("test-key", rendered)
        self.assertNotIn("main.example", rendered)

    def test_usage_absence_remains_unavailable_instead_of_zero(self):
        clock = iter((7_000_000_000, 7_020_000_000))
        evidence = self.contract.MainLlmContractExecutor(
            config_provider=self.config,
            model_factory=lambda _config: SimpleNamespace(
                invoke=lambda _messages: {"content": self.expected_text()}
            ),
            monotonic_ns=lambda: next(clock),
        )()

        self.assertTrue(evidence.contract_valid)
        self.assertFalse(evidence.usage_metadata_available)
        self.assertIsNone(evidence.input_tokens)
        self.assertIsNone(evidence.output_tokens)
        self.assertIsNone(evidence.total_tokens)

    def test_preflight_rejects_invalid_config_without_building_or_calling_model(self):
        calls: list[str] = []
        executor = self.contract.MainLlmContractExecutor(
            config_provider=lambda: self.config(main_llm_api_key=""),
            model_factory=lambda _config: calls.append("built"),
        )

        with self.assertRaises(self.contract.MainLlmContractFailure) as raised:
            executor()

        self.assertEqual(raised.exception.stage, "preflight")
        self.assertEqual(raised.exception.code, "invalid_configuration")
        self.assertFalse(raised.exception.llm_called)
        self.assertEqual(calls, [])

    def test_request_errors_map_to_stable_codes_without_preserving_raw_exception(self):
        cases = (
            (401, "authorization_failed"),
            (403, "authorization_failed"),
            (404, "model_not_found"),
            (429, "model_rate_limited"),
            (400, "main_llm_request_rejected"),
        )

        for status_code, expected_code in cases:
            with self.subTest(status_code=status_code):
                class RequestFailure(RuntimeError):
                    pass

                error = RequestFailure(
                    "private api_key=sk-secret https://private.invalid"
                )
                error.status_code = status_code
                clock = iter((9_000_000_000, 9_005_000_000))
                executor = self.contract.MainLlmContractExecutor(
                    config_provider=self.config,
                    model_factory=lambda _config, exc=error: SimpleNamespace(
                        invoke=lambda _messages: (_ for _ in ()).throw(exc)
                    ),
                    monotonic_ns=lambda: next(clock),
                )
                with self.assertRaises(
                    self.contract.MainLlmContractFailure
                ) as raised:
                    executor()
                failure = raised.exception
                self.assertEqual(failure.code, expected_code)
                self.assertTrue(failure.llm_called)
                self.assertEqual(failure.elapsed_ms, 5)
                self.assertNotIn("sk-secret", repr(failure.__dict__))
                self.assertNotIn("private.invalid", repr(failure.__dict__))

    def test_default_model_factory_disables_retries_and_bounds_output(self):
        calls: list[dict[str, object]] = []
        fake_module = types.ModuleType("langchain_openai")

        def fake_chat_openai(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace()

        fake_module.ChatOpenAI = fake_chat_openai
        with patch.dict(sys.modules, {"langchain_openai": fake_module}):
            self.contract._build_main_llm_contract_model(self.config())

        self.assertEqual(len(calls), 1)
        kwargs = calls[0]
        self.assertEqual(kwargs["timeout"], 30)
        self.assertEqual(kwargs["max_retries"], 0)
        self.assertFalse(kwargs["streaming"])
        self.assertEqual(kwargs["max_tokens"], 256)
        self.assertNotIn("tools", kwargs)
        self.assertNotIn("temperature", kwargs)
        self.assertNotIn("response_format", kwargs)

    def test_contract_module_has_no_database_rag_qq_or_reliability_dependency(self):
        source = (AI_CHAT_ROOT / "owner_console_main_llm_contract.py").read_text(
            encoding="utf-8"
        ).lower()
        for forbidden in (
            "from .database",
            "from .rag",
            "agent_tasks",
            "reliability_events",
            "toolregistry",
            "mainagentstate",
            "nonebot",
            "send_private_msg",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
