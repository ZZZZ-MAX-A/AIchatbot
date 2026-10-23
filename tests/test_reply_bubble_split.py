from __future__ import annotations

import asyncio
import random
import types
import unittest

from pure_ai_chat_loader import ensure_ai_chat_packages, load_module, AI_CHAT_ROOT


DAILY_THREE = (
    '\uFF08\u5979\u542c\u89c1\u95e8\u54cd\uff0c\u628a\u7b14\u653e\u4e0b\u3002\uFF09\n'
    '\u300c\u8fdb\u3002\u300d\n'
    '\n'
    '\uFF08\u5979\u628a\u676f\u5b50\u63a8\u8fc7\u53bb\u4e00\u70b9\u3002\uFF09\n'
    '\u300c\u6211\u4e5f\u5728\u3002\u300d\n'
    '\n'
    '\uFF08\u5979\u54ac\u4f4f\u4e0b\u5507\u3002\uFF09\n'
    '\u300c\u8c22\u8c22\u4f60\u3002\u300d'
)

ADULT_THREE = (
    '\uFF08\u5979\u6ca1\u6709\u8bdd\uff0c\u53ea\u662f\u8eab\u4f53\u5fae\u5fae\u5411\u524d\u503e\u3002\uFF09\n'
    '\n'
    '\u300c\u8981\u7684\u8bdd\uff0c\u5c31\u8fd9\u6837\u3002\u300d\n'
    '\n'
    '\uFF08\u5979\u4f4e\u58f0\u5730\u547c\u51fa\u4e00\u53e3\u6c14\u3002\uFF09\n'
    '\u300c\u6162\u4e00\u70b9\u3002\u300d'
)

SHORT_ONE = '\u300c\u597d\u3002\u300d'

UNBALANCED = '\uFF08\u5979\u6ca1\u8bf4\u5b8c\n\n\u300c\u7b49\u4e00\u4e0b\u3002\u300d'


def seven_paragraphs() -> str:
    parts = [
        '\uFF08' + ('\u52a8\u4f5c\u8d77\u624b' * 8) + '\uFF09',
        '\u300c\u8981\u3002\u300d',
        '\u300c\u8fd9\u6b21\u771f\u7684\u8981\u4e00\u6b21\u3002\u300d',
        '\uFF08\u5979\u770b\u4e86\u4f60\u4e00\u773c\u3002\uFF09',
        '\u300c\u6293\u4f4f\u6211\u3002\u300d',
        '\u300c\u518d\u8fd1\u4e00\u70b9\u3002\u300d',
        '\u300c\u522b\u505c\u3002\u300d',
    ]
    return '\n\n'.join(parts)


class ReplyBubbleSplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_ai_chat_packages()
        cls.mod = load_module(
            'src.plugins.ai_chat.reply_bubble_split',
            AI_CHAT_ROOT / 'reply_bubble_split.py',
        )

    def setUp(self) -> None:
        self.mod.clear_chat_bubble_generations_for_tests()

    def test_daily_three_beats_split(self):
        bubbles = self.mod.split_reply_bubbles(DAILY_THREE)
        self.assertEqual(len(bubbles), 3)
        self.assertTrue(bubbles[0].startswith('\uFF08'))
        self.assertIn('\u300c\u8fdb\u3002\u300d', bubbles[0])
        self.assertIn('\u300c\u8c22\u8c22\u4f60\u3002\u300d', bubbles[2])

    def test_adult_three_beats_allow_long_opening(self):
        bubbles = self.mod.split_reply_bubbles(ADULT_THREE)
        self.assertEqual(len(bubbles), 3)
        self.assertTrue(self.mod.is_pure_action_paragraph(bubbles[0]))

    def test_short_reply_stays_one_bubble(self):
        bubbles = self.mod.split_reply_bubbles(SHORT_ONE)
        self.assertEqual(bubbles, [SHORT_ONE])

    def test_no_blank_line_stays_one_bubble(self):
        text = '\uFF08\u5979\u70b9\u5934\u3002\uFF09\n\u300c\u597d\u3002\u300d'
        self.assertEqual(self.mod.split_reply_bubbles(text), [text])

    def test_unbalanced_brackets_fail_closed(self):
        bubbles = self.mod.split_reply_bubbles(UNBALANCED)
        self.assertEqual(bubbles, [UNBALANCED.strip()])

    def test_many_paragraphs_pack_to_three(self):
        bubbles = self.mod.split_reply_bubbles(seven_paragraphs())
        self.assertEqual(len(bubbles), 3)
        self.assertTrue(bubbles[0].startswith('\uFF08'))
        self.assertIn('\u300c\u522b\u505c\u3002\u300d', bubbles[2])

    def test_disabled_resolve_keeps_full_text(self):
        resolved = self.mod.resolve_chat_bubbles(DAILY_THREE, enabled=False)
        self.assertEqual(resolved, (DAILY_THREE,))

    def test_empty_text_returns_empty_split(self):
        self.assertEqual(self.mod.split_reply_bubbles('   '), [])

    def test_gate_requires_owner_private_when_flag_on(self):
        config = types.SimpleNamespace(
            enable_chat_bubble_split=True,
            chat_bubble_split_owner_private_only=True,
        )
        self.assertTrue(
            self.mod.chat_bubble_split_allowed(config, is_owner=True, is_private=True)
        )
        self.assertFalse(
            self.mod.chat_bubble_split_allowed(config, is_owner=False, is_private=True)
        )
        self.assertFalse(
            self.mod.chat_bubble_split_allowed(config, is_owner=True, is_private=False)
        )

    def test_default_off_never_allows_split(self):
        config = types.SimpleNamespace(
            enable_chat_bubble_split=False,
            chat_bubble_split_owner_private_only=True,
        )
        self.assertFalse(
            self.mod.chat_bubble_split_allowed(config, is_owner=True, is_private=True)
        )

    def test_delay_bands_and_total_budget(self):
        rng = random.Random(0)
        short = self.mod.bubble_delay_ms(
            'short',
            'also',
            min_delay_ms=700,
            max_delay_ms=1200,
            remaining_budget_ms=3500,
            rng=rng,
        )
        self.assertGreaterEqual(short, 500)
        self.assertLessEqual(short, 800)
        long_prev = self.mod.bubble_delay_ms(
            'x' * 130,
            'tail',
            min_delay_ms=700,
            max_delay_ms=1200,
            remaining_budget_ms=3500,
            rng=rng,
        )
        self.assertGreaterEqual(long_prev, 1000)
        self.assertLessEqual(long_prev, 1500)
        exhausted = self.mod.bubble_delay_ms(
            'x' * 130,
            'tail',
            min_delay_ms=700,
            max_delay_ms=1200,
            remaining_budget_ms=0,
            rng=rng,
        )
        self.assertEqual(exhausted, 0)
        delays = self.mod.next_bubble_delays(
            ['a' * 200, 'b' * 200, 'c' * 200],
            min_delay_ms=700,
            max_delay_ms=1200,
            rng=random.Random(1),
        )
        self.assertEqual(len(delays), 2)
        self.assertLessEqual(sum(delays), 3500)

    def test_generation_cancel_stops_wait(self):
        async def _run():
            key = 'persona:test:private:1'
            gen = self.mod.bump_chat_bubble_generation(key)
            task = asyncio.create_task(self.mod.wait_for_bubble_delay(key, gen, 2000))
            await asyncio.sleep(0.05)
            self.mod.bump_chat_bubble_generation(key)
            cancelled = await task
            self.assertTrue(cancelled)

        asyncio.run(_run())


if __name__ == '__main__':
    unittest.main()
