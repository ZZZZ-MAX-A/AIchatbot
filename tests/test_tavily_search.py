from __future__ import annotations

import asyncio
import json
import unittest

from pure_ai_chat_loader import load_tavily_search_modules


class FakeTavilyTransport:
    def __init__(self, response) -> None:
        self.response = response
        self.calls = []

    async def post_json(self, endpoint, **kwargs):
        self.calls.append((endpoint, kwargs))
        return self.response


class TavilyBasicSearchProviderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = load_tavily_search_modules()
        cls.security = modules["security"]
        cls.search = modules["search"]
        cls.tavily = modules["tavily"]

    def response(self, payload, *, status_code=200, content_type="application/json"):
        return self.tavily.TavilyHttpResponse(
            status_code=status_code,
            content_type=content_type,
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )

    def provider(self, response, **kwargs):
        transport = FakeTavilyTransport(response)
        provider = self.tavily.TavilyBasicSearchProvider(
            api_key="tvly-test-secret",
            transport=transport,
            **kwargs,
        )
        return provider, transport

    def official_shape(self):
        return {
            "query": "Python 3.14 有哪些主要新特性",
            "follow_up_questions": None,
            "answer": None,
            "images": [],
            "results": [
                {
                    "title": "What’s New In Python 3.14",
                    "url": "https://docs.python.org/3.14/whatsnew/3.14.html",
                    "content": "Python 3.14 的主要新特性概览。",
                    "score": 0.99,
                    "raw_content": None,
                }
            ],
            "response_time": 1.5,
        }

    def test_provider_sends_only_fixed_basic_search_contract(self):
        provider, transport = self.provider(self.response(self.official_shape()))

        result = asyncio.run(
            provider.search("Python 3.14 有哪些主要新特性", max_results=3)
        )

        self.assertEqual(len(transport.calls), 1)
        endpoint, request = transport.calls[0]
        self.assertEqual(endpoint, "https://api.tavily.com/search")
        self.assertEqual(
            request["headers"]["Authorization"],
            "Bearer tvly-test-secret",
        )
        self.assertEqual(request["headers"]["Accept"], "application/json")
        self.assertEqual(
            request["json_body"],
            {
                "query": "Python 3.14 有哪些主要新特性",
                "search_depth": "basic",
                "max_results": 3,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "auto_parameters": False,
            },
        )
        self.assertEqual(request["timeout_seconds"], 10)
        self.assertEqual(request["max_response_bytes"], 262_144)
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].title, "What’s New In Python 3.14")
        self.assertEqual(result.results[0].snippet, "Python 3.14 的主要新特性概览。")
        self.assertEqual(
            result.results[0].source_url,
            "https://docs.python.org/3.14/whatsnew/3.14.html",
        )
        self.assertEqual(result.response_bytes, len(self.response(self.official_shape()).body))

    def test_provider_output_runs_through_existing_sanitizer_and_formatter(self):
        provider, _transport = self.provider(self.response(self.official_shape()))

        execution = asyncio.run(
            self.search.execute_external_search(
                provider,
                "Python 3.14 有哪些主要新特性",
            )
        )

        self.assertEqual(execution.provider_name, "tavily")
        self.assertEqual(execution.external_request_count, 1)
        self.assertEqual(len(execution.results), 1)
        self.assertEqual(execution.results[0].source_host, "docs.python.org")
        self.assertNotIn("https://", execution.response_text)
        self.assertIn("来源：docs.python.org", execution.response_text)

    def test_provider_ignores_answer_images_raw_content_and_unknown_fields(self):
        payload = self.official_shape()
        payload["answer"] = "This must not enter the project response."
        payload["images"] = ["https://example.com/private.png"]
        payload["unknown_future_field"] = "ignored"
        payload["results"][0]["raw_content"] = "raw content must be ignored"
        provider, _transport = self.provider(self.response(payload))

        result = asyncio.run(provider.search("公开问题", max_results=3))
        serialized = repr(result)

        self.assertNotIn("must not enter", serialized)
        self.assertNotIn("private.png", serialized)
        self.assertNotIn("raw content must be ignored", serialized)
        self.assertNotIn("unknown_future_field", serialized)

    def test_provider_deterministically_cleans_and_limits_tavily_content(self):
        payload = self.official_shape()
        payload["results"][0]["content"] = (
            "### 页面导航¶\n"
            "* **第一项** | __第二项__ `code`\n"
            "正文 " + "内容" * 300
        )
        provider, _transport = self.provider(self.response(payload))

        result = asyncio.run(provider.search("公开问题", max_results=3))
        snippet = result.results[0].snippet

        self.assertLessEqual(len(snippet), self.tavily.TAVILY_MAX_CONTENT_CHARS)
        self.assertNotIn("###", snippet)
        self.assertNotIn("**", snippet)
        self.assertNotIn("__", snippet)
        self.assertNotIn("|", snippet)
        self.assertNotIn("¶", snippet)
        self.assertNotIn("`", snippet)
        self.assertIn("页面导航", snippet)
        self.assertIn("第一项", snippet)
        self.assertIn("第二项", snippet)
        self.assertIn("code", snippet)
        self.assertTrue(snippet.endswith("..."))

    def test_provider_rejects_missing_or_unsafe_api_keys(self):
        response = self.response(self.official_shape())
        for key in ("", "   ", "tvly-test\r\nInjected: value", "a b"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    self.tavily.TavilyBasicSearchProvider(
                        api_key=key,
                        transport=FakeTavilyTransport(response),
                    )

    def test_provider_rejects_expanded_result_budget_before_transport(self):
        provider, transport = self.provider(self.response(self.official_shape()))

        for value in (0, 4, True, "3"):
            with self.subTest(value=value):
                with self.assertRaises(self.security.ExternalReadPolicyError) as raised:
                    asyncio.run(provider.search("公开问题", max_results=value))
                self.assertEqual(
                    raised.exception.category,
                    self.security.ExternalReadPolicyCategory.INVALID_BUDGET,
                )
        self.assertEqual(transport.calls, [])

    def test_provider_maps_http_and_contract_failures_to_safe_categories(self):
        cases = (
            (
                self.response(
                    {"detail": {"error": "Authorization: Bearer must-not-leak"}},
                    status_code=401,
                ),
                self.security.ExternalReadPolicyCategory.AUTHENTICATION_FAILED,
            ),
            (
                self.response({"detail": "forbidden"}, status_code=403),
                self.security.ExternalReadPolicyCategory.AUTHENTICATION_FAILED,
            ),
            (
                self.response({"detail": "rate limited"}, status_code=429),
                self.security.ExternalReadPolicyCategory.RATE_LIMITED,
            ),
            (
                self.response({"detail": "server unavailable"}, status_code=503),
                self.security.ExternalReadPolicyCategory.PROVIDER_UNAVAILABLE,
            ),
            (
                self.response({"results": []}, content_type="text/html"),
                self.security.ExternalReadPolicyCategory.INVALID_PROVIDER_RESPONSE,
            ),
            (
                self.response({"results": "invalid"}),
                self.security.ExternalReadPolicyCategory.INVALID_PROVIDER_RESPONSE,
            ),
        )
        for response, category in cases:
            with self.subTest(category=category):
                provider, _transport = self.provider(response)
                with self.assertRaises(self.security.ExternalReadPolicyError) as raised:
                    asyncio.run(provider.search("公开问题", max_results=3))
                self.assertEqual(raised.exception.category, category)
                self.assertNotIn("must-not-leak", str(raised.exception))

    def test_provider_enforces_response_byte_budget_again(self):
        response = self.tavily.TavilyHttpResponse(
            status_code=200,
            content_type="application/json",
            body=b"x" * 65,
        )
        provider, _transport = self.provider(response, max_response_bytes=64)

        with self.assertRaises(self.security.ExternalReadPolicyError) as raised:
            asyncio.run(provider.search("公开问题", max_results=3))

        self.assertEqual(
            raised.exception.category,
            self.security.ExternalReadPolicyCategory.RESPONSE_TOO_LARGE,
        )


if __name__ == "__main__":
    unittest.main()
