from __future__ import annotations

import ast
import asyncio
from contextlib import AsyncExitStack, ExitStack, asynccontextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


def plugin_functions(names, namespace):
    tree = ast.parse((AI_CHAT_ROOT / '__init__.py').read_text(encoding='utf-8'))
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names]
    if len(nodes) != len(names):
        raise AssertionError('Requested entry functions are missing')
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), '<chat-time-runtime>', 'exec'), namespace)
    return namespace


class PrivateEvent:
    def __init__(self, now, *, text='今天是什么日子', owner=True, persona='aike'):
        self.time = now.timestamp()
        self.text = text
        self.user_id = 'owner' if owner else 'visitor'
        self.persona = persona


class GroupEvent:
    __init__ = PrivateEvent.__init__
    group_id = 'test-group'


class ChatTimeRuntimeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.local = load_module('src.plugins.ai_chat.local_time', AI_CHAT_ROOT / 'local_time.py')
        cls.reunion = load_module('src.plugins.ai_chat.reunion', AI_CHAT_ROOT / 'reunion.py')
        cls.interactions = load_module('src.plugins.ai_chat.chat_interactions', AI_CHAT_ROOT / 'chat_interactions.py')
        cls.contracts = load_module('src.plugins.ai_chat.chat_contracts', AI_CHAT_ROOT / 'chat_contracts.py')
        cls.llm = load_module('src.plugins.ai_chat.llm', AI_CHAT_ROOT / 'llm.py')

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.store = self.interactions.InteractionStore(Path(temp.name) / 'interactions.db')
        self.now = datetime.fromisoformat('2026-10-12T08:00:00+08:00')
        self.requests = []
        self.candidate_reply = '测试回复。'
        config = SimpleNamespace(
            bot_timezone='Asia/Shanghai', enable_chat_reunion=True, chat_reunion_min_gap_hours=3,
            enable_chat_sticker_intent_shadow=False, ai_temperature=0.7, enable_unknown_slang_tool=False,
            aike_llm_api_key='test', aike_llm_base_url='https://unit.invalid/v1', aike_llm_model='aike-model', aike_llm_timeout_seconds=5,
            enable_persona_llm_routing=True, persona_llm_role_card_keys=frozenset({'linyin'}),
            persona_llm_api_key='test', persona_llm_base_url='https://unit.invalid/v1', persona_llm_model='linyin-model',
            persona_llm_timeout_seconds=5, persona_llm_provider='openai', persona_llm_num_ctx=4096,
            persona_llm_max_tokens=640, persona_llm_keep_alive_seconds=0,
        )
        def scope(event):
            return SimpleNamespace(configuration_error='', bot_self_id='account-' + event.persona,
                                   persona_id=event.persona, routing_v2_active=event.persona == 'linyin')
        namespace = {
            'config': config, 'asyncio': asyncio, '_session_locks': {}, '_interaction_store': self.store,
            'AsyncExitStack': AsyncExitStack, 'asynccontextmanager': asynccontextmanager,
            'datetime': datetime, 'timezone': timezone,
            'InteractionKey': self.interactions.InteractionKey, 'PrivateMessageEvent': PrivateEvent,
            'is_owner': lambda cfg, event: event.user_id == 'owner', 'conversation_scope': scope,
            'build_local_time_snapshot': Mock(side_effect=lambda name: self.local.build_local_time_snapshot(name, clock=lambda: self.now)),
            'resolve_local_time_request': self.local.resolve_local_time_request,
            'history_with_trusted_local_time_context': self.local.history_with_trusted_local_time_context,
            'finalize_local_time_chat_reply': self.local.finalize_local_time_chat_reply,
            'reunion_allowed': self.reunion.reunion_allowed, 'parse_created_at': self.reunion.parse_created_at,
            'classify_reunion_gap': self.reunion.classify_reunion_gap, 'build_reunion_hint': self.reunion.build_reunion_hint,
            'correct_capped_reunion_duration': self.reunion.correct_capped_reunion_duration,
            'timezone_for_name': self.local.timezone_for_name,
            'clean_text': lambda event: event.text, 'llm_user_text': lambda event, text: text,
            'build_chat_weather_context': AsyncMock(return_value=''), 'ask_llm': self.llm.ask_llm,
            'combine_ephemeral_chat_system_contexts': lambda *parts: '\n'.join(filter(None, parts)),
            'current_message_identity_context': lambda event: 'speaker identity',
            'extract_sticker_intent': lambda reply: SimpleNamespace(visible_reply=reply, intent=None, status='none'),
            'evaluate_chat_sticker_intent_shadow': AsyncMock(), 'log_ai_event_error': Mock(), 'log_background_error': Mock(),
            'record_encyclopedia_observation_safely': Mock(),
            'write_encyclopedia_turn_log_safely': Mock(),
            'ChatRuntimeResult': self.contracts.ChatRuntimeResult, 'VISION_FAILURE_REPLY': 'vision failed',
            'chat_session_key': lambda event: ('group:' if isinstance(event, GroupEvent) else 'private:') + event.persona,
            'chat_bubble_split_allowed': lambda *args, **kwargs: True,
            'normalize_bubble_limits': lambda cfg: (0, 0, 3),
            'resolve_chat_bubbles': lambda text, **kwargs: text.split('\n\n'),
            'current_chat_bubble_generation': lambda key: 1, 'next_bubble_delays': lambda bubbles, **kwargs: [0] * len(bubbles),
            'wait_for_bubble_delay': AsyncMock(return_value=False),
            'record_chat_message_delivery': Mock(),
        }
        self.ns = plugin_functions({
            'session_lock', 'owner_interaction_key', 'owner_interaction_lock_key', 'chat_turn_lock',
            'chat_turn_scope',
            'record_owner_interaction_success', 'reunion_context_for_chat', 'generate_chat_text_response',
            'send_chat_reply_bubbles', 'send_tts_record',
        }, namespace)
        case = self
        class FakeClient:
            def __init__(self, **kwargs):
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
            async def create(self, **kwargs):
                case.requests.append(deepcopy(kwargs['messages']))
                return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=case.candidate_reply, tool_calls=[]))])
        async def fake_ollama(route, messages, **kwargs):
            self.requests.append(deepcopy(messages))
            return self.candidate_reply
        stack = ExitStack()
        self.addCleanup(stack.close)
        for name in ['load_system_prompt', 'load_base_chat_prompt', 'load_persona_prompt', 'load_world_card_prompt']:
            stack.enter_context(patch.object(self.llm, name, return_value='test-' + name))
        stack.enter_context(patch.object(self.llm, 'AsyncOpenAI', FakeClient))
        stack.enter_context(patch.object(self.llm, '_ask_ollama', side_effect=fake_ollama))
        # Entry generation must hand off its snapshot, never reread at the model boundary.
        stack.enter_context(patch.object(self.llm, 'build_local_time_snapshot', side_effect=AssertionError('second clock read')))

    def key(self, persona='aike'):
        return self.interactions.InteractionKey('account-' + persona, persona, 'owner')

    async def generate(self, event=None, history=None, *, vision_failed=False):
        event = event or PrivateEvent(self.now)
        return await self.ns['generate_chat_text_response'](
            event, SimpleNamespace(finish=AsyncMock()), SimpleNamespace(history=history or []),
            SimpleNamespace(for_llm=event.text, vision_failed=vision_failed), role_card_key=event.persona,
        )

    async def test_every_round_and_both_personas_receive_time_on_cloud_and_local(self):
        for persona, provider, text in [('aike', 'openai', '你好'), ('linyin', 'openai', '今天是什么日子'), ('linyin', 'ollama', '看这张图片')]:
            with self.subTest(persona=persona, provider=provider):
                self.ns['config'].persona_llm_provider = provider
                result = await self.generate(PrivateEvent(self.now, persona=persona, text=text))
                messages = self.requests[-1]
                time_contexts = [item['content'] for item in messages if '[本轮北京时间]' in item['content']]
                self.assertEqual(len(time_contexts), 1)
                self.assertIn('2026-10-12T08:00:00+08:00', time_contexts[0])
                self.assertEqual(messages[-1], {'role': 'user', 'content': text})
                self.assertTrue(result.time_observation['chat_time_context_injected'])
        self.assertEqual(self.ns['build_local_time_snapshot'].call_count, 3)

    async def test_encyclopedia_observation_is_forwarded_and_recorded_once_by_persona(self):
        async def reply_with_evidence(*args, **kwargs):
            kwargs['tool_observation'].update(encyclopedia_status='found', encyclopedia_trigger='direct_question')
            return '根据公共资料回答。'
        self.ns['ask_llm'] = AsyncMock(side_effect=reply_with_evidence)
        result = await self.generate(PrivateEvent(self.now, persona='linyin', text='凛音知道牛来吗？'))
        self.assertEqual(result.tool_observation['encyclopedia_status'], 'found')
        self.ns['record_encyclopedia_observation_safely'].assert_called_once_with(result.tool_observation, 'linyin')
        self.ns['write_encyclopedia_turn_log_safely'].assert_called_once_with(result.tool_observation, 'linyin', reply='根据公共资料回答。', error=None)

    async def test_encyclopedia_failure_is_recorded_even_if_final_chat_model_fails(self):
        async def failing_reply(*args, **kwargs):
            kwargs['tool_observation'].update(encyclopedia_status='planner_invalid_response')
            raise RuntimeError('model unavailable')
        self.ns['ask_llm'] = AsyncMock(side_effect=failing_reply)
        result = await self.generate(PrivateEvent(self.now, text='你听过这个专名吗？'))
        self.assertIsNone(result)
        self.ns['record_encyclopedia_observation_safely'].assert_called_once_with({'encyclopedia_status': 'planner_invalid_response'}, 'aike')
        self.assertIsInstance(self.ns['write_encyclopedia_turn_log_safely'].call_args.kwargs['error'], RuntimeError)

    async def test_explicit_question_and_validation_use_one_midnight_snapshot(self):
        self.now = datetime.fromisoformat('2026-10-12T00:00:00+08:00')
        self.candidate_reply = '今天是星期日。'
        result = await self.generate(PrivateEvent(self.now, text='今天星期几'))
        self.assertEqual(result.reply, '今天是星期一。')
        self.assertEqual(self.ns['build_local_time_snapshot'].call_count, 1)
        self.assertIn('2026-10-12T00:00:00+08:00', self.requests[-1][-2]['content'])
        self.assertTrue(any('当前日期：2026-10-12' in message['content'] for message in self.requests[-1]))

    async def test_history_does_not_accumulate_time_or_reunion_prompts(self):
        history = [{'role': 'assistant', 'content': '过去的日期是2025年。'}]
        original = deepcopy(history)
        await self.generate(history=history)
        self.now += timedelta(days=1)
        await self.generate(history=history)
        self.assertEqual(history, original)
        for messages in self.requests:
            self.assertEqual(sum('[本轮北京时间]' in message['content'] for message in messages), 1)
        self.assertIn('2026-10-13', self.requests[-1][-2]['content'])

    async def test_month_gap_caps_emotion_only_and_does_not_record_before_delivery(self):
        self.store.record_success(self.key(), source='private', succeeded_at=self.now - timedelta(days=30))
        before = self.store.latest(self.key())
        result = await self.generate()
        self.assertEqual(result.time_observation['reunion_bucket'], self.reunion.BUCKET_TWO_WEEKS)
        self.assertEqual(result.time_observation['reunion_elapsed_seconds'], 30 * 86400)
        self.assertEqual(self.store.latest(self.key()), before)
        hints = [message['content'] for message in self.requests[-1] if '[本轮重逢状态]' in message['content']]
        self.assertEqual(len(hints), 1)
        self.assertIn('实际聊天间隔：约 30 天', hints[0])

    async def test_recent_group_reply_suppresses_private_reunion_for_same_persona_only(self):
        self.store.record_success(self.key(), source='group', succeeded_at=self.now - timedelta(hours=1))
        self.store.record_success(self.key('linyin'), source='private', succeeded_at=self.now - timedelta(days=14))
        result = await self.generate()
        self.assertEqual(result.time_observation['reunion_status'], 'below_threshold')
        self.assertFalse(any('[本轮重逢状态]' in message['content'] for message in self.requests[-1]))
        result = await self.generate(PrivateEvent(self.now, persona='linyin'))
        self.assertEqual(result.time_observation['reunion_status'], 'injected')

    async def test_month_return_cannot_be_spoken_as_capped_two_week_absence(self):
        self.store.record_success(self.key(), source='private', succeeded_at=self.now - timedelta(days=30))
        self.candidate_reply = '狗修金有两周没来找爱可聊天了……爱可特别想您。'
        result = await self.generate()
        self.assertEqual(result.reply, '狗修金有30天没来找爱可聊天了……爱可特别想您。')
        self.assertTrue(result.time_observation['reunion_duration_corrected'])

    async def test_group_and_non_owner_do_not_receive_private_reunion_metadata(self):
        old = self.now - timedelta(days=30)
        self.store.record_success(self.key(), source='private', succeeded_at=old)
        for event in [GroupEvent(self.now), PrivateEvent(self.now, owner=False)]:
            result = await self.generate(event)
            self.assertEqual(result.time_observation['reunion_status'], 'disabled_or_out_of_scope')
            self.assertFalse(any('[本轮重逢状态]' in message['content'] for message in self.requests[-1]))
            self.assertFalse(any(old.isoformat() in message['content'] for message in self.requests[-1]))

    async def test_failed_and_partial_bubble_delivery(self):
        event = PrivateEvent(self.now)
        failed = SimpleNamespace(send=AsyncMock(side_effect=RuntimeError('send failed')))
        with self.assertRaises(RuntimeError):
            await self.ns['send_chat_reply_bubbles'](failed, event, 'first')
        self.assertIsNone(self.store.latest(self.key()))
        self.ns['record_chat_message_delivery'].assert_not_called()
        partial = SimpleNamespace(send=AsyncMock(side_effect=[None, RuntimeError('second failed')]))
        with self.assertRaises(RuntimeError):
            await self.ns['send_chat_reply_bubbles'](partial, event, 'first\n\nsecond')
        self.assertIsNotNone(self.store.latest(self.key()))
        self.ns['record_chat_message_delivery'].assert_called_once_with(event, 'first\n\nsecond')

    async def test_non_owner_and_failure_reply_do_not_refresh_owner_clock(self):
        matcher = SimpleNamespace(send=AsyncMock())
        await self.ns['send_chat_reply_bubbles'](matcher, PrivateEvent(self.now, owner=False), 'reply')
        await self.ns['send_chat_reply_bubbles'](matcher, PrivateEvent(self.now), 'failure', counts_as_chat=False)
        self.assertIsNone(self.store.latest(self.key()))
        result = await self.generate(vision_failed=True)
        self.assertFalse(result.interaction_success_eligible)
        self.candidate_reply = ''
        result = await self.generate()
        self.assertFalse(result.interaction_success_eligible)

    async def test_queued_message_after_delivery_does_not_retrigger(self):
        self.store.record_success(self.key(), source='private', succeeded_at=self.now - timedelta(days=14))
        first = await self.generate()
        self.assertEqual(first.time_observation['reunion_status'], 'injected')
        self.store.record_success(self.key(), source='private', succeeded_at=self.now + timedelta(seconds=5))
        self.now += timedelta(seconds=10)
        queued = PrivateEvent(self.now - timedelta(seconds=8))
        second = await self.generate(queued)
        self.assertEqual(second.time_observation['reunion_status'], 'queued_or_future_timestamp')
        self.assertFalse(any('[本轮重逢状态]' in message['content'] for message in self.requests[-1]))

    async def test_missing_or_unreadable_store_preserves_chat(self):
        result = await self.generate()
        self.assertEqual(result.time_observation['reunion_status'], 'no_success_baseline')
        with patch.object(self.store, 'latest', side_effect=RuntimeError('storage failed')):
            result = await self.generate()
        self.assertEqual(result.reply, self.candidate_reply)
        self.assertEqual(result.time_observation['reunion_status'], 'storage_error')

    async def test_owner_group_and_private_share_lock_and_personas_do_not(self):
        lock = self.ns['chat_turn_lock'](PrivateEvent(self.now), 'private')
        self.assertIs(lock, self.ns['chat_turn_lock'](GroupEvent(self.now), 'group'))
        self.assertIsNot(lock, self.ns['chat_turn_lock'](PrivateEvent(self.now, persona='linyin'), 'private-linyin'))
        order = []
        async def turn(label):
            async with lock:
                order.append(label + '-start')
                await asyncio.sleep(0)
                order.append(label + '-end')
        await asyncio.gather(turn('private'), turn('group'))
        self.assertEqual(order, ['private-start', 'private-end', 'group-start', 'group-end'])

    async def test_turn_scope_preserves_history_lock_without_non_owner_deadlock(self):
        event = PrivateEvent(self.now)
        history_lock = self.ns['session_lock']('private')
        async with self.ns['chat_turn_scope'](event, 'private'):
            self.assertTrue(history_lock.locked())
            self.assertTrue(self.ns['chat_turn_lock'](event, 'private').locked())
        self.assertFalse(history_lock.locked())
        async def visitor_turn():
            async with self.ns['chat_turn_scope'](PrivateEvent(self.now, owner=False), 'visitor'):
                self.assertTrue(self.ns['session_lock']('visitor').locked())
        await asyncio.wait_for(visitor_turn(), timeout=1)

    async def test_model_boundary_supplies_time_for_scene_calls_without_snapshot(self):
        snapshot = self.local.build_local_time_snapshot(clock=lambda: self.now)
        with patch.object(self.llm, 'build_local_time_snapshot', return_value=snapshot) as clock:
            await self.llm.ask_llm(self.ns['config'], [], 'scene turn', role_card_key='linyin', completion_route='legacy')
        clock.assert_called_once_with('Asia/Shanghai')
        self.assertIn('[本轮北京时间]', self.requests[-1][-2]['content'])

    async def test_voice_only_semantic_reply_counts_after_success(self):
        event = PrivateEvent(self.now)
        self.ns.update({
            'tts_enabled_for_event': lambda event: True,
            'adapt_speech_text': lambda text, **kwargs: SimpleNamespace(text=text, language='zh'),
            'tts_text_limit': lambda language: 1000,
            'tts_route_for_event': lambda event: ('test-voice', 'normal'),
            'tts_trailing_noise_cleanup_for_event': lambda event: False,
            'request_tts': AsyncMock(return_value=SimpleNamespace(audio_path=Path('test.wav'))),
            'MessageSegment': SimpleNamespace(record=lambda path: path),
        })
        event.user_id = '12345'
        self.ns['is_owner'] = lambda cfg, event: True
        bot = SimpleNamespace(call_api=AsyncMock())
        await self.ns['send_tts_record'](bot, event, 'read aloud')
        key = self.interactions.InteractionKey('account-aike', 'aike', '12345')
        self.assertIsNone(self.store.latest(key))
        bot.call_api.side_effect = RuntimeError('send failed')
        with self.assertRaises(RuntimeError):
            await self.ns['send_tts_record'](bot, event, 'semantic reply', counts_as_chat=True)
        self.assertIsNone(self.store.latest(key))
        bot.call_api.side_effect = None
        await self.ns['send_tts_record'](bot, event, 'semantic reply', counts_as_chat=True)
        self.assertIsNotNone(self.store.latest(key))


if __name__ == '__main__':
    unittest.main()
