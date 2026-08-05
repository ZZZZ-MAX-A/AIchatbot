from __future__ import annotations

import asyncio
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, load_scene_hub_modules


class SceneHubTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        modules = load_scene_hub_modules()
        cls.director = modules["director"]
        cls.hub_module = modules["hub"]

    def make_settings(self, **overrides):
        values = {
            "enabled": True,
            "group_id": "30003",
            "owner_id": "10001",
            "aike_bot_id": "20001",
            "linyin_bot_id": "20002",
            "max_context_events": 20,
            "max_reply_sentences": 3,
            "max_reply_chars": 160,
            "actor_max_tokens": 256,
            "director_context_events": 6,
            "director_circuit_seconds": 120,
            "member_cache_seconds": 30,
            "max_pending_turns": 1,
        }
        values.update(overrides)
        return self.hub_module.SceneHubSettings(**values)

    def interaction_result(self):
        step = self.director.ScenePlanStep
        plan = self.director.ScenePlan(
            1,
            "interaction",
            (
                step("aike", "linyin", None, False, False),
                step("linyin", "aike", "aike", True, True),
            ),
            "directed_interaction",
            0.98,
        )
        return self.director.SceneDirectorResult("ready", plan)

    async def run_turn(self, hub, *, sender_result=True, event_id="event-1", actor=None):
        timeline = []

        async def members():
            return {"10001", "20001", "20002"}

        async def director(context, owner_message):
            timeline.append(("director", owner_message, tuple(context)))
            return self.interaction_result()

        async def default_actor(request):
            timeline.append(
                (
                    "actor",
                    request.speaker,
                    None if request.prior_reply is None else request.prior_reply.text,
                )
            )
            return "你好。" if request.speaker == "aike" else "嗯，你好。"

        async def sender(speaker, reply):
            timeline.append(("send", speaker, reply))
            if isinstance(sender_result, dict):
                return sender_result.get(speaker, False)
            return sender_result

        result = await hub.handle_message(
            group_id="30003",
            sender_id="10001",
            source_bot_id="20001",
            event_id=event_id,
            owner_message="爱可给凛音打一个招呼",
            member_provider=members,
            director=director,
            actor=actor or default_actor,
            sender=sender,
        )
        return result, timeline

    async def test_interaction_waits_for_successful_send_and_passes_actual_text(self):
        hub = self.hub_module.SceneHub(self.make_settings())

        result, timeline = await self.run_turn(hub)

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.model_calls, 3)
        self.assertEqual(result.sent_speakers, ("aike", "linyin"))
        self.assertEqual(result.plan_mode, "interaction")
        self.assertEqual(result.planned_speakers, ("aike", "linyin"))
        self.assertEqual(
            [(item.speaker, item.status) for item in result.step_outcomes],
            [("aike", "sent"), ("linyin", "sent")],
        )
        self.assertEqual(
            [item[:2] for item in timeline],
            [
                ("director", "爱可给凛音打一个招呼"),
                ("actor", "aike"),
                ("send", "aike"),
                ("actor", "linyin"),
                ("send", "linyin"),
            ],
        )
        linyin_actor = next(
            item for item in timeline if item[:2] == ("actor", "linyin")
        )
        self.assertEqual(linyin_actor[2], "你好。")

    async def test_failed_first_send_skips_dependent_linyin_without_calling_it(self):
        hub = self.hub_module.SceneHub(self.make_settings())

        result, timeline = await self.run_turn(
            hub, sender_result={"aike": False, "linyin": True}
        )

        self.assertEqual(result.model_calls, 2)
        self.assertEqual(result.sent_speakers, ())
        self.assertIn("linyin", result.skipped_speakers)
        self.assertEqual(
            [(item.speaker, item.status) for item in result.step_outcomes],
            [("aike", "send_failed"), ("linyin", "dependency_not_sent")],
        )
        self.assertNotIn(("actor", "linyin", None), timeline)

    async def test_empty_first_reply_is_observable_and_skips_dependency(self):
        hub = self.hub_module.SceneHub(self.make_settings())

        async def empty_actor(request):
            return "" if request.speaker == "aike" else "不应调用"

        result, timeline = await self.run_turn(hub, actor=empty_actor)

        self.assertEqual(result.model_calls, 2)
        self.assertEqual(result.sent_speakers, ())
        self.assertEqual(
            [(item.speaker, item.status) for item in result.step_outcomes],
            [("aike", "empty_reply"), ("linyin", "dependency_not_sent")],
        )
        self.assertFalse(any(item[0] == "send" for item in timeline))

    async def test_same_event_received_by_second_bot_executes_only_once(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        first, _ = await self.run_turn(hub, event_id="same-event")
        second, timeline = await self.run_turn(hub, event_id="same-event")

        self.assertEqual(first.status, "completed")
        self.assertEqual(second.status, "duplicate")
        self.assertEqual(timeline, [])

    async def test_non_owner_bot_message_never_starts_a_turn(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        calls = []

        async def unexpected(*args):
            calls.append(args)
            raise AssertionError("must not be called")

        result = await hub.handle_message(
            group_id="30003",
            sender_id="20001",
            source_bot_id="20002",
            event_id="bot-reply",
            owner_message="你好。",
            member_provider=unexpected,
            director=unexpected,
            actor=unexpected,
            sender=unexpected,
        )

        self.assertEqual(result.status, "ignored_non_owner")
        self.assertEqual(calls, [])

    async def test_other_group_and_wrong_membership_fail_closed(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        calls = []

        async def unexpected(*args):
            calls.append(args)
            raise AssertionError("must not be called")

        other = await hub.handle_message(
            group_id="99999",
            sender_id="10001",
            source_bot_id="20001",
            event_id="other",
            owner_message="你好",
            member_provider=unexpected,
            director=unexpected,
            actor=unexpected,
            sender=unexpected,
        )
        self.assertEqual(other.status, "out_of_scope")

        async def wrong_members():
            return {"10001", "20001", "someone-else"}

        wrong = await hub.handle_message(
            group_id="30003",
            sender_id="10001",
            source_bot_id="20001",
            event_id="wrong-members",
            owner_message="你好",
            member_provider=wrong_members,
            director=unexpected,
            actor=unexpected,
            sender=unexpected,
        )
        self.assertEqual(wrong.status, "member_set_mismatch")
        self.assertEqual(calls, [])

    async def test_active_turn_drops_second_pending_owner_turn(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        started = asyncio.Event()
        release = asyncio.Event()

        async def members():
            return {"10001", "20001", "20002"}

        async def director(context, owner_message):
            started.set()
            await release.wait()
            return self.director.SceneDirectorResult(
                "ready",
                self.director.ScenePlan(1, "none", (), "no_reply", 1.0),
            )

        async def unused(*args):
            raise AssertionError("not used")

        first_task = asyncio.create_task(
            hub.handle_message(
                group_id="30003",
                sender_id="10001",
                source_bot_id="20001",
                event_id="first",
                owner_message="第一条",
                member_provider=members,
                director=director,
                actor=unused,
                sender=unused,
            )
        )
        await started.wait()
        second = await hub.handle_message(
            group_id="30003",
            sender_id="10001",
            source_bot_id="20002",
            event_id="second",
            owner_message="第二条",
            member_provider=members,
            director=director,
            actor=unused,
            sender=unused,
        )
        release.set()
        first = await first_task

        self.assertEqual(first.status, "completed")
        self.assertEqual(second.status, "busy")

    def test_group_reply_guard_limits_three_sentences_and_160_chars(self):
        guard = self.hub_module.normalize_group_reply
        self.assertEqual(
            guard("第一句。第二句！第三句？第四句。"),
            "第一句。第二句！第三句？",
        )
        long_reply = "这是一条没有任何句号的很长群聊回复" * 10
        trimmed = guard(long_reply)
        self.assertEqual(len(trimmed), 160)
        self.assertTrue(trimmed.endswith("…"))
        self.assertNotIn("\n", guard("第一句。\n第二句。"))

    def test_group_reply_guard_ignores_short_parenthetical_action_sentences(self):
        guard = self.hub_module.normalize_group_reply
        reply = (
            "爱可，你好。我是凛音，主人的私人女仆。"
            "（凛音微微颔首，语气平静温和。）"
            "主人的事情，我会认真照看好；以后也请多关照。"
        )

        self.assertEqual(guard(reply), reply)
        self.assertEqual(
            guard("第一句。（短动作。）第二句！第三句？第四句。"),
            "第一句。（短动作。）第二句！第三句？",
        )

    def test_group_reply_guard_never_cuts_inside_parentheses_at_char_limit(self):
        guard = self.hub_module.normalize_group_reply
        reply = "第一句。" + "（" + ("很长的动作" * 40) + "。）最后一句。"

        trimmed = guard(reply, max_chars=40)

        self.assertLessEqual(len(trimmed), 40)
        self.assertEqual(trimmed.count("（"), trimmed.count("）"))
        self.assertEqual(trimmed, "第一句。")

    def test_emergency_keyword_plan_routes_names_plural_and_default_once(self):
        build = self.hub_module.build_emergency_scene_plan

        def speakers(message):
            return tuple(step.speaker for step in build(message).steps)

        self.assertEqual(speakers("我想听听爱可的看法"), ("aike",))
        self.assertEqual(speakers("我想听听凛音的看法"), ("linyin",))
        self.assertEqual(speakers("请 AIKE 回答"), ("aike",))
        self.assertEqual(speakers("请 LINYIN 回答"), ("linyin",))
        self.assertEqual(speakers("爱可和凛音都说一下"), ("aike", "linyin"))
        self.assertEqual(speakers("凛音和爱可都说一下"), ("linyin", "aike"))
        self.assertEqual(speakers("爱可，想听你们两个说说"), ("aike", "linyin"))
        self.assertEqual(speakers("凛音，你们俩怎么看"), ("linyin", "aike"))
        for plural in (
            "你们",
            "你俩",
            "你们俩",
            "你们两个",
            "两位",
            "二位",
            "大家",
            "两个人",
            "两个机器人",
            "两位姑娘",
            "两位小姐",
            "两位助手",
        ):
            self.assertEqual(speakers(f"{plural}怎么看"), ("aike", "linyin"))
        self.assertEqual(speakers("今天有点累"), ("aike", "linyin"))
        self.assertEqual(speakers("爱可，爱可，你说一下"), ("aike",))

    async def test_director_timeout_uses_emergency_route_then_aike_notice(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        timeline = []

        async def members():
            return {"10001", "20001", "20002"}

        async def director(context, owner_message):
            timeline.append(("director", owner_message))
            return self.director.SceneDirectorResult(
                "timeout", self.director.safe_fallback_plan(), True
            )

        async def actor(request):
            timeline.append(("actor", request.speaker))
            return "凛音应急回复。"

        async def sender(speaker, reply):
            timeline.append(("send", speaker, reply))
            return True

        result = await hub.handle_message(
            group_id="30003",
            sender_id="10001",
            source_bot_id="20001",
            event_id="emergency-timeout",
            owner_message="我想听听凛音的看法",
            member_provider=members,
            director=director,
            actor=actor,
            sender=sender,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.director_status, "timeout")
        self.assertEqual(result.route, "emergency_keywords")
        self.assertEqual(result.fallback_reason, "timeout")
        self.assertEqual(result.emergency_notice, "sent")
        self.assertEqual(result.model_calls, 2)
        self.assertEqual(result.planned_speakers, ("linyin",))
        self.assertEqual(result.sent_speakers, ("linyin",))
        self.assertEqual(
            timeline,
            [
                ("director", "我想听听凛音的看法"),
                ("actor", "linyin"),
                ("send", "linyin", "凛音应急回复。"),
                (
                    "send",
                    "aike",
                    self.hub_module.EMERGENCY_NOTICE_TEXT,
                ),
            ],
        )
        self.assertEqual(
            [(event.speaker, event.text) for event in hub.public_events],
            [("owner", "我想听听凛音的看法"), ("linyin", "凛音应急回复。")],
        )

    async def test_circuit_skips_qwen_and_does_not_repeat_notice(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        director_calls = 0
        notice_calls = 0
        actor_requests = []

        async def members():
            return {"10001", "20001", "20002"}

        async def director(context, owner_message):
            nonlocal director_calls
            director_calls += 1
            return self.director.SceneDirectorResult(
                "unavailable", self.director.safe_fallback_plan(), True
            )

        async def actor(request):
            actor_requests.append(request)
            return f"{request.speaker}回复。"

        async def sender(speaker, reply):
            nonlocal notice_calls
            if reply == self.hub_module.EMERGENCY_NOTICE_TEXT:
                notice_calls += 1
            return True

        async def run(event_id, message):
            return await hub.handle_message(
                group_id="30003",
                sender_id="10001",
                source_bot_id="20001",
                event_id=event_id,
                owner_message=message,
                member_provider=members,
                director=director,
                actor=actor,
                sender=sender,
            )

        first = await run("circuit-1", "今天有点累")
        second = await run("circuit-2", "你们想吃什么")

        self.assertEqual(director_calls, 1)
        self.assertEqual(notice_calls, 1)
        self.assertEqual(first.director_status, "unavailable")
        self.assertEqual(first.fallback_reason, "unavailable")
        self.assertEqual(first.emergency_notice, "sent")
        self.assertEqual(first.model_calls, 3)
        self.assertEqual(second.director_status, "circuit_open")
        self.assertEqual(second.fallback_reason, "circuit_open")
        self.assertEqual(second.emergency_notice, "not_repeated")
        self.assertEqual(second.model_calls, 2)
        self.assertEqual(second.sent_speakers, ("aike", "linyin"))

        first_linyin = next(
            request
            for request in actor_requests
            if request.scene_turn_id == "scene-1" and request.speaker == "linyin"
        )
        second_linyin = next(
            request
            for request in actor_requests
            if request.scene_turn_id == "scene-2" and request.speaker == "linyin"
        )
        self.assertEqual(first_linyin.public_context[-1].speaker, "aike")
        self.assertEqual(first_linyin.public_context[-1].scene_turn_id, "scene-1")
        self.assertEqual(second_linyin.public_context[-1].speaker, "aike")
        self.assertEqual(second_linyin.public_context[-1].scene_turn_id, "scene-2")
        self.assertFalse(
            any(
                event.text == self.hub_module.EMERGENCY_NOTICE_TEXT
                for event in hub.public_events
            )
        )

    async def test_emergency_notice_failure_is_logged_without_retry_or_loop(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        sends = []

        async def members():
            return {"10001", "20001", "20002"}

        async def director(context, owner_message):
            raise RuntimeError("director transport unavailable")

        async def actor(request):
            return "凛音仍然回复。"

        async def sender(speaker, reply):
            sends.append((speaker, reply))
            return reply != self.hub_module.EMERGENCY_NOTICE_TEXT

        result = await hub.handle_message(
            group_id="30003",
            sender_id="10001",
            source_bot_id="20002",
            event_id="notice-failed",
            owner_message="我想问凛音一件事",
            member_provider=members,
            director=director,
            actor=actor,
            sender=sender,
        )

        self.assertEqual(result.director_status, "unavailable")
        self.assertEqual(result.emergency_notice, "send_failed")
        self.assertEqual(result.sent_speakers, ("linyin",))
        self.assertEqual(
            sends,
            [
                ("linyin", "凛音仍然回复。"),
                ("aike", self.hub_module.EMERGENCY_NOTICE_TEXT),
            ],
        )

    async def test_expired_circuit_reprobes_and_renotifies_on_failure(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        director_calls = 0
        notice_calls = 0

        async def members():
            return {"10001", "20001", "20002"}

        async def director(context, owner_message):
            nonlocal director_calls
            director_calls += 1
            return self.director.SceneDirectorResult(
                "timeout", self.director.safe_fallback_plan(), True
            )

        async def actor(request):
            return f"{request.speaker}回复。"

        async def sender(speaker, reply):
            nonlocal notice_calls
            if reply == self.hub_module.EMERGENCY_NOTICE_TEXT:
                notice_calls += 1
            return True

        async def run(event_id):
            return await hub.handle_message(
                group_id="30003",
                sender_id="10001",
                source_bot_id="20001",
                event_id=event_id,
                owner_message="普通群消息",
                member_provider=members,
                director=director,
                actor=actor,
                sender=sender,
            )

        first = await run("reprobe-1")
        hub._director_circuit_open_until = 0.0
        second = await run("reprobe-2")

        self.assertEqual(director_calls, 2)
        self.assertEqual(notice_calls, 2)
        self.assertEqual(first.emergency_notice, "sent")
        self.assertEqual(second.emergency_notice, "sent")
        self.assertEqual(second.director_status, "timeout")
        self.assertEqual(second.fallback_reason, "timeout")

    async def test_successful_reprobe_closes_circuit_without_recovery_notice(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        director_calls = 0
        notices = 0

        async def members():
            return {"10001", "20001", "20002"}

        async def director(context, owner_message):
            nonlocal director_calls
            director_calls += 1
            if director_calls == 1:
                return self.director.SceneDirectorResult(
                    "timeout", self.director.safe_fallback_plan(), True
                )
            return self.director.SceneDirectorResult(
                "ready", self.hub_module.build_single_speaker_plan("aike")
            )

        async def actor(request):
            return f"{request.speaker}回复。"

        async def sender(speaker, reply):
            nonlocal notices
            if reply == self.hub_module.EMERGENCY_NOTICE_TEXT:
                notices += 1
            return True

        async def run(event_id):
            return await hub.handle_message(
                group_id="30003",
                sender_id="10001",
                source_bot_id="20001",
                event_id=event_id,
                owner_message="普通群消息",
                member_provider=members,
                director=director,
                actor=actor,
                sender=sender,
            )

        await run("recover-1")
        hub._director_circuit_open_until = 0.0
        recovered = await run("recover-2")

        self.assertEqual(director_calls, 2)
        self.assertEqual(notices, 1)
        self.assertEqual(recovered.route, "director")
        self.assertEqual(recovered.director_status, "ready")
        self.assertEqual(recovered.fallback_reason, "none")
        self.assertEqual(recovered.emergency_notice, "not_needed")
        self.assertEqual(hub._director_circuit_open_until, 0.0)

    def test_scene_hub_rejects_invalid_circuit_window(self):
        self.assertEqual(
            self.hub_module.scene_hub_settings_status(
                self.make_settings(director_circuit_seconds=0)
            ),
            "invalid_config",
        )

    def test_actor_instruction_is_explicitly_temporary_and_private_safe(self):
        step = self.director.ScenePlanStep("linyin", "aike", "aike", True, True)
        request = self.hub_module.SceneActorRequest(
            "scene-1",
            "linyin",
            "回应爱可",
            (),
            self.hub_module.PublicSceneEvent("scene-1", "aike", "你好。"),
            step,
        )
        prompt = self.hub_module.build_scene_actor_system_context(request)

        self.assertIn("只适用于当前指定三人群", prompt)
        self.assertIn("不得改变私聊风格、角色卡或记忆", prompt)
        self.assertIn("通常回复 2 句", prompt)
        self.assertIn("最多 3 句、最多 160 个可见字符", prompt)
        self.assertIn("当前必须发言的角色：凛音（linyin）", prompt)
        self.assertIn("本条回复的目标受众：爱可（aike）", prompt)
        self.assertIn("不得自称或代替另一角色", prompt)
        self.assertIn("已经成功发送 prior_reply", prompt)
        self.assertIn("不得重新执行已经由先发角色完成的任务", prompt)
        self.assertIn('"send_status":"success"', prompt)

    def test_second_actor_gets_prior_reply_as_final_task_in_both_directions(self):
        cases = (
            ("aike", "linyin", "爱可已经介绍完自己。", "凛音（linyin）"),
            ("linyin", "aike", "凛音已经说完她的看法。", "爱可（aike）"),
        )
        for prior_speaker, speaker, prior_text, current_label in cases:
            with self.subTest(speaker=speaker):
                step = self.director.ScenePlanStep(
                    speaker, prior_speaker, prior_speaker, True, True
                )
                request = self.hub_module.SceneActorRequest(
                    "scene-1",
                    speaker,
                    "爱可，今天是凛音第一天来，你给她介绍一下你自己吧。",
                    (),
                    self.hub_module.PublicSceneEvent(
                        "scene-1", prior_speaker, prior_text
                    ),
                    step,
                )

                user_prompt = self.hub_module.build_scene_actor_user_prompt(request)
                system_prompt = self.hub_module.build_scene_actor_system_context(request)

                self.assertIn(prior_text, user_prompt)
                self.assertIn(f"给{current_label}的本地执行任务", user_prompt)
                self.assertIn("已经说完的话，不是你的台词", user_prompt)
                self.assertIn("不得复述她的原句", user_prompt)
                self.assertNotIn("今天是凛音第一天来", user_prompt)
                self.assertIn('"owner_message_background":', system_prompt)
                self.assertIn("今天是凛音第一天来", system_prompt)

    def test_proactive_command_matching_is_explicit_and_owner_friendly(self):
        matches = self.hub_module.is_proactive_chat_command
        self.assertTrue(matches("/继续聊"))
        self.assertTrue(matches("你们 聊会儿"))
        self.assertTrue(matches("你们接着聊"))
        self.assertTrue(matches("你们自己找个话题"))
        self.assertFalse(matches("你们今天想聊什么？"))
        self.assertFalse(matches("爱可继续聊刚才的事"))

    async def test_proactive_chat_runs_two_messages_once_and_rotates_opening_role(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        requests = []
        sends = []

        async def members():
            return {"10001", "20001", "20002"}

        async def actor(request):
            requests.append(request)
            return f"{request.speaker}主动消息。"

        async def sender(speaker, reply):
            sends.append((speaker, reply))
            return True

        async def run(event_id):
            return await hub.handle_proactive_chat(
                trigger="manual",
                group_id="30003",
                sender_id="10001",
                source_bot_id="20001",
                event_id=event_id,
                member_provider=members,
                actor=actor,
                sender=sender,
            )

        first = await run("manual-1")
        second = await run("manual-2")

        self.assertEqual(first.route, "proactive_manual")
        self.assertEqual(first.director_status, "skipped_proactive")
        self.assertEqual(first.model_calls, 2)
        self.assertEqual(first.sent_speakers, ("aike", "linyin"))
        self.assertEqual(second.sent_speakers, ("linyin", "aike"))
        self.assertEqual(len(sends), 4)
        self.assertTrue(all(request.turn_kind == "proactive" for request in requests))
        self.assertIsNone(requests[0].prior_reply)
        self.assertEqual(requests[1].prior_reply.text, "aike主动消息。")
        self.assertEqual(requests[3].prior_reply.text, "linyin主动消息。")
        self.assertEqual(
            [event.speaker for event in hub.public_events],
            ["aike", "linyin", "linyin", "aike"],
        )
        self.assertNotIn("owner", [event.speaker for event in hub.public_events])

    async def test_proactive_first_failure_stops_second_without_retry(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        actor_calls = []
        sends = []

        async def members():
            return {"10001", "20001", "20002"}

        async def actor(request):
            actor_calls.append(request.speaker)
            raise RuntimeError("first actor unavailable")

        async def sender(speaker, reply):
            sends.append((speaker, reply))
            return True

        result = await hub.handle_proactive_chat(
            trigger="idle",
            group_id="30003",
            sender_id="10001",
            source_bot_id="20001",
            event_id="idle-failure",
            member_provider=members,
            actor=actor,
            sender=sender,
        )

        self.assertEqual(result.model_calls, 1)
        self.assertEqual(actor_calls, ["aike"])
        self.assertEqual(sends, [])
        self.assertEqual(result.sent_speakers, ())
        self.assertEqual(
            [(item.speaker, item.status) for item in result.step_outcomes],
            [("aike", "actor_error"), ("linyin", "dependency_not_sent")],
        )

    async def test_idle_timer_is_single_shot_and_owner_message_cancels_it(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        idle_calls = []

        async def runner(event_id):
            idle_calls.append(event_id)

        armed = await hub.arm_idle_chat(runner, delay_seconds=0.01)
        await asyncio.sleep(0.04)
        await asyncio.sleep(0.02)
        self.assertTrue(armed)
        self.assertEqual(idle_calls, ["idle-1"])
        self.assertIsNone(hub._idle_task)

        await hub.arm_idle_chat(runner, delay_seconds=10)

        async def members():
            return {"10001", "20001", "20002"}

        async def director(context, owner_message):
            raise AssertionError("single address should skip director")

        async def actor(request):
            return "在的。"

        async def sender(speaker, reply):
            return True

        result = await hub.handle_message(
            group_id="30003",
            sender_id="10001",
            source_bot_id="20001",
            event_id="owner-cancels-idle",
            owner_message="爱可，你在吗",
            member_provider=members,
            director=director,
            actor=actor,
            sender=sender,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(idle_calls, ["idle-1"])
        self.assertIsNone(hub._idle_task)

    def test_scene_log_contains_only_finite_execution_state(self):
        outcome = self.hub_module.SceneStepOutcome
        result = self.hub_module.SceneTurnResult(
            status="completed",
            scene_turn_id="scene-7",
            director_status="ready",
            model_calls=3,
            sent_speakers=("aike", "linyin"),
            skipped_speakers=(),
            plan_mode="interaction",
            planned_speakers=("aike", "linyin"),
            step_outcomes=(outcome("aike", "sent"), outcome("linyin", "sent")),
        )

        line = self.hub_module.format_scene_turn_log(result)

        self.assertEqual(
            line,
            "turn=scene-7 status=completed director=ready route=none "
            "fallback_reason=none emergency_notice=not_needed mode=interaction "
            "model_calls=3 planned=aike,linyin "
            "outcomes=aike:sent,linyin:sent sent=aike,linyin skipped=- "
            "ms_member=0 ms_director=0 ms_first_actor=0 ms_first_send=0 ms_second_actor=0 ms_second_send=0 ms_first_reply=0 ms_total=0",
        )
        self.assertNotIn("owner_message", line)
        self.assertNotIn("public_context", line)
        self.assertNotIn("group_id", line)
        self.assertNotIn("bot_id", line)

    def test_nonebot_entry_reserves_group_and_bypasses_normal_persistence(self):
        source = (AI_CHAT_ROOT / "__init__.py").read_text(encoding="utf-8")
        handler = source.split("@shared_scene_hub.handle()", 1)[1].split(
            "@group_chat.handle()", 1
        )[0]

        self.assertIn("priority=15, block=True", source)
        self.assertIn('"get_group_member_list"', source)
        self.assertIn("_scene_group_members(", handler)
        self.assertIn('"send_group_msg"', handler)
        self.assertIn("await ask_llm(", handler)
        self.assertIn("build_scene_private_continuity_context(", handler)
        self.assertIn("private_continuity_context", handler)
        self.assertIn("log_scene_turn_result(", handler)
        self.assertIn("build_scene_actor_profile(request.speaker)", handler)
        self.assertIn("completion_route=actor_profile.completion_route", handler)
        self.assertIn("reasoning_effort=actor_profile.reasoning_effort", handler)
        self.assertIn("actor_profile.style_examples.content", handler)
        self.assertIn("build_scene_actor_user_prompt(request)", handler)
        self.assertIn('request.turn_kind != "proactive"', handler)
        self.assertIn("is_proactive_chat_command(text)", handler)
        self.assertIn("handle_proactive_chat(", handler)
        self.assertIn("arm_idle_chat(run_idle_chat, delay_seconds=60.0)", handler)
        self.assertIn('trigger="idle"', handler)
        self.assertIn('trigger="manual"', handler)
        self.assertNotIn("handle_chat(", handler)
        self.assertNotIn("save_message(", handler)
        self.assertNotIn("append_message(", handler)
        self.assertNotIn("compress_session(", handler)


    async def test_unambiguous_single_address_skips_director(self):
        hub = self.hub_module.SceneHub(self.make_settings())
        hub._director_circuit_open_until = float("inf")
        timeline = []

        async def members():
            return {"10001", "20001", "20002"}

        async def director(context, owner_message):
            timeline.append(("director", owner_message, tuple(context)))
            raise AssertionError("director must be skipped on unambiguous single address")

        async def actor(request):
            timeline.append(("actor", request.speaker))
            return "在的。"

        async def sender(speaker, reply):
            timeline.append(("send", speaker, reply))
            return True

        result = await hub.handle_message(
            group_id="30003",
            sender_id="10001",
            source_bot_id="20001",
            event_id="fast-1",
            owner_message="爱可，今天天气怎么样",
            member_provider=members,
            director=director,
            actor=actor,
            sender=sender,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.route, "single_fastpath")
        self.assertEqual(result.director_status, "skipped_fastpath")
        self.assertEqual(result.plan_mode, "single")
        self.assertEqual(result.model_calls, 1)
        self.assertEqual(result.fallback_reason, "none")
        self.assertEqual(result.emergency_notice, "not_needed")
        self.assertEqual(result.sent_speakers, ("aike",))
        self.assertEqual(timeline, [("actor", "aike"), ("send", "aike", "在的。")])
        self.assertGreaterEqual(result.timing.total_ms, 0)
        self.assertEqual(result.timing.director_ms, 0)
        self.assertGreaterEqual(result.timing.first_reply_ms, 0)

    async def test_director_receives_only_configured_recent_events(self):
        hub = self.hub_module.SceneHub(
            self.make_settings(max_context_events=20, director_context_events=6)
        )
        for index in range(8):
            hub._events.append(
                self.hub_module.PublicSceneEvent(
                    f"seed-{index}",
                    "owner" if index % 2 == 0 else "aike",
                    f"seed-{index}",
                )
            )
        seen = {}

        async def members():
            return {"10001", "20001", "20002"}

        async def director(context, owner_message):
            seen["context"] = list(context)
            return self.interaction_result()

        async def actor(request):
            return "你好。" if request.speaker == "aike" else "嗯。"

        async def sender(speaker, reply):
            return True

        result = await hub.handle_message(
            group_id="30003",
            sender_id="10001",
            source_bot_id="20001",
            event_id="window-1",
            owner_message="爱可给凛音打一个招呼",
            member_provider=members,
            director=director,
            actor=actor,
            sender=sender,
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.route, "director")
        self.assertEqual(len(seen["context"]), 6)
        self.assertEqual(seen["context"][0]["text"], "seed-2")
        self.assertEqual(seen["context"][-1]["text"], "seed-7")
        self.assertEqual(len(hub.public_events), 11)

    def test_unambiguous_single_speaker_helper_is_conservative(self):
        resolve = self.hub_module.resolve_unambiguous_single_speaker
        self.assertEqual(resolve("爱可，今天天气怎么样"), "aike")
        self.assertEqual(resolve("凛音：你在吗"), "linyin")
        self.assertEqual(resolve("爱可 你好"), "aike")
        self.assertIsNone(resolve("爱可给凛音打一个招呼"))
        self.assertIsNone(resolve("你觉得爱可怎么样"))
        self.assertIsNone(resolve("爱可今天天气怎么样"))

if __name__ == "__main__":
    unittest.main()
