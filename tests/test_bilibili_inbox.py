from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock, patch

from pure_ai_chat_loader import ensure_ai_chat_packages

import httpx

from src.bilibili_connector import BilibiliBinding, BindingStore, DeliveryStore, PrivateMessageResult
from src.bilibili_history import BilibiliHistoryStore, HistoryScope
from src.bilibili_history_bridge import BilibiliHistoryWriter
from src.bilibili_inbox import (
    InboxBlocked, InboxPolicy, InboxStore, deliver_reply, fetch_messages, generate_reply,
    normalize_message, poll_inbox, reply_delivery, run_inbox,
)

BINDING = BilibiliBinding("aike", "aike", "101", "202")
STAMP = int(time.time()) - 60


def raw(seq, *, owner=True, text=None, kind=1, **changes):
    value = {"msg_seqno": seq, "msg_key": str(100000 + seq), "sender_uid": "202" if owner else "101",
        "receiver_id": "101" if owner else "202", "receiver_type": 1, "timestamp": STAMP + seq,
        "msg_type": kind, "msg_status": 0, "content": json.dumps({"content": text or f"synthetic message {seq}"})}
    return {**value, **changes}


class InboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_ai_chat_packages()

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name)
        self.store = InboxStore(self.home, "a" * 64)
        self.policy = InboxPolicy()
        self.now = time.time()
        BindingStore(self.home / "binding.json").save(BINDING)
        self.writer = object.__new__(BilibiliHistoryWriter)
        self.writer.binding = BINDING
        self.writer.config = NS()
        self.writer.scope = HistoryScope(self.store.scope)
        self.writer.store = BilibiliHistoryStore(self.home / "history.db")

    def client(self, pages):
        requests = []
        def handle(request):
            requests.append(request)
            page = pages.pop(0)
            return httpx.Response(page.pop("_http", 200), json=page)
        client = httpx.Client(transport=httpx.MockTransport(handle))
        self.addCleanup(client.close)
        return NS(_client=client, _json=lambda response: response.json()), requests

    def page(self, messages, more=0, code=0):
        return {"code": code, "data": {"messages": messages, "has_more": more, "max_seqno": 999999}}

    def queue(self, messages=None):
        messages = messages or [raw(1)]
        self.store.initialize(0)
        normalized = [normalize_message(m, BINDING) for m in messages]
        self.store.ingest(normalized, max(m["seq"] for m in normalized), self.now)
        return self.store.create_batch(self.now + 5, self.policy)

    @contextmanager
    def browser(self, client):
        yield NS(account_client=client)

    def test_defaults_validate_and_boolean_or_extra_configuration_is_rejected(self):
        self.policy.validate()
        for changes in ({"min_poll_seconds": True}, {"debounce_seconds": 0}, {"min_poll_seconds": 0}):
            with self.assertRaises(ValueError):
                replace(self.policy, **changes).validate()

    def test_owner_pair_and_outbound_direction_are_validated(self):
        self.assertEqual(normalize_message(raw(1), BINDING)["role"], "user")
        self.assertEqual(normalize_message(raw(2, owner=False), BINDING)["role"], "assistant")
        for changes in ({"sender_uid": "999"}, {"receiver_id": "999"}, {"receiver_type": 2}, {"msg_seqno": True}):
            with self.assertRaises(ValueError):
                normalize_message(raw(1, **changes), BINDING)

    def test_retracted_and_unsupported_content_is_not_presented_as_seen(self):
        self.assertTrue(normalize_message(raw(1, msg_status=1), BINDING)["unavailable"])
        message = normalize_message(raw(2, kind=2, content=json.dumps({"url": "SYNTHETIC_IMAGE"})), BINDING)
        self.assertNotIn("SYNTHETIC_IMAGE", message["text"])
        self.assertIn("尚未解析", message["text"])

    def test_fetch_paginates_backwards_and_does_not_trust_global_max(self):
        client, requests = self.client([self.page([raw(5), raw(4), raw(3)], 1), self.page([raw(3), raw(2), raw(1)])])
        messages, cursor = fetch_messages(client, BINDING, cursor=1)
        self.assertEqual([m["seq"] for m in messages], [2, 3, 4, 5])
        self.assertEqual(cursor, 5)
        self.assertEqual(requests[1].url.params["end_seqno"], "3")
        self.assertEqual(requests[0].url.params["talker_id"], BINDING.owner_mid)

    def test_repeated_page_and_unread_gap_are_not_silently_skipped(self):
        for pages in ([self.page([raw(5)], 1)] * 3, [self.page([raw(5)], 1)]):
            client, _ = self.client([dict(p) for p in pages])
            with self.assertRaises(Exception):
                fetch_messages(client, BINDING, cursor=1, max_pages=len(pages))

    def test_blocked_http_or_business_codes_are_identified(self):
        for page in ({**self.page([]), "_http": 412}, self.page([], code=-352)):
            client, _ = self.client([page])
            with self.assertRaises(InboxBlocked):
                fetch_messages(client, BINDING, cursor=0)

    def test_baseline_skips_history_then_only_queues_new_owner_messages(self):
        client, _ = self.client([self.page([raw(2), raw(1)]), self.page([raw(4, owner=False), raw(3), raw(2)])])
        with patch("src.bilibili_inbox.inbox_browser", side_effect=lambda *_: self.browser(client)):
            self.assertEqual(poll_inbox(self.store, BINDING), {"status": "initialized", "received": 0})
            self.assertIsNone(self.store.pending_window())
            self.assertEqual(poll_inbox(self.store, BINDING)["received"], 1)
        key = self.store.create_batch(self.now, self.policy)
        self.assertEqual([m["seq"] for m in self.store.batch(key)["messages"]], [3])
        self.assertEqual(self.store.state()["cursor"], 4)

    def test_duplicate_receive_and_restart_preserve_cursor_and_queue(self):
        self.store.initialize(0)
        message = normalize_message(raw(1), BINDING)
        self.assertEqual(self.store.ingest([message], 1, self.now), 1)
        self.assertEqual(self.store.ingest([message], 1, self.now), 0)
        restarted = InboxStore(self.home, self.store.scope)
        self.assertEqual(restarted.state()["cursor"], 1)
        self.assertEqual(restarted.counts()["pending_messages"], 1)

    def test_cursor_is_not_advanced_when_fetch_fails(self):
        self.store.initialize(1)
        client, _ = self.client([self.page([raw(3, sender_uid="999")])])
        with patch("src.bilibili_inbox.inbox_browser", side_effect=lambda *_: self.browser(client)):
            with self.assertRaises(ValueError):
                poll_inbox(self.store, BINDING)
        self.assertEqual(self.store.state()["cursor"], 1)

    def test_batch_order_merge_and_message_limit(self):
        key = self.queue([raw(3), raw(1), raw(2)])
        self.assertEqual([m["seq"] for m in self.store.batch(key)["messages"]], [1, 2, 3])
        self.assertIsNone(self.store.pending_window())

    def test_generation_is_recovered_as_interrupted_not_generated_twice(self):
        key = self.queue()
        self.store.recover()
        self.assertEqual(self.store.batch(key)["status"], "interrupted")
        self.assertEqual(self.store.unfinished(), [])

    def test_plain_reply_uses_character_memory_and_records_real_both_sides(self):
        key = self.queue([raw(1, text="合成测试消息"), raw(2, text="第二句")])
        model = MagicMock()
        model.usage = [{"total_tokens": 321}]
        model.ask.return_value = {"reply": "合成角色回复"}
        account = MagicMock()
        account.send_private_message.return_value = PrivateMessageResult(True, False, 200, 0, "", "synthetic-receipt")
        with patch("src.bilibili_history_bridge.BilibiliHistoryWriter", return_value=self.writer), \
             patch("src.bilibili_memory.load_owner_memory", return_value="SYNTHETIC_QQ_MEMORY") as memory, \
             patch("src.bilibili_persona.persona_settings", return_value=("SYNTHETIC_ROLE", NS(), False)), \
             patch("src.bilibili_persona.PersonaModel", return_value=model) as factory, \
             patch("src.bilibili_inbox.inbox_browser", side_effect=lambda *_: self.browser(account)), \
             patch("src.plugins.ai_chat.rag.providers.build_embedding_provider", side_effect=RuntimeError("offline")):
            self.assertEqual(generate_reply(self.store, BINDING, NS(), key), "sent")
        memory.assert_called_once()
        self.assertEqual(factory.call_args.kwargs["memory"], "SYNTHETIC_QQ_MEMORY")
        self.assertEqual(model.ask.call_args.args[0], "reply")
        current = model.ask.call_args.args[1]["owner_current_messages"]
        self.assertEqual([m["text"] for m in current], ["合成测试消息", "第二句"])
        self.assertNotIn("message_id", current[0])
        self.assertEqual(account.send_private_message.call_args.kwargs["delivery_key"], "inbox-reply-v1:" + key)
        self.assertEqual(self.store.batch(key)["status"], "sent")
        snapshot = self.writer.store.snapshot(self.writer.scope, provider="", model="")
        self.assertEqual([m.role for m in snapshot.recent], ["user", "user", "assistant"])
        self.assertEqual(snapshot.recent[-1].content, "合成角色回复")
        model.close.assert_called_once()

    def test_invalid_or_failed_generation_is_not_sent_or_retried(self):
        key = self.queue()
        model = MagicMock()
        model.usage = []
        model.ask.return_value = {"reply": "x" * 301}
        with patch("src.bilibili_history_bridge.BilibiliHistoryWriter", return_value=self.writer), \
             patch("src.bilibili_memory.load_owner_memory"), \
             patch("src.bilibili_persona.persona_settings", return_value=("role", NS(), False)), \
             patch("src.bilibili_persona.PersonaModel", return_value=model), \
             patch("src.bilibili_inbox.inbox_browser") as browser:
            self.assertEqual(generate_reply(self.store, BINDING, NS(), key), "generation_failed")
        self.assertEqual(self.store.batch(key)["status"], "generation_failed")
        browser.assert_not_called()
        self.assertEqual(self.store.unfinished(), [])

    def test_stop_after_generation_keeps_draft_without_sending(self):
        key = self.queue()
        self.store.finish(key, "ready", draft="synthetic reply")
        with patch("src.bilibili_inbox.inbox_browser") as browser:
            self.assertEqual(deliver_reply(self.store, BINDING, key, self.writer, should_stop=lambda: True), "cancelled")
        browser.assert_not_called()
        self.assertEqual(self.store.batch(key)["status"], "ready")

    def test_unknown_platform_result_never_reposts_after_restart(self):
        key = self.queue()
        self.store.finish(key, "sending", draft="synthetic reply")
        ledger = DeliveryStore(self.home / "deliveries.sqlite3")
        import hashlib
        digest = hashlib.sha256(json.dumps([BINDING.aike_mid, BINDING.owner_mid, "explicit", "inbox-reply-v1:" + key], ensure_ascii=False).encode()).hexdigest()
        request_id = ledger.reserve(digest)
        ledger.finish(request_id, "unknown")
        with patch("src.bilibili_inbox.inbox_browser") as browser:
            self.assertEqual(deliver_reply(self.store, BINDING, key, self.writer), "failed_or_unknown")
        browser.assert_not_called()
        self.assertEqual(self.store.batch(key)["status"], "unknown")
        self.assertFalse((self.home / "history.db").exists())

    def test_successful_ledger_reconciles_archive_without_reposting(self):
        key = self.queue()
        self.store.finish(key, "sending", draft="synthetic reply")
        import hashlib
        ledger = DeliveryStore(self.home / "deliveries.sqlite3")
        digest = hashlib.sha256(json.dumps([BINDING.aike_mid, BINDING.owner_mid, "explicit", "inbox-reply-v1:" + key], ensure_ascii=False).encode()).hexdigest()
        request_id = ledger.reserve(digest)
        ledger.finish(request_id, "sent", 0)
        with patch("src.bilibili_inbox.inbox_browser") as browser, \
             patch("src.plugins.ai_chat.rag.providers.build_embedding_provider", side_effect=RuntimeError("offline")):
            self.assertEqual(deliver_reply(self.store, BINDING, key, self.writer), "sent")
            self.assertEqual(deliver_reply(self.store, BINDING, key, self.writer), "sent")
        browser.assert_not_called()
        snapshot = self.writer.store.snapshot(self.writer.scope, provider="", model="")
        self.assertEqual(len(snapshot.recent), 1)
        self.assertEqual(snapshot.recent[0].time_kind, "send_attempt")

    def test_idle_check_does_not_create_model_or_reply(self):
        with patch("src.bilibili_inbox.poll_inbox", return_value={"status":"ok", "received":0}), \
             patch("src.bilibili_inbox.generate_reply") as generate:
            self.assertEqual(run_inbox(self.store, BINDING, NS(), self.policy, once=True)["status"], "checked")
        generate.assert_not_called()

    def test_receive_failures_persist_backoff_across_restart(self):
        for error, seconds in [(RuntimeError("PRIVATE_ERROR"), 900), (InboxBlocked(), 14400)]:
            with self.subTest(seconds=seconds):
                self.store.update_state(retry_not_before=0, next_poll=0)
                with patch("src.bilibili_inbox.poll_inbox", side_effect=error) as poll:
                    run_inbox(self.store, BINDING, NS(), self.policy, once=True, clock=lambda:self.now)
                self.assertEqual(self.store.state()["retry_not_before"], self.now + seconds)
                with patch("src.bilibili_inbox.poll_inbox") as poll:
                    run_inbox(self.store, BINDING, NS(), self.policy, once=True, clock=lambda:self.now+10)
                poll.assert_not_called()
                self.assertNotIn("PRIVATE_ERROR", json.dumps(self.store.state()))

    def test_local_browser_busy_does_not_get_platform_failure_backoff(self):
        from src.bilibili_browser import BrowserControllerBusy
        with patch("src.bilibili_inbox.poll_inbox", side_effect=BrowserControllerBusy()):
            run_inbox(self.store, BINDING, NS(), self.policy, once=True, clock=lambda:self.now)
        self.assertEqual(self.store.state()["retry_not_before"], self.now + self.policy.min_poll_seconds)

    def test_merging_waits_then_handles_consecutive_messages_in_one_batch(self):
        self.store.initialize(0)
        self.store.ingest([normalize_message(raw(1), BINDING), normalize_message(raw(2), BINDING)], 2, self.now)
        with patch("src.bilibili_inbox.poll_inbox", return_value={"status":"ok", "received":0}), \
             patch("src.bilibili_inbox.generate_reply", return_value="sent") as generate:
            run_inbox(self.store, BINDING, NS(), self.policy, once=True, clock=lambda:self.now+2)
            generate.assert_not_called()
            run_inbox(self.store, BINDING, NS(), self.policy, once=True, clock=lambda:self.now+5)
        self.assertEqual(len(self.store.batch(generate.call_args.args[3])["messages"]), 2)
        generate.assert_called_once()

    def test_separate_process_status_and_stop_do_not_need_live_services(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, AIKE_BILIBILI_HOME=str(self.home))
        code = (
            "from pathlib import Path; import os; from unittest.mock import patch; from types import SimpleNamespace as NS; "
            "from src.bilibili_inbox import InboxStore,InboxPolicy,run_inbox; "
            "from src.bilibili_connector import BilibiliBinding; "
            "mock=patch('src.bilibili_inbox.poll_inbox',return_value=dict(status='ok',received=0));mock.start(); "
            f"run_inbox(InboxStore(Path(os.environ['AIKE_BILIBILI_HOME']),{'a'*64!r}),BilibiliBinding('aike','aike','101','202'),NS(),InboxPolicy())"
        )
        process = subprocess.Popen([sys.executable, '-u', '-c', code], cwd=root, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            deadline = time.monotonic() + 10
            while not self.store.session_path.is_file() and process.poll() is None and time.monotonic()<deadline:
                time.sleep(0.05)
            entry = root / 'scripts' / 'bilibili_inbox.py'
            status = subprocess.run([sys.executable,str(entry),'status'],env=env,cwd=root,capture_output=True,check=True)
            self.assertTrue(json.loads(status.stdout)["running"])
            stop = subprocess.run([sys.executable,str(entry),'stop'],env=env,cwd=root,capture_output=True,check=True)
            self.assertEqual(json.loads(stop.stdout)["status"], "stop_requested")
            _, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode,0,stderr)
            self.assertFalse(self.store.is_running())
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)

    def test_background_launcher_returns_without_inheriting_captured_pipes(self):
        root = Path(__file__).resolve().parents[1]
        env = dict(os.environ, AIKE_BILIBILI_HOME=str(self.home))
        code = (
            "from pathlib import Path; import os; from unittest.mock import patch; from types import SimpleNamespace as NS; "
            "from src.bilibili_inbox import InboxStore,InboxPolicy,run_inbox; "
            "from src.bilibili_connector import BilibiliBinding; "
            "mock=patch('src.bilibili_inbox.poll_inbox',return_value=dict(status='ok',received=0));mock.start(); "
            f"run_inbox(InboxStore(Path(os.environ['AIKE_BILIBILI_HOME']),{'a'*64!r}),BilibiliBinding('aike','aike','101','202'),NS(),InboxPolicy())"
        )
        launch = (
            "import json,os,sys; from pathlib import Path; "
            "from scripts.bilibili_inbox import start_background; "
            f"print(json.dumps(start_background(Path(os.environ['AIKE_BILIBILI_HOME']),[sys.executable,'-u','-c',{code!r}])))"
        )
        try:
            result = subprocess.run([sys.executable, '-c', launch], cwd=root, env=env,
                capture_output=True, timeout=10, check=True)
            self.assertEqual(json.loads(result.stdout)["status"], "started")
            self.assertTrue(self.store.is_running())
        finally:
            if self.store.is_running():
                self.store.request_stop()
                deadline = time.monotonic() + 10
                while self.store.is_running() and time.monotonic() < deadline:
                    time.sleep(0.05)
                if self.store.is_running():
                    import signal
                    os.kill(self.store.state()["pid"], signal.SIGTERM)
        self.assertFalse(self.store.is_running())

    def test_background_launcher_reports_immediate_worker_exit(self):
        from scripts.bilibili_inbox import start_background
        with self.assertRaises(RuntimeError):
            start_background(self.home, [sys.executable, '-c', 'raise SystemExit(1)'])


if __name__ == '__main__':
    unittest.main()
