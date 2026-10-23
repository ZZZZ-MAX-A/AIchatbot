from __future__ import annotations

import unittest

from pure_ai_chat_loader import load_scene_hub_modules
from test_memory_audience import plugin_functions


class SceneMemberPrivacyTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = load_scene_hub_modules()

    async def trial(self, change_at):
        module = self.modules["hub"]
        director_module = self.modules["director"]
        hub = module.SceneHub(module.SceneHubSettings(
            enabled=True, group_id="30003", owner_id="10001",
            aike_bot_id="20001", linyin_bot_id="20002", member_cache_seconds=30,
        ))
        members = {"10001", "20001", "20002"}
        calls = []

        async def member_provider():
            if change_at == "lookup_error" and calls:
                raise RuntimeError("unavailable")
            return set(members)

        async def director(context, message):
            calls.append("director")
            if change_at == "director":
                members.add("outsider")
            return director_module.SceneDirectorResult("ready", director_module.ScenePlan(
                1, "interaction", (
                    director_module.ScenePlanStep("aike", "linyin", None, False, False),
                    director_module.ScenePlanStep("linyin", "aike", "aike", True, True),
                ), "directed_interaction", 0.99,
            ))

        async def actor(request):
            calls.append(f"actor:{request.speaker}")
            if change_at == "actor":
                members.add("outsider")
            return "你好。"

        async def sender(speaker, reply):
            calls.append(f"send:{speaker}")
            if change_at == "first_send":
                members.add("outsider")
            return True

        await hub._validated_members(member_provider)
        if change_at == "cached":
            members.add("outsider")
        result = await hub.handle_message(
            group_id="30003", sender_id="10001", source_bot_id="20001",
            event_id="privacy-event", owner_message="你们打个招呼",
            member_provider=member_provider, director=director, actor=actor, sender=sender,
        )
        return result, calls

    async def test_unchanged_members_preserve_both_private_continuity_actors(self):
        result, calls = await self.trial("unchanged")
        self.assertEqual(result.status, "completed")
        self.assertEqual(calls, ["director", "actor:aike", "send:aike", "actor:linyin", "send:linyin"])

    async def test_stale_cache_cannot_authorize_new_member(self):
        result, calls = await self.trial("cached")
        self.assertEqual(result.status, "member_set_mismatch")
        self.assertEqual(calls, [])

    async def test_member_joining_during_director_blocks_private_read(self):
        result, calls = await self.trial("director")
        self.assertEqual(result.status, "member_set_mismatch")
        self.assertEqual(calls, ["director"])

    async def test_member_joining_during_actor_blocks_send(self):
        result, calls = await self.trial("actor")
        self.assertEqual(result.status, "member_set_mismatch")
        self.assertEqual(calls, ["director", "actor:aike"])

    async def test_member_joining_after_first_send_blocks_second_actor(self):
        result, calls = await self.trial("first_send")
        self.assertEqual(result.status, "member_set_mismatch")
        self.assertEqual(calls, ["director", "actor:aike", "send:aike"])
        self.assertEqual(result.sent_speakers, ("aike",))

    async def test_member_lookup_error_fails_closed(self):
        result, calls = await self.trial("lookup_error")
        self.assertEqual(result.status, "member_lookup_failed")
        self.assertEqual(calls, ["director"])

    async def test_onebot_member_query_bypasses_adapter_cache(self):
        captured = []

        class Bot:
            async def call_api(self, method, **kwargs):
                captured.append((method, kwargs))
                return [{"user_id": "10001"}]

        ns = plugin_functions({"_scene_group_members"}, {})
        self.assertEqual(await ns["_scene_group_members"](Bot(), "30003"), {"10001"})
        self.assertEqual(captured, [("get_group_member_list", {"group_id": 30003, "no_cache": True})])


if __name__ == "__main__":
    unittest.main()
