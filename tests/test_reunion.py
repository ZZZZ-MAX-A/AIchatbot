from __future__ import annotations

from datetime import datetime, timedelta, timezone
import types
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


UTC = timezone.utc


class ReunionUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.mod = load_module(
            'src.plugins.ai_chat.reunion',
            AI_CHAT_ROOT / 'reunion.py',
        )

    def test_short_gap_has_no_hint(self):
        now = datetime(2026, 8, 24, 21, 0, tzinfo=UTC)
        last = (now - timedelta(hours=1)).isoformat()
        self.assertEqual(self.mod.resolve_reunion_hint(last, now=now, min_gap_hours=3), '')

    def test_missing_timestamp_fail_closed(self):
        now = datetime(2026, 8, 24, 21, 0, tzinfo=UTC)
        self.assertEqual(self.mod.resolve_reunion_hint(None, now=now), '')
        self.assertEqual(self.mod.resolve_reunion_hint('not-a-time', now=now), '')

    def test_one_day_gap_is_not_relabelled_as_overnight(self):
        now = datetime(2026, 8, 24, 23, 0, tzinfo=UTC)
        last = datetime(2026, 8, 23, 14, 0, tzinfo=UTC)
        gap = self.mod.classify_reunion_gap(last, now, min_gap_hours=3)
        self.assertIsNotNone(gap)
        self.assertEqual(gap.bucket, self.mod.BUCKET_ONE_TWO_DAYS)
        hint = self.mod.resolve_reunion_hint(last.isoformat(), now=now)
        self.assertIn('约 1 天 9 小时', hint)
        self.assertIn('\u91cd\u9022', hint)
        self.assertIn('更强', hint)

    def test_several_days_bucket(self):
        now = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)
        last = now - timedelta(days=4)
        gap = self.mod.classify_reunion_gap(last, now)
        self.assertEqual(gap.bucket, self.mod.BUCKET_SEVERAL_DAYS)
        hint = self.mod.build_reunion_hint(gap)
        self.assertIn('约 4 天', hint)
        self.assertIn('\u4e0d\u8981\u4e3b\u52a8\u628a\u4e0a\u4e00\u573a', hint)

    def test_gate_owner_private_only(self):
        config = types.SimpleNamespace(
            enable_chat_reunion=True,
            chat_reunion_owner_private_only=True,
        )
        self.assertTrue(self.mod.reunion_allowed(config, is_owner=True, is_private=True))
        self.assertFalse(self.mod.reunion_allowed(config, is_owner=False, is_private=True))
        self.assertFalse(self.mod.reunion_allowed(config, is_owner=True, is_private=False))

    def test_disabled_gate(self):
        config = types.SimpleNamespace(
            enable_chat_reunion=False,
            chat_reunion_owner_private_only=True,
        )
        self.assertFalse(self.mod.reunion_allowed(config, is_owner=True, is_private=True))

    def test_all_thresholds_and_future_timestamp(self):
        now = datetime(2026, 10, 12, 0, 0, tzinfo=UTC)
        cases = [(3, self.mod.BUCKET_A_WHILE), (11.99, self.mod.BUCKET_A_WHILE),
                 (12, self.mod.BUCKET_HALF_DAY), (24, self.mod.BUCKET_ONE_TWO_DAYS),
                 (72, self.mod.BUCKET_SEVERAL_DAYS), (168, self.mod.BUCKET_LONG),
                 (336, self.mod.BUCKET_TWO_WEEKS), (720, self.mod.BUCKET_TWO_WEEKS)]
        for hours, bucket in cases:
            with self.subTest(hours=hours):
                gap = self.mod.classify_reunion_gap(now - timedelta(hours=hours), now)
                self.assertEqual(gap.bucket, bucket)
        self.assertIsNone(self.mod.classify_reunion_gap(now + timedelta(hours=1), now, min_gap_hours=0))

    def test_sleeping_overnight_does_not_increase_strength(self):
        last = datetime.fromisoformat('2026-10-11T23:00:00+08:00')
        now = datetime.fromisoformat('2026-10-12T08:00:00+08:00')
        gap = self.mod.classify_reunion_gap(last, now)
        self.assertEqual(gap.bucket, self.mod.BUCKET_A_WHILE)
        self.assertEqual(gap.time_of_day, '早上')
        self.assertIsNone(self.mod.classify_reunion_gap(last, last + timedelta(hours=1)))

    def test_emotional_cap_preserves_actual_month_gap(self):
        now = datetime(2026, 10, 12, tzinfo=UTC)
        hint = self.mod.resolve_reunion_hint((now - timedelta(days=30)).isoformat(), now=now)
        self.assertIn('实际聊天间隔：约 30 天', hint)
        self.assertIn('上限：', hint)
        self.assertIn('时间事实不封顶', hint)
        self.assertIn('角色卡', hint)
        self.assertIn('新话题就跟随新话题', hint)
        self.assertNotIn('先用很轻的一拍', hint)

    def test_legacy_flag_cannot_enable_non_owner_reunion(self):
        config = types.SimpleNamespace(enable_chat_reunion=True, chat_reunion_owner_private_only=False)
        self.assertFalse(self.mod.reunion_allowed(config, is_owner=False, is_private=True))

    def test_narrow_duration_correction_preserves_emotion_and_other_time_mentions(self):
        correct = self.mod.correct_capped_reunion_duration
        self.assertEqual(correct('主人，14天没和您说话，我很想您。', 30 * 86400),
                         '主人，30天没和您说话，我很想您。')
        for reply in ['两周没来找爱可了。', '电影两周后上映。', '不是两周没来，是一个月。',
                      '不止两周没来找爱可了。']:
            self.assertEqual(correct(reply, 14 * 86400), reply)
        for reply in ['电影两周后上映。', '不是两周没来，是一个月。', '不止两周没来找爱可了。']:
            self.assertEqual(correct(reply, 30 * 86400), reply)


if __name__ == '__main__':
    unittest.main()
