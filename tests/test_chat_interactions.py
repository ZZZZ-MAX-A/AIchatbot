from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest

from pure_ai_chat_loader import AI_CHAT_ROOT, ensure_ai_chat_packages, load_module


class ChatInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()
        cls.mod = load_module('src.plugins.ai_chat.chat_interactions', AI_CHAT_ROOT / 'chat_interactions.py')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'nested' / 'interactions.db'
        self.store = self.mod.InteractionStore(self.path)
        self.key = self.mod.InteractionKey('account-a', 'aike', 'owner')
        self.now = datetime(2026, 10, 12, 1, 0, tzinfo=timezone.utc)

    def test_read_missing_does_not_create_any_files(self):
        self.assertIsNone(self.store.latest(self.key))
        self.assertFalse(self.path.parent.exists())

    def test_group_and_private_share_only_delivery_metadata(self):
        self.store.record_success(self.key, source='group', succeeded_at=self.now)
        record = self.mod.InteractionStore(self.path).latest(self.key)
        self.assertEqual(record.source, 'group')
        self.assertEqual(datetime.fromisoformat(record.succeeded_at), self.now)
        self.store.record_success(self.key, source='private', succeeded_at=self.now + timedelta(hours=1))
        self.assertEqual(self.store.latest(self.key).source, 'private')
        with closing(sqlite3.connect(self.path)) as connection:
            columns = {row[1] for row in connection.execute('PRAGMA table_info(owner_interactions)')}
        self.assertEqual(columns, {'bot_self_id', 'persona_id', 'owner_id', 'succeeded_at', 'source'})

    def test_accounts_personas_and_owners_are_isolated(self):
        self.store.record_success(self.key, source='private', succeeded_at=self.now)
        for key in [self.mod.InteractionKey('account-b', 'aike', 'owner'),
                    self.mod.InteractionKey('account-a', 'linyin', 'owner'),
                    self.mod.InteractionKey('account-a', 'aike', 'other')]:
            self.assertIsNone(self.store.latest(key))

    def test_delayed_completion_cannot_move_time_backwards(self):
        self.store.record_success(self.key, source='group', succeeded_at=self.now)
        self.store.record_success(self.key, source='private', succeeded_at=self.now - timedelta(days=3))
        self.assertEqual(self.store.latest(self.key).source, 'group')
        self.assertEqual(datetime.fromisoformat(self.store.latest(self.key).succeeded_at), self.now)

    def test_concurrent_writes_keep_latest_success(self):
        def record(index):
            self.store.record_success(self.key, source='group', succeeded_at=self.now + timedelta(seconds=index))
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(record, [5, 1, 8, 3, 10, 2, 7, 9]))
        self.assertEqual(datetime.fromisoformat(self.store.latest(self.key).succeeded_at), self.now + timedelta(seconds=10))

    def test_invalid_input_does_not_create_database(self):
        for kwargs in [dict(source='proactive'), dict(source='private', succeeded_at=datetime(2026, 10, 12))]:
            with self.assertRaises(ValueError):
                self.store.record_success(self.key, **kwargs)
        with self.assertRaises(ValueError):
            self.store.latest(self.mod.InteractionKey('', 'aike', 'owner'))
        self.assertFalse(self.path.exists())


if __name__ == '__main__':
    unittest.main()
