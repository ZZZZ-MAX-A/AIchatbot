from __future__ import annotations

import ast
import asyncio
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from pure_ai_chat_loader import (
    AI_CHAT_ROOT, ensure_ai_chat_packages, load_module,
    load_sticker_classifier_module, load_sticker_selection_module, load_sticker_library_module,
)


class PrivateEvent:
    def __init__(self, account='20001', *, persona='aike', owner=True):
        self.self_id, self.user_id, self.persona, self.owner = account, 10001, persona, owner


class GroupEvent:
    __init__ = PrivateEvent.__init__


class StickerChatRuntimeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.classifier = load_sticker_classifier_module()
        cls.selection = load_sticker_selection_module()
        cls.sticker_library = load_sticker_library_module()
        cls.reliability = load_module('src.plugins.ai_chat.reliability_events', AI_CHAT_ROOT / 'reliability_events.py')
        cls.attachment = load_module('src.plugins.ai_chat.sticker_attachment', AI_CHAT_ROOT / 'sticker_attachment.py')
        cls.tree = ast.parse((AI_CHAT_ROOT / '__init__.py').read_text(encoding='utf-8'))

    def setUp(self):
        self.clock = 1000.0
        self.generations = {}
        self.bot = SimpleNamespace(call_api=AsyncMock())
        self.runtime = self.selection.StickerSelectionRuntime()
        self.library = SimpleNamespace(issues=(), assets=(SimpleNamespace(
            enabled=True, persona_key='aike', scope='owner_private', sticker_id='synthetic_asset',
            moods=('playful',), intensity='medium', usage_tags=('acting_cute',),
        ),))
        self.classify = AsyncMock(return_value=self.classifier.StickerClassifierResult(
            'requested', self.classifier.StickerIntent('playful', 'medium', 'acting_cute', .93),
            response_chars=110, finish_reason='stop',
            diagnostics=self.classifier.StickerClassifierDiagnostics(
                request_started=True, max_tokens=500, timeout_ms=8000, elapsed_ms=123,
                prompt_tokens=200, completion_tokens=90, total_tokens=290,
                reasoning_tokens=50, reasoning_chars=100,
            ),
        ))
        config = SimpleNamespace(
            enable_remote_sticker_classifier=True, enable_local_stickers=True,
            enable_chat_sticker_attachments=True, chat_sticker_owner_private_only=True,
            chat_sticker_cooldown_seconds=120, chat_sticker_min_messages_between=4,
            chat_sticker_max_per_hour=6, chat_sticker_max_per_reply=1,
            chat_sticker_min_intent_confidence=.82, sticker_classifier_api_key='unit-only',
            sticker_classifier_base_url='https://unit.invalid', sticker_classifier_model='unit-model',
            sticker_classifier_timeout_seconds=8, sticker_classifier_max_input_chars=2400,
            local_sticker_root=Path('synthetic-library'),
        )
        def resolved(event):
            return (SimpleNamespace(bot_self_id=event.self_id, configuration_error='', routing_v2_active=True),
                    self.selection.StickerSelectionScope(f'private:{event.user_id}', event.persona))
        async def fake_attachment(root, sticker_id, user_id, *, limits, sender, can_send):
            await asyncio.sleep(0)
            if not can_send():
                return self.attachment.StickerAttachmentResult('expired', False)
            await sender(user_id, Path('synthetic.gif'))
            return self.attachment.StickerAttachmentResult('sent', True, sticker_id)
        self.ns = {
            '__name__': __name__, '__package__': 'src.plugins.ai_chat', 'asyncio': asyncio,
            'dataclass': dataclass, 'replace': replace, 'Path': Path, 'config': config,
            'PrivateMessageEvent': PrivateEvent, 'is_owner': lambda cfg, event: event.owner,
            'ALLOWED_PERSONA_KEYS': self.sticker_library.ALLOWED_PERSONA_KEYS, 'resolve_chat_sticker_scope': resolved,
            'chat_session_key': self.key, 'current_chat_bubble_generation': lambda key: self.generations.get(key, 0),
            'current_selection_time': lambda: self.clock, 'sticker_limits_from_config': lambda: None,
            'chat_sticker_message_progress': lambda *args: 10,
            'StickerSelectionContext': self.selection.StickerSelectionContext,
            'StickerSelectionPolicy': self.selection.StickerSelectionPolicy,
            'available_sticker_combinations': self.selection.available_sticker_combinations,
            'RemoteStickerClassifierSettings': self.classifier.RemoteStickerClassifierSettings,
            'StickerClassifierDiagnostics': self.classifier.StickerClassifierDiagnostics,
            'load_approved_sticker_library': Mock(side_effect=lambda *a, **kw: self.library),
            'classify_sticker_intent': self.classify, 'send_selected_sticker_attachment': fake_attachment,
            'MessageSegment': SimpleNamespace(image=lambda path: 'synthetic image'),
            'record_success_safely': Mock(), 'record_result_safely': Mock(), 'record_failure_safely': Mock(),
            'ReliabilityOutcome': self.reliability.ReliabilityOutcome,
            '_chat_sticker_selection_runtime': self.runtime, '_chat_sticker_attachments_suspended': {},
            '_remote_sticker_classifier_snapshots': {}, '_remote_sticker_classifier_tasks': {},
            '_chat_sticker_attachment_locks': {}, '_remote_sticker_classifier_sample_id': 0,
            'VISION_FAILURE_REPLY': 'vision failed', 'update_chat_commit': Mock(),
            'send_chat_reply_bubbles': AsyncMock(return_value=1),
            'build_chat_turn': lambda user, assistant: SimpleNamespace(stored_user=user, stored_assistant=assistant),
            'persist_scoped_chat_turn': AsyncMock(), 'schedule_scoped_chat_compression': AsyncMock(),
            'should_count_private_trial': lambda event: False,
        }
        names = {
            'RemoteStickerClassifierShadowSnapshot', 'RemoteStickerClassifierEvaluation',
            'remote_sticker_classifier_settings', '_remote_classifier_snapshot_for_absent_intent',
            '_record_remote_sticker_classifier_reliability', '_evaluate_remote_sticker_classifier_result',
            '_maybe_send_remote_sticker_attachment', '_record_sticker_attachment_reliability',
            '_chat_sticker_attachments_suspended_for', 'remote_sticker_scope_key',
            'schedule_remote_sticker_classifier_shadow', 'schedule_chat_reply_sticker',
            'chat_sticker_selection_context',
            'render_chat_result', 'finalize_chat_result',
        }
        nodes = [n for n in self.tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
        self.assertEqual(len(nodes), len(names))
        module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), '<sticker-runtime>', 'exec'), self.ns)

    @staticmethod
    def key(event):
        return f'{event.self_id}:{event.user_id}'

    def schedule(self, event=None, text='synthetic current turn'):
        event = event or PrivateEvent()
        self.ns['schedule_remote_sticker_classifier_shadow'](self.bot, event, text, 'synthetic reply')
        return event

    async def drain(self):
        tasks = list(self.ns['_remote_sticker_classifier_tasks'].values())
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=3)

    def latest(self, event):
        key = self.ns['remote_sticker_scope_key'](self.ns['resolve_chat_sticker_scope'](event))
        return self.ns['_remote_sticker_classifier_snapshots'][key]

    def state_key(self, event):
        return self.ns['remote_sticker_scope_key'](self.ns['resolve_chat_sticker_scope'](event))

    async def test_success_uses_available_combinations_sends_once_and_records_delivery(self):
        event = self.schedule()
        await self.drain()
        self.bot.call_api.assert_awaited_once()
        self.assertEqual(self.latest(event).attachment_status, 'sent')
        self.assertEqual(self.latest(event).finish_reason, 'stop')
        self.assertEqual(self.latest(event).diagnostics, self.classify.return_value.diagnostics)
        self.assertEqual(self.classify.call_args.kwargs['available_combinations'], (('playful', 'medium', 'acting_cute'),))
        self.ns['record_success_safely'].assert_any_call('sticker_attachment', 'send_image')
        self.assertEqual(self.ns['_remote_sticker_classifier_tasks'], {})

    async def test_truncated_request_keeps_usage_in_status_without_sending(self):
        self.classify.return_value = replace(self.classify.return_value, status='response_truncated',
                                            intent=None, response_chars=0, finish_reason='length')
        event = self.schedule()
        await self.drain()
        snapshot = self.latest(event)
        self.assertEqual(snapshot.classifier_status, 'response_truncated')
        self.assertEqual(snapshot.diagnostics, self.classify.return_value.diagnostics)
        self.assertEqual(snapshot.diagnostics.max_tokens, 500)
        self.bot.call_api.assert_not_awaited()

    async def test_owner_status_command_renders_truncated_request_usage(self):
        diagnostics = self.classifier.StickerClassifierDiagnostics(
            request_started=True, max_tokens=500, timeout_ms=8000, elapsed_ms=1500,
            prompt_tokens=300, completion_tokens=500, total_tokens=800,
            reasoning_tokens=500, reasoning_chars=1700,
        )
        self.classify.return_value = replace(self.classify.return_value, status='response_truncated',
            intent=None, response_chars=0, finish_reason='length', diagnostics=diagnostics)
        event = self.schedule()
        await self.drain()
        handler = next(node for node in self.tree.body if isinstance(node, ast.AsyncFunctionDef)
            and any(isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
                    and isinstance(dec.func.value, ast.Name)
                    and dec.func.value.id == 'sticker_intent_status_cmd' for dec in node.decorator_list))
        handler = deepcopy(handler)
        handler.name, handler.decorator_list = '_status_command_under_test', []
        self.ns.update(require_owner=AsyncMock(),
            format_sticker_classifier_diagnostics=self.classifier.format_sticker_classifier_diagnostics,
            format_remote_sticker_attachment_status=self.classifier.format_remote_sticker_attachment_status)
        module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), handler], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), '<sticker-status>', 'exec'), self.ns)
        class Finished(Exception):
            pass
        matcher = SimpleNamespace(finish=AsyncMock(side_effect=Finished))
        with self.assertRaises(Finished):
            await self.ns['_status_command_under_test'](event, matcher)
        text = matcher.finish.call_args.args[0]
        self.assertIn('length / 0 字符', text)
        self.assertIn('max_tokens=500', text)
        self.assertIn('输入 300 / 输出 500 / 总计 800', text)
        self.assertIn('思考 token：500；思考内容：1700 字符', text)
        self.assertIn('分类耗时：1500 毫秒', text)
        self.assertIn('自动附带：未触发', text)
        self.assertNotIn('unit-only', text)

    async def test_unsupported_persona_group_and_visitor_do_not_classify(self):
        for event in [PrivateEvent(persona='unknown'), PrivateEvent(persona='shared'), GroupEvent(), PrivateEvent(owner=False)]:
            self.schedule(event)
        await self.drain()
        self.classify.assert_not_called()
        self.bot.call_api.assert_not_called()

    async def test_shared_asset_sends_for_both_personas_without_shared_cooldown(self):
        self.library.assets[0].persona_key = 'shared'
        aike = self.schedule(PrivateEvent('20001', persona='aike'))
        await self.drain()
        linyin = self.schedule(PrivateEvent('30001', persona='linyin'))
        await self.drain()
        self.assertEqual(self.bot.call_api.await_count, 2)
        self.assertEqual(self.latest(aike).attachment_status, 'sent')
        self.assertEqual(self.latest(linyin).attachment_status, 'sent')
        self.assertEqual(len(self.runtime._last_sent_at), 2)

    async def test_linyin_does_not_borrow_aike_exclusive_asset(self):
        event = self.schedule(PrivateEvent('30001', persona='linyin'))
        await self.drain()
        self.assertEqual(self.classify.call_args.kwargs['available_combinations'], ())
        self.assertEqual(self.latest(event).decision_reason, 'no_match')
        self.bot.call_api.assert_not_called()

    async def test_empty_text_and_frequency_gate_skip_model(self):
        self.schedule(text=' ')
        self.classify.assert_not_called()
        self.schedule()
        await self.drain()
        self.classify.reset_mock()
        event = self.schedule()
        await self.drain()
        self.classify.assert_not_called()
        self.assertEqual(self.latest(event).decision_reason, 'cooldown')

    async def test_invalid_library_skips_model_and_records_asset_failure(self):
        self.library.issues = ('invalid',)
        event = self.schedule()
        await self.drain()
        self.classify.assert_not_called()
        self.assertEqual(self.latest(event).decision_reason, 'library_unavailable')
        self.assertIn('sticker_library_unavailable', [c.kwargs['code'] for c in self.ns['record_result_safely'].call_args_list])

    async def test_new_turn_cancels_old_classification_and_only_latest_sends(self):
        started = asyncio.Event()
        first = True
        async def classify(*args, **kwargs):
            nonlocal first
            if first:
                first = False
                started.set()
                await asyncio.Event().wait()
            return self.classify.return_value
        self.ns['classify_sticker_intent'] = classify
        event = self.schedule(text='old')
        await asyncio.wait_for(started.wait(), timeout=2)
        previous = list(self.ns['_remote_sticker_classifier_tasks'].values())[0]
        self.generations[self.key(event)] = 1
        self.schedule(event, text='new')
        await self.drain()
        await previous
        self.bot.call_api.assert_awaited_once()
        self.assertEqual(self.latest(event).sample_id, 2)

    async def test_accounts_do_not_block_each_others_classification(self):
        slow_started, release = asyncio.Event(), asyncio.Event()
        self.addCleanup(release.set)
        async def classify(settings, user_text, *args, **kwargs):
            if user_text == 'slow':
                slow_started.set()
                await release.wait()
            return self.classify.return_value
        self.ns['classify_sticker_intent'] = classify
        a, b = PrivateEvent('20001'), PrivateEvent('20002')
        self.schedule(a, 'slow')
        await asyncio.wait_for(slow_started.wait(), timeout=2)
        self.schedule(b, 'fast')
        fast = list(self.ns['_remote_sticker_classifier_tasks'].values())[-1]
        await asyncio.wait_for(fast, timeout=2)
        self.assertEqual(self.latest(b).attachment_status, 'sent')
        release.set()
        await self.drain()
        self.assertEqual(self.bot.call_api.await_count, 2)
        self.assertEqual(self.latest(a).attachment_status, 'sent')

    async def test_new_generation_without_new_reply_discards_old_result(self):
        started, release = asyncio.Event(), asyncio.Event()
        self.addCleanup(release.set)
        async def classify(*args, **kwargs):
            started.set()
            await release.wait()
            return self.classify.return_value
        self.ns['classify_sticker_intent'] = classify
        event = self.schedule()
        await asyncio.wait_for(started.wait(), timeout=2)
        self.generations[self.key(event)] = 1
        release.set()
        await self.drain()
        self.bot.call_api.assert_not_called()
        self.assertEqual(self.latest(event).attachment_status, 'expired')

    async def test_superseded_inflight_send_finishes_frequency_commit_before_next_selection(self):
        started, release = asyncio.Event(), asyncio.Event()
        self.addCleanup(release.set)
        async def send(*args, **kwargs):
            started.set()
            await release.wait()
        self.bot.call_api.side_effect = send
        event = self.schedule()
        await asyncio.wait_for(started.wait(), timeout=2)
        previous = list(self.ns['_remote_sticker_classifier_tasks'].values())[0]
        self.generations[self.key(event)] = 1
        self.schedule(event, text='new turn during send')
        release.set()
        await self.drain()
        await previous
        self.bot.call_api.assert_awaited_once()
        self.assertEqual(self.latest(event).decision_reason, 'cooldown')
        self.ns['record_success_safely'].assert_any_call('sticker_attachment', 'send_image')

    async def test_send_failure_does_not_consume_frequency_and_is_recorded(self):
        self.bot.call_api.side_effect = RuntimeError('synthetic adapter failure')
        # The production attachment contract catches adapter exceptions.
        async def failing(*args, **kwargs):
            return self.attachment.StickerAttachmentResult('send_failed', False)
        self.ns['send_selected_sticker_attachment'] = failing
        event = self.schedule()
        await self.drain()
        self.assertEqual(self.latest(event).attachment_status, 'send_failed')
        self.assertEqual(self.runtime._last_sent_at, {})
        self.assertIn('sticker_send_failed', [c.kwargs['code'] for c in self.ns['record_result_safely'].call_args_list])

    async def test_commit_failure_counts_delivery_and_suspends_only_that_session_temporarily(self):
        original = self.runtime.commit_sent
        self.runtime.commit_sent = Mock(side_effect=ValueError('shuffle changed'))
        a, b = PrivateEvent('20001'), PrivateEvent('20002')
        self.schedule(a)
        await self.drain()
        self.assertEqual(self.latest(a).attachment_status, 'sent_commit_failed')
        self.assertIn(self.state_key(a), self.runtime._last_sent_at)
        self.runtime.commit_sent = original
        self.schedule(b)
        await self.drain()
        self.assertEqual(self.latest(b).attachment_status, 'sent')
        self.clock += 121
        self.assertFalse(self.ns['_chat_sticker_attachments_suspended_for'](self.state_key(a)))
        self.assertEqual(self.ns['_chat_sticker_attachments_suspended'], {})

    async def test_unknown_send_acknowledgement_consumes_frequency_conservatively(self):
        async def timeout(*args, **kwargs):
            return self.attachment.StickerAttachmentResult('send_timeout', False)
        self.ns['send_selected_sticker_attachment'] = timeout
        event = self.schedule()
        await self.drain()
        self.assertEqual(self.latest(event).attachment_status, 'send_timeout')
        self.assertIn(self.state_key(event), self.runtime._last_sent_at)
        self.schedule(event)
        self.assertEqual(self.latest(event).attachment_status, 'suspended')
        self.assertEqual(self.classify.await_count, 1)

    async def test_vision_failure_and_semantic_voice_do_not_schedule(self):
        scheduler = Mock()
        self.ns['schedule_remote_sticker_classifier_shadow'] = scheduler
        matcher, event = SimpleNamespace(finish=AsyncMock()), PrivateEvent()
        for reply, voice in [('vision failed', False), ('synthetic', True)]:
            await self.ns['render_chat_result'](self.bot, event, matcher,
                SimpleNamespace(reply=reply, interaction_success_eligible=True),
                SimpleNamespace(semantic_voice=voice), classifier_user_text='synthetic')
        scheduler.assert_not_called()

    async def test_shared_post_send_gate_for_render_and_finalize_including_v2(self):
        for function in ['render_chat_result', 'finalize_chat_result']:
            for delivered, eligible, changed, expected in [(1, True, False, 1), (0, True, False, 0), (1, False, False, 0), (1, True, True, 0)]:
                with self.subTest(function=function, delivered=delivered, eligible=eligible, changed=changed):
                    event = PrivateEvent()
                    self.generations[self.key(event)] = 0
                    scheduler = Mock()
                    self.ns['schedule_remote_sticker_classifier_shadow'] = scheduler
                    async def bubbles(*args, **kwargs):
                        if changed:
                            self.generations[self.key(event)] = 1
                        return delivered
                    self.ns['send_chat_reply_bubbles'] = bubbles
                    result = SimpleNamespace(reply='synthetic reply', stored_assistant='synthetic', interaction_success_eligible=eligible, assistant_sent_at=None)
                    matcher, options = SimpleNamespace(finish=AsyncMock()), SimpleNamespace(semantic_voice=False)
                    if function == 'render_chat_result':
                        await self.ns[function](self.bot, event, matcher, result, options, classifier_user_text='current turn')
                    else:
                        await self.ns[function](self.bot, event, matcher, 'synthetic', SimpleNamespace(),
                                                SimpleNamespace(stored='synthetic'), result, options,
                                                classifier_user_text='current turn', tts_candidate_enabled=False)
                    self.assertEqual(scheduler.call_count, expected)

    async def test_response_failures_use_distinct_registered_safe_codes(self):
        for status in ['empty_response', 'response_too_large', 'json_invalid', 'contract_invalid', 'response_truncated', 'response_filtered', 'unsupported_combination']:
            self.ns['_record_remote_sticker_classifier_reliability'](status)
            call = self.ns['record_result_safely'].call_args
            self.assertIn(call.kwargs['code'], self.reliability.CODE_CONTRACTS)
            self.reliability.create_reliability_event(
                **call.kwargs, category=self.reliability.CODE_CONTRACTS[call.kwargs['code']].category,
            )
        codes = [c.kwargs['code'] for c in self.ns['record_result_safely'].call_args_list]
        self.assertEqual(len(set(codes)), 7)


if __name__ == '__main__':
    unittest.main()
