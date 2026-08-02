from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import unittest

import httpx

from pure_ai_chat_loader import load_chat_weather_module


class ChatWeatherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.weather = load_chat_weather_module()
        cls.today = date(2026, 7, 31)

    def setUp(self) -> None:
        self.weather.clear_weather_cache()

    def test_explicit_weather_requires_no_classifier(self):
        intent = self.weather.detect_weather_intent(
            "爱可，萍乡明天会下雨吗？",
            mode="owner_explicit",
            today=self.today,
        )

        self.assertIsNotNone(intent)
        self.assertEqual(intent.kind.value, "explicit")
        self.assertEqual(intent.target_date, date(2026, 8, 1))

    def test_owner_auto_matches_near_future_outing(self):
        intent = self.weather.detect_weather_intent(
            "明天想出去逛逛",
            mode="owner_auto",
            today=self.today,
        )

        self.assertIsNotNone(intent)
        self.assertEqual(intent.kind.value, "implicit_outing")
        self.assertEqual(intent.target_date, date(2026, 8, 1))

    def test_explicit_only_does_not_match_implicit_outing(self):
        intent = self.weather.detect_weather_intent(
            "明天想出去逛逛",
            mode="owner_explicit",
            today=self.today,
        )

        self.assertIsNone(intent)

    def test_router_excludes_writing_translation_hypothetical_and_past(self):
        examples = (
            "帮我写一篇明天出去逛逛的故事",
            "把明天会下雨吗翻译成英语",
            "假设明天下雨应该怎么写",
            "昨天天气怎么样",
        )

        for text in examples:
            with self.subTest(text=text):
                self.assertIsNone(
                    self.weather.detect_weather_intent(
                        text,
                        mode="owner_auto",
                        today=self.today,
                    )
                )

    def payload(self, target_date: date | None = None):
        selected_date = target_date or self.today
        return {
            "timezone": "Asia/Shanghai",
            "daily": {
                "time": [selected_date.isoformat()],
                "weather_code": [61],
                "temperature_2m_max": [33.2],
                "temperature_2m_min": [26.4],
                "precipitation_probability_max": [70],
                "wind_speed_10m_max": [15.3],
            },
        }

    def test_structured_response_is_validated_and_formatted(self):
        fetched_at = datetime(
            2026,
            7,
            31,
            12,
            0,
            tzinfo=timezone(timedelta(hours=8)),
        )
        forecast = self.weather.parse_open_meteo_forecast(
            self.payload(),
            location="萍乡",
            target_date=self.today,
            fetched_at=fetched_at,
        )
        context = self.weather.build_weather_system_context(forecast)

        self.assertEqual(forecast.condition, "有雨")
        self.assertIn("地点：萍乡", context)
        self.assertIn("最大降水概率：70%", context)
        self.assertIn("萍乡今天", context)
        self.assertIn("不要向用户展示 YYYY-MM-DD", context)
        self.assertIn("只供本轮回答使用", context)
        self.assertNotIn("http", context)
        self.assertNotIn("Open-Meteo", context)

    def test_response_rejects_wrong_timezone_and_invalid_probability(self):
        wrong_timezone = self.payload()
        wrong_timezone["timezone"] = "UTC"
        with self.assertRaisesRegex(ValueError, "timezone"):
            self.weather.parse_open_meteo_forecast(
                wrong_timezone,
                location="萍乡",
                target_date=self.today,
            )

        invalid_probability = self.payload()
        invalid_probability["daily"]["precipitation_probability_max"] = [101]
        with self.assertRaisesRegex(ValueError, "precipitation_probability_max"):
            self.weather.parse_open_meteo_forecast(
                invalid_probability,
                location="萍乡",
                target_date=self.today,
            )

    def test_fetch_makes_one_bounded_request_without_retry(self):
        target_date = datetime.now(self.weather.CHINA_STANDARD_TIME).date()
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                json=self.payload(target_date),
            )

        async def run():
            transport = httpx.MockTransport(handler)
            async with httpx.AsyncClient(transport=transport) as client:
                return await self.weather.fetch_open_meteo_forecast(
                    latitude=27.62,
                    longitude=113.85,
                    location="萍乡",
                    target_date=target_date,
                    timeout_seconds=3,
                    client=client,
                )

        forecast = asyncio.run(run())

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.host, "api.open-meteo.com")
        self.assertEqual(forecast.location, "萍乡")

    def test_unavailable_context_forbids_weather_guessing(self):
        context = self.weather.build_weather_unavailable_system_context()

        self.assertIn("不得根据模型记忆猜测", context)
        self.assertNotIn("MainAgent", context)
        self.assertNotIn("Tavily", context)

    def test_validated_forecast_cache_is_short_lived_and_bounded(self):
        fetched_at = datetime(
            2026,
            7,
            31,
            12,
            0,
            tzinfo=timezone(timedelta(hours=8)),
        )
        forecast = self.weather.parse_open_meteo_forecast(
            self.payload(),
            location="萍乡",
            target_date=self.today,
            fetched_at=fetched_at,
        )
        self.weather.remember_weather_forecast(
            forecast,
            latitude=27.62,
            longitude=113.85,
            clock=lambda: 100.0,
        )

        cached = self.weather.cached_weather_forecast(
            location="萍乡",
            latitude=27.62,
            longitude=113.85,
            target_date=self.today,
            clock=lambda: 101.0,
        )
        expired = self.weather.cached_weather_forecast(
            location="萍乡",
            latitude=27.62,
            longitude=113.85,
            target_date=self.today,
            clock=lambda: 701.0,
        )

        self.assertEqual(cached, forecast)
        self.assertIsNone(expired)


class ChatWeatherIntegrationContractTests(unittest.TestCase):
    def test_weather_is_ephemeral_owner_private_chat_capability(self):
        plugin = Path(load_chat_weather_module().__file__)
        source = plugin.read_text(encoding="utf-8")
        runtime_source = plugin.with_name("__init__.py").read_text(encoding="utf-8")

        self.assertIn("OPEN_METEO_FORECAST_URL", source)
        self.assertNotIn("main_agent", source.lower())
        self.assertNotIn("tavily", source.lower())
        weather_start = runtime_source.index("async def build_chat_weather_context(")
        weather_end = runtime_source.index(
            "def combine_ephemeral_chat_system_contexts(",
            weather_start,
        )
        weather_block = runtime_source[weather_start:weather_end]
        self.assertIn("isinstance(event, PrivateMessageEvent)", weather_block)
        self.assertIn("is_owner(config, event)", weather_block)
        self.assertIn("except Exception", weather_block)
        self.assertIn("return build_weather_unavailable_system_context()", weather_block)


if __name__ == "__main__":
    unittest.main()
