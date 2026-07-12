from __future__ import annotations

import asyncio
import unittest

from pure_ai_chat_loader import load_tavily_search_modules


class FakeTavilyTransport:
    def __init__(self, response) -> None:
        self.response = response
        self.calls = []

    async def post_json(
        self,
        endpoint,
        *,
        headers,
        json_body,
        timeout_seconds,
        max_response_bytes,
    ):
        self.calls.append(
            {
                "endpoint": endpoint,
                "headers": headers,
                "body": json_body,
                "timeout_seconds": timeout_seconds,
                "max_response_bytes": max_response_bytes,
            }
        )
        return self.response


class TavilyExternalReadExecutorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.modules = load_tavily_search_modules()
        cls.tavily = cls.modules["tavily"]
        cls.executor_module = cls.modules["tavily_executor"]

    def response(self, body: str):
        return self.tavily.TavilyHttpResponse(
            status_code=200,
            content_type="application/json",
            body=body.encode("utf-8"),
        )

    def test_fixed_executor_maps_one_search_to_formal_ephemeral_payload(self):
        transport = FakeTavilyTransport(
            self.response(
                '{"results": ['
                '{"title": "Python 官方文档", '
                '"url": "https://docs.python.org/zh-cn/3/", '
                '"content": "Python 3 中文官方资料。", '
                '"score": 0.99, "raw_content": "must-not-pass"}'
                ']}'
            )
        )
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            timeout_seconds=7,
            transport=transport,
        )

        payload = asyncio.run(executor("  Python 3 中文官方文档  "))

        self.assertEqual(len(transport.calls), 1)
        call = transport.calls[0]
        self.assertEqual(call["timeout_seconds"], 7)
        self.assertEqual(call["body"]["search_depth"], "basic")
        self.assertEqual(call["body"]["max_results"], 3)
        self.assertFalse(call["body"]["include_answer"])
        self.assertFalse(call["body"]["include_raw_content"])
        self.assertFalse(call["body"]["include_images"])
        self.assertEqual(payload.provider_name, "tavily")
        self.assertEqual(payload.result_count, 1)
        self.assertEqual(payload.source_host_count, 1)
        self.assertEqual(payload.external_request_count, 1)
        self.assertEqual(payload.status_category, "completed")
        self.assertEqual(payload.error_category, "none")
        self.assertIn("docs.python.org", payload.report_text)
        self.assertNotIn("must-not-pass", payload.report_text)
        self.assertNotIn("tvly-unit-secret", payload.report_text)
        self.assertNotIn("https://", payload.report_text)

    def test_no_results_maps_to_no_results_without_a_second_request(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
        )

        payload = asyncio.run(executor("公开天气信息"))

        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(payload.result_count, 0)
        self.assertEqual(payload.status_category, "no_results")
        self.assertEqual(payload.external_request_count, 1)

    def test_factory_rejects_missing_key_and_unsafe_budget_before_network(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))
        with self.assertRaises(ValueError):
            self.executor_module.create_tavily_external_read_executor(
                api_key="",
                transport=transport,
            )
        with self.assertRaises(self.modules["security"].ExternalReadPolicyError):
            self.executor_module.create_tavily_external_read_executor(
                api_key="tvly-unit-secret",
                timeout_seconds=16,
                transport=transport,
            )
        self.assertEqual(transport.calls, [])

    def test_executor_repr_does_not_expose_api_key(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))
        executor = self.executor_module.create_tavily_external_read_executor(
            api_key="tvly-unit-secret",
            transport=transport,
        )

        self.assertNotIn("tvly-unit-secret", repr(executor))

    def test_configured_factory_stays_absent_while_feature_is_disabled(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))

        executor = self.executor_module.create_configured_tavily_external_read_executor(
            feature_enabled=False,
            api_key="tvly-unit-secret",
            timeout_seconds=99,
            transport=transport,
        )

        self.assertIsNone(executor)
        self.assertEqual(transport.calls, [])

    def test_configured_factory_fails_closed_for_invalid_key_or_budget(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))

        missing_key = self.executor_module.create_configured_tavily_external_read_executor(
            feature_enabled=True,
            api_key="",
            timeout_seconds=10,
            transport=transport,
        )
        invalid_budget = self.executor_module.create_configured_tavily_external_read_executor(
            feature_enabled=True,
            api_key="tvly-unit-secret",
            timeout_seconds=16,
            transport=transport,
        )

        self.assertIsNone(missing_key)
        self.assertIsNone(invalid_budget)
        self.assertEqual(transport.calls, [])

    def test_configured_factory_builds_only_with_all_required_gates(self):
        transport = FakeTavilyTransport(self.response('{"results": []}'))

        executor = self.executor_module.create_configured_tavily_external_read_executor(
            feature_enabled=True,
            api_key="tvly-unit-secret",
            timeout_seconds=10,
            transport=transport,
        )

        self.assertIsInstance(executor, self.executor_module.TavilyExternalReadExecutor)
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
