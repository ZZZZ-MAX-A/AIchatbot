from __future__ import annotations

import json
import unittest

from pure_ai_chat_loader import load_scene_hub_modules


class SceneDirectorTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.director = load_scene_hub_modules()["director"]

    def valid_interaction(self) -> str:
        return json.dumps(
            {
                "schema_version": 1,
                "mode": "interaction",
                "steps": [
                    {
                        "speaker": "aike",
                        "audience": "linyin",
                        "depends_on": None,
                        "requires_prior_send_success": False,
                        "include_prior_reply": False,
                    },
                    {
                        "speaker": "linyin",
                        "audience": "aike",
                        "depends_on": "aike",
                        "requires_prior_send_success": True,
                        "include_prior_reply": True,
                    },
                ],
                "reason_code": "directed_interaction",
                "confidence": 0.98,
            }
        )

    def test_directed_greeting_contract_requires_send_dependency(self):
        result = self.director.parse_scene_plan(self.valid_interaction())

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.plan.mode, "interaction")
        self.assertEqual([step.speaker for step in result.plan.steps], ["aike", "linyin"])
        self.assertTrue(result.plan.steps[1].requires_prior_send_success)
        self.assertTrue(result.plan.steps[1].include_prior_reply)

    def test_prompt_distinguishes_directed_introduction_from_talking_about_persona(self):
        prompt = self.director.DIRECTOR_SYSTEM_PROMPT

        self.assertIn(
            "爱可，今天是凛音第一天来你给她介绍一下你自己吧",
            prompt,
        )
        self.assertIn("必须是 interaction：aike 先向 linyin 介绍自己", prompt)
        self.assertIn(
            "凛音，爱可是第一次见你，你向她介绍一下自己吧",
            prompt,
        )
        self.assertIn("必须是 interaction：linyin 先向 aike 介绍自己", prompt)
        self.assertIn("爱可，你觉得凛音是怎样的人？", prompt)
        self.assertIn("是 single", prompt)
        self.assertIn("谈论另一个角色", prompt)
        self.assertIn("对另一个角色说话或执行交流行为", prompt)
        self.assertIn("正确解析代词", prompt)

    def test_unknown_field_or_dialogue_field_fails_closed(self):
        payload = json.loads(self.valid_interaction())
        payload["dialogue"] = "爱可先说你好"

        result = self.director.parse_scene_plan(json.dumps(payload))

        self.assertEqual(result.status, "contract_invalid")
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.plan.mode, "none")
        self.assertEqual(result.plan.steps, ())

    def test_interaction_without_waiting_is_invalid(self):
        payload = json.loads(self.valid_interaction())
        payload["steps"][1]["requires_prior_send_success"] = False

        result = self.director.parse_scene_plan(json.dumps(payload))

        self.assertEqual(result.status, "contract_invalid")
        self.assertEqual(result.plan.mode, "none")

    def test_duplicate_speaker_and_more_than_two_steps_are_invalid(self):
        payload = json.loads(self.valid_interaction())
        payload["steps"][1]["speaker"] = "aike"
        duplicate = self.director.parse_scene_plan(json.dumps(payload))
        self.assertEqual(duplicate.status, "contract_invalid")

        payload = json.loads(self.valid_interaction())
        payload["steps"].append(payload["steps"][0])
        too_many = self.director.parse_scene_plan(json.dumps(payload))
        self.assertEqual(too_many.status, "contract_invalid")

    def test_settings_are_explicit_https_and_provider_has_no_auto_fallback(self):
        settings = self.director.SceneDirectorSettings(
            enabled=True,
            provider="qwen",
            api_key="secret",
            base_url="https://example.invalid/v1",
            model="qwen-turbo",
            timeout_seconds=8,
        )
        self.assertEqual(self.director.director_settings_status(settings), "ready")
        self.assertNotIn("secret", repr(settings))

        invalid = self.director.SceneDirectorSettings(
            enabled=True,
            provider="automatic",
            api_key="secret",
            base_url="https://example.invalid/v1",
            model="qwen-turbo",
        )
        self.assertEqual(self.director.director_settings_status(invalid), "invalid_config")

    async def test_director_transport_is_called_exactly_once_on_invalid_json(self):
        calls = []

        async def transport(settings, messages):
            calls.append((settings.provider, messages))
            return "not-json"

        settings = self.director.SceneDirectorSettings(
            enabled=True,
            provider="deepseek",
            api_key="secret",
            base_url="https://example.invalid/v1",
            model="deepseek-chat",
        )
        result = await self.director.direct_scene_turn(
            settings, [], "爱可给凛音打一个招呼", transport=transport
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(result.status, "json_invalid")
        self.assertEqual(result.plan.mode, "none")


if __name__ == "__main__":
    unittest.main()
