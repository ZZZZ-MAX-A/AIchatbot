from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class EncyclopediaObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.module = load_module('src.plugins.ai_chat.encyclopedia_observability', AI_CHAT_ROOT / 'encyclopedia_observability.py')

    def observation(self, **overrides):
        value = {
            'encyclopedia_trace_id': '11111111-1111-4111-8111-111111111111',
            'encyclopedia_mode': 'prefetch', 'encyclopedia_policy_reason': 'ready',
            'encyclopedia_trigger': 'direct_question', 'encyclopedia_status': 'found',
            'encyclopedia_evidence_provided': True, 'encyclopedia_evidence_provided_count': 1,
            'encyclopedia_lookup_attempted': True, 'encyclopedia_chat_requests': 1,
        }
        value.update(overrides)
        return value

    def test_record_distinguishes_model_decisions_query_failures_and_reply_failure(self):
        cases = [
            ('not_requested', 'model_tool_decision'), ('not_needed', 'planner_decision'),
            ('skipped', 'local_gate'), ('not_found', 'public_lookup'), ('no_content', 'public_lookup'),
            ('lookup_timeout', 'public_lookup'), ('source_unavailable', 'public_lookup'),
            ('planner_timeout', 'planner'), ('planner_invalid_response', 'planner'),
            ('invalid_arguments', 'query_arguments'), ('unsupported_tool', 'tool_dispatch'),
        ]
        for status, location in cases:
            with self.subTest(status=status):
                row = self.module.build_encyclopedia_turn_log(self.observation(encyclopedia_status=status, encyclopedia_evidence_provided=False), 'linyin', reply='回复')
                self.assertEqual(row['location'], location)
        row = self.module.build_encyclopedia_turn_log(self.observation(), 'linyin', error=TimeoutError('PRIVATE-ERROR timeout'))
        self.assertEqual(row['status'], 'found')
        self.assertTrue(row['evidence_provided'])
        self.assertEqual(row['location'], 'reply_request')
        self.assertEqual(row['reply_failure_code'], 'request_timeout')
        self.assertNotIn('PRIVATE', json.dumps(row))

    def test_uncertain_reply_after_evidence_is_a_review_hint_not_a_verdict(self):
        row = self.module.build_encyclopedia_turn_log(self.observation(), 'aike', reply='这个名字以前没听过，您指的是哪个作品里的角色？')
        self.assertEqual(row['location'], 'reply_review')
        self.assertTrue(row['reply_uncertainty_cue'])
        self.assertIn('不能据此断定答错', row['detail'])
        self.assertNotIn('您指的是', json.dumps(row, ensure_ascii=False))

    def test_closed_schema_omits_private_text_and_rejects_freeform_metadata(self):
        observation = self.observation(
            query='PRIVATE-QUERY', results='PRIVATE-PAGE', role_card='PRIVATE-CARD', api_key='PRIVATE-KEY',
            encyclopedia_trace_id='PRIVATE-TRACE', encyclopedia_mode='PRIVATE-MODE',
            encyclopedia_tool_statuses=['found', 'PRIVATE-STATUS'], encyclopedia_plan_ms=-1,
            encyclopedia_failure_code='PRIVATE-FAILURE', encyclopedia_source_error_types=['HTTPStatusError', 'PRIVATE-TYPE'],
        )
        row = self.module.build_encyclopedia_turn_log(observation, 'PRIVATE-PERSONA', reply='PRIVATE-REPLY')
        text = json.dumps(row, ensure_ascii=False)
        self.assertNotIn('PRIVATE', text)
        self.assertEqual(row['tool_statuses'], ['found', 'unknown'])
        self.assertEqual(row['persona'], 'other')
        self.assertEqual(row['plan_ms'], 0)
        self.assertEqual(row['query_failure_code'], '')
        self.assertEqual(row['source_error_types'], ['HTTPStatusError', 'unknown'])

    def test_json_lines_use_beijing_time_and_preserve_previous_turns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'encyclopedia.log'
            first = self.observation()
            self.assertTrue(self.module.write_encyclopedia_turn_log_safely(first, 'aike', reply='第一轮回复', path=path))
            second = self.observation(encyclopedia_status='not_needed', encyclopedia_evidence_provided=False)
            self.assertTrue(self.module.write_encyclopedia_turn_log_safely(second, 'linyin', reply='第二轮回复', path=path))
            rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
            self.assertEqual([row['persona'] for row in rows], ['aike', 'linyin'])
            self.assertEqual([row['reply_status'] for row in rows], ['succeeded', 'succeeded'])
            self.assertTrue(all(row['time'].endswith('+08:00') for row in rows))
        row = self.module.build_encyclopedia_turn_log(self.observation(), 'aike', reply='回复', occurred_at=datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(row['time'], '2026-10-14T08:00:00+08:00')

    def test_log_io_failure_does_not_raise_into_chat(self):
        with tempfile.TemporaryDirectory() as directory:
            blocked = Path(directory) / 'not-a-directory'
            blocked.write_text('existing file', encoding='utf-8')
            observation = self.observation()
            result = self.module.write_encyclopedia_turn_log_safely(observation, 'aike', reply='正常回复', path=blocked / 'encyclopedia.log')
            self.assertFalse(result)
            self.assertFalse(observation['encyclopedia_log_written'])
            self.assertEqual(observation['encyclopedia_reply_status'], 'succeeded')

    def test_cancellation_empty_reply_and_disabled_policy_are_visible(self):
        row = self.module.build_encyclopedia_turn_log(self.observation(), 'linyin', error=asyncio.CancelledError())
        self.assertEqual(row['location'], 'interrupted')
        self.assertEqual(row['reply_status'], 'cancelled')
        self.assertEqual(self.module.build_encyclopedia_turn_log(self.observation(), 'linyin', reply='  ')['location'], 'reply_empty')
        row = self.module.build_encyclopedia_turn_log(self.observation(encyclopedia_status='disabled', encyclopedia_policy_reason='not_allowed'), 'linyin', reply='回复')
        self.assertEqual(row['policy'], 'not_allowed')
        self.assertEqual(row['location'], 'policy_gate')

    def test_partial_tool_failure_does_not_hide_successful_evidence(self):
        row = self.module.build_encyclopedia_turn_log(self.observation(encyclopedia_status='not_found', encyclopedia_tool_statuses=['found', 'not_found']), 'aike', reply='回复')
        self.assertEqual(row['location'], 'lookup_partial')
        self.assertTrue(row['evidence_provided'])
        self.assertEqual(row['tool_statuses'], ['found', 'not_found'])

    def test_nested_diagnostics_reject_raw_text_and_unrecognised_fields(self):
        raw = {
            'outcome': 'completed', 'status': 'lookup_timeout', 'cache': 'miss',
            'query': 'PRIVATE-QUERY', 'elapsed_ms': -3,
            'candidates': [{'ref': 'PRIVATE-TERM', 'chars': 4, 'title': 'PRIVATE-TITLE'}],
            'planner': {'content': 'PRIVATE-JSON', 'reasoning_content': 'PRIVATE-REASONING',
                        'finish_reason': 'PRIVATE-FINISH', 'model_ref': 'PRIVATE-MODEL', 'completion_tokens': 'PRIVATE-TOKENS',
                        'thinking_mode': 'PRIVATE-MODE'},
            'requests': [{'phase': 'PRIVATE-PHASE', 'url': 'PRIVATE-URL', 'body': 'PRIVATE-BODY',
                          'error_type': 'PRIVATE-ERROR', 'api_error': 'PRIVATE-API'}],
        }
        observation = self.observation(encyclopedia_runs=[raw], encyclopedia_model_requests=[{
            'content': 'PRIVATE-REPLY', 'error_type': 'PRIVATE-ERROR', 'finish_reason': 'PRIVATE-FINISH',
        }])
        row = self.module.build_encyclopedia_turn_log(observation, 'aike', reply='回复')
        self.assertEqual(row['schema_version'], 2)
        self.assertNotIn('PRIVATE', json.dumps(row))
        self.assertEqual(row['query_runs'][0]['elapsed_ms'], 0)
        self.assertIsNone(row['query_runs'][0]['planner']['completion_tokens'])

    def test_nested_diagnostic_collections_are_bounded(self):
        row = self.module.build_encyclopedia_turn_log(self.observation(
            encyclopedia_runs=[{'requests': [{}] * 30, 'candidates': [{}] * 9}] * 5,
            encyclopedia_model_requests=[{}] * 5,
        ), 'linyin', reply='回复')
        self.assertEqual(len(row['query_runs']), 2)
        self.assertEqual(len(row['query_runs'][0]['requests']), 24)
        self.assertEqual(len(row['query_runs'][0]['candidates']), 3)
        self.assertEqual(len(row['model_requests']), 2)


if __name__ == '__main__':
    unittest.main()
