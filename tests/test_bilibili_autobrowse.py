from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock, patch

from src.bilibili_autobrowse import AutoBrowseStore, BrowsePolicy, execute_browser_round, run_loop
from src.bilibili_browser import profile_lock
from src.bilibili_connector import (
    BilibiliBinding, BilibiliConnectorError, BilibiliShareLimit, DeliveryStore,
    video_delivery_key, video_share_scope,
)
from src.bilibili_browse import preview
from src.bilibili_history import HistoryScope
from test_bilibili_daily_note import report


NOW = datetime(2026, 10, 22, 2, 0, tzinfo=timezone.utc).timestamp()  # Beijing 10:00.
BINDING = BilibiliBinding("aike", "aike", "101", "202")
BV = "BV1xx411c7mD"


class MinimumRandom:
    def randint(self, minimum, maximum):
        return minimum


class ShareQuotaTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = DeliveryStore(self.root / "deliveries.sqlite3")
        self.scope = video_share_scope(BINDING)

    def reserve(self, key, stamp=NOW):
        with patch("src.bilibili_connector.time.time", return_value=stamp):
            return self.store.reserve(key, share_scope=self.scope, bvid=BV)

    def test_three_per_beijing_day_persist_across_store_instances(self):
        for n in range(3):
            key = self.reserve(f"video-{n}", NOW + n * 7201)
            self.store.finish(key, "sent", 0)
        self.store = DeliveryStore(self.store.path)
        with self.assertRaises(BilibiliShareLimit) as error:
            self.reserve("fourth", NOW + 3 * 7201)
        self.assertEqual(error.exception.reason, "daily_limit")
        self.assertEqual(self.store.quota_status(BINDING, now=int(NOW + 3 * 7201))["remaining_today"], 0)
        self.reserve("next-day", NOW + 86400)

    def test_midnight_does_not_bypass_spacing_and_unknown_is_not_released(self):
        midnight = datetime(2026, 10, 22, 16, 0, tzinfo=timezone.utc).timestamp()
        key = self.reserve("unknown", midnight - 60)
        self.store.finish(key, "unknown")
        self.assertEqual(self.store.quota_status(BINDING, now=int(midnight))["used_today"], 0)
        with self.assertRaises(BilibiliShareLimit) as error:
            self.reserve("after-midnight", midnight)
        self.assertEqual(error.exception.reason, "cooldown")
        self.reserve("later", midnight + 7200)

    def test_confirmed_failure_releases_quota_but_duplicate_key_stays_reserved(self):
        key = self.reserve("failed")
        self.store.finish(key, "failed", -1)
        self.assertEqual(self.store.quota_status(BINDING, now=int(NOW))["used_today"], 0)
        with self.assertRaisesRegex(BilibiliConnectorError, "已阻止重复发送"):
            self.reserve("failed", NOW + 1)
        self.reserve("different-video", NOW + 1)

    def test_pending_reservation_blocks_other_processes_before_post(self):
        self.reserve("first")
        with self.assertRaises(BilibiliShareLimit):
            self.reserve("second")

    def test_concurrent_distinct_videos_cannot_bypass_cooldown(self):
        def attempt(n):
            try:
                return DeliveryStore(self.store.path).reserve(str(n), share_scope=self.scope, bvid=BV)
            except BilibiliShareLimit:
                return None
        with patch("src.bilibili_connector.time.time", return_value=NOW), ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(sum(value is not None for value in results), 1)

    def test_general_replies_do_not_use_active_share_quota(self):
        with patch("src.bilibili_connector.time.time", return_value=NOW):
            key = self.store.reserve("owner-requested-reply")
        self.store.finish(key, "sent", 0)
        self.assertEqual(self.store.quota_status(BINDING, now=int(NOW))["used_today"], 0)
        self.reserve("active-share")

    def test_separate_owner_pair_has_own_quota(self):
        self.reserve("owner-one")
        other = BilibiliBinding("aike", "aike", "101", "303")
        with patch("src.bilibili_connector.time.time", return_value=NOW):
            self.store.reserve("owner-two", share_scope=video_share_scope(other), bvid=BV)

    def test_legacy_receipts_count_conservatively_and_read_only_status_does_not_migrate(self):
        with closing(sqlite3.connect(self.store.path)) as c, c:
            c.execute("CREATE TABLE deliveries(delivery_key TEXT PRIMARY KEY,request_id TEXT,state TEXT,created_at INTEGER,code INTEGER)")
            c.execute("INSERT INTO deliveries VALUES('legacy','legacy-request','sent',?,0)", (NOW,))
        before = self.store.path.read_bytes()
        status = self.store.quota_status(BINDING, now=int(NOW))
        self.assertEqual(status["used_today"], 1)
        self.assertEqual(status["legacy_uncertain_today"], 1)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_matching_report_classifies_old_share_without_new_delivery_or_message_copy(self):
        with closing(sqlite3.connect(self.store.path)) as c, c:
            c.execute("CREATE TABLE deliveries(delivery_key TEXT PRIMARY KEY,request_id TEXT,state TEXT,created_at INTEGER,code INTEGER)")
            c.execute("INSERT INTO deliveries VALUES(?,'old-request','sent',?,0)", (video_delivery_key(BINDING, BV), NOW))
        reports = self.root / "previews"
        reports.mkdir()
        (reports / "fixture.json").write_text(json.dumps({"delivery": {"bvid": BV, "request_id": "old-request"}}), encoding="utf-8")
        self.store.register_reported_shares(BINDING, reports)
        status = self.store.quota_status(BINDING, now=int(NOW))
        self.assertEqual(status["used_today"], 1)
        self.assertEqual(status["legacy_uncertain_today"], 0)
        self.assertEqual(len(self.store.recent()), 1)

    def test_missing_quota_read_does_not_create_files(self):
        self.assertEqual(self.store.quota_status(BINDING, now=int(NOW))["remaining_today"], 3)
        self.assertFalse(self.store.path.exists())

    def test_actual_connector_send_path_enforces_quota_before_fourth_post_and_exempts_replies(self):
        from test_bilibili_connector import BilibiliConnectorTests
        fixture = BilibiliConnectorTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for n in range(3):
            with patch("src.bilibili_connector.time.time", return_value=NOW + n * 7201):
                fixture.send(dry_run=False, delivery_key=f"video-share-v1:BV{n:010d}")
        with patch("src.bilibili_connector.time.time", return_value=NOW + 3 * 7201):
            with self.assertRaises(BilibiliShareLimit):
                fixture.send(dry_run=False, delivery_key="video-share-v1:BV9999999999")
            self.assertEqual(sum(r.method == "POST" for r in fixture.requests), 3)
            fixture.send(dry_run=False, delivery_key="owner-reply")
        self.assertEqual(sum(r.method == "POST" for r in fixture.requests), 4)


class AutoBrowseTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = AutoBrowseStore(self.root / "private", "a" * 64)
        self.policy = BrowsePolicy()
        self.now = NOW
        self.rng = MinimumRandom()

    def clock(self):
        return self.now

    def run_once(self, execute=None, **kwargs):
        return run_loop(self.store, self.policy, execute or MagicMock(return_value={"status": "ok", "usage": []}),
                        once=True, clock=self.clock, rng=self.rng, **kwargs)

    def test_default_bounds_and_invalid_config_fail_without_network(self):
        self.assertEqual(self.policy.max_rounds_per_day, 6)
        self.assertEqual(self.policy.max_selected, 1)
        self.assertEqual((self.policy.min_interval_minutes, self.policy.max_interval_minutes), (90, 180))
        for changes in ({"min_interval_minutes": 0}, {"max_selected": 3}, {"per_source": 10}, {"max_rounds_per_day": True}):
            with self.assertRaises(ValueError):
                BrowsePolicy(**changes).validate()

    def test_first_due_round_runs_and_next_restart_does_not_replay(self):
        execute = MagicMock(return_value={"status": "ok", "usage": [{"total_tokens": 123}], "seen_bvids": [BV]})
        self.run_once(execute, send=True)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(self.store.seen(self.now), {BV})
        self.assertEqual(self.store.today(self.now)["known_tokens"], 123)
        result = self.run_once(execute, send=True)
        self.assertEqual(result["status"], "waiting")
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(self.store.state()["next_due"], NOW + 90 * 60)

    def test_quiet_hours_do_not_browse_or_share(self):
        self.now = datetime(2026, 10, 22, 17, 0, tzinfo=timezone.utc).timestamp()  # Next day 01:00.
        execute = MagicMock()
        result = self.run_once(execute, send=True)
        self.assertEqual(result["status"], "waiting")
        self.assertEqual(datetime.fromtimestamp(result["next_due"], timezone(timedelta(hours=8))).hour, 9)
        execute.assert_not_called()

    def test_cross_midnight_quiet_window_and_disabled_quiet_hours(self):
        policy = BrowsePolicy(quiet_start_hour=23, quiet_end_hour=9)
        late = datetime(2026, 10, 22, 15, 30, tzinfo=timezone.utc).timestamp()
        self.assertTrue(policy.quiet(late))
        self.assertFalse(policy.quiet(NOW))
        self.assertFalse(BrowsePolicy(quiet_start_hour=0, quiet_end_hour=0).quiet(late))

    def test_daily_round_budget_reserves_before_expensive_work_and_survives_crash(self):
        for n in range(6):
            self.assertIsNotNone(self.store.begin_round(NOW + n, self.policy, NOW + 10000))
        self.assertIsNone(self.store.begin_round(NOW + 10, self.policy, NOW + 10000))
        self.assertEqual(self.store.today(NOW)["rounds"], 6)
        self.assertEqual(self.store.today(NOW)["unfinished_rounds"], 6)
        self.assertEqual(self.store.today(NOW)["unknown_usage"], 6)
        self.assertIsNotNone(self.store.begin_round(NOW + 86400, self.policy, NOW + 90000))

    def test_daily_limit_schedules_tomorrow_without_catchup(self):
        for _ in range(6):
            self.store.begin_round(NOW, self.policy, NOW)
        execute = MagicMock()
        result = self.run_once(execute)
        self.assertEqual(result["status"], "daily_round_limit")
        self.assertGreater(result["next_due"], NOW + 12 * 3600)
        execute.assert_not_called()

    def test_seen_selection_advances_refresh_index_and_expires_after_seven_days(self):
        execute = MagicMock(return_value={"status": "ok", "seen_bvids": [BV], "usage": []})
        self.run_once(execute)
        self.now = self.store.state()["next_due"]
        self.run_once(execute)
        self.assertEqual(execute.call_args.args[:2], (2, {BV}))
        self.assertEqual(self.store.seen(self.now + 8 * 86400), set())

    def test_failure_backs_off_and_does_not_retry_in_same_round_or_call_it_free(self):
        execute = MagicMock(side_effect=RuntimeError("PRIVATE_ERROR_DETAILS"))
        result = self.run_once(execute)
        self.assertEqual(result["status"], "error")
        self.assertGreaterEqual(result["next_due"], NOW + 240 * 60)
        self.assertEqual(self.store.today(NOW)["unknown_usage"], 1)
        self.assertNotIn("PRIVATE_ERROR_DETAILS", json.dumps(self.store.state()))
        execute.assert_called_once()

    def test_store_and_status_read_only_when_absent(self):
        self.assertEqual(self.store.state(), {})
        self.assertFalse(self.store.is_running())
        self.assertEqual(self.store.today(NOW)["rounds"], 0)
        self.assertEqual(self.store.seen(NOW), set())
        self.assertFalse(self.store.home.exists())

    def test_process_lock_blocks_second_worker_and_stop_is_scoped_to_running_session(self):
        self.store.update_state(run_id="a" * 32)
        with profile_lock(self.store.lock_path):
            self.assertTrue(self.store.is_running())
            with self.assertRaises(BilibiliConnectorError):
                self.run_once()
            self.assertEqual(self.store.request_stop()["status"], "stop_requested")
            self.assertTrue(self.store.should_stop("a" * 32))
            self.assertFalse(self.store.should_stop("b" * 32))
        self.assertFalse(self.store.is_running())

    def test_cooperative_stop_exits_loop_without_extra_round(self):
        execute = MagicMock(return_value={"status": "ok", "usage": []})
        def sleep(_):
            self.store.request_stop()
        result = run_loop(self.store, self.policy, execute, clock=self.clock, sleep=sleep, rng=self.rng)
        self.assertEqual(result["status"], "stopped")
        execute.assert_called_once()
        self.assertEqual(self.store.state()["phase"], "stopped")
        self.assertFalse(self.store.is_running())

    def test_cli_help_and_status_outside_repo_do_not_start_browser_or_chat_model(self):
        script = Path(__file__).resolve().parents[1] / "scripts/bilibili_autobrowse.py"
        environment = {**os.environ, "AIKE_BILIBILI_HOME": str(self.root / "unused")}
        for args in (["--help"], ["status"], ["stop"]):
            result = subprocess.run([sys.executable, str(script), *args], cwd=tempfile.gettempdir(),
                                    env=environment, capture_output=True)
            self.assertEqual(result.returncode, 0)
        self.assertFalse((self.root / "unused").exists())

    def browser_fixture(self):
        from test_bilibili_browse import BrowseTests, FakeModel
        from src.bilibili_connector import BindingStore, PrivateMessageResult
        from src.bilibili_daily_note import BilibiliDailyNoteStore
        from src.bilibili_history import HistoryScope
        fixture = BrowseTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        BindingStore(self.store.home / "binding.json").save(BINDING)
        fixture.account.send_private_message = MagicMock(return_value=PrivateMessageResult(True, False, 200, 0, "", "synthetic-request"))
        model = FakeModel()
        model.close = MagicMock()
        diary = BilibiliDailyNoteStore(self.store.home / "daily-note.sqlite3")
        journal = NS(update=lambda data: diary.update(HistoryScope(self.store.scope), data))
        return fixture, model, diary, journal

    def execute_fixture(self, *, send=True, stop=False, quota=False):
        fixture, model, diary, journal = self.browser_fixture()
        history = MagicMock()
        history.record_share.return_value = {"status": "saved"}
        browser_context = MagicMock()
        browser_context.__enter__.return_value = fixture.browser
        if quota:
            fixture.account.send_private_message.side_effect = BilibiliShareLimit("daily_limit")
        stop_checks = iter((False, False, stop))
        with patch("src.bilibili_browser.PersistentBrowser") as manager_class, \
             patch("src.bilibili_persona.persona_settings", return_value=("role", NS(), False)), \
             patch("src.bilibili_persona.PersonaModel", return_value=model), \
             patch("src.bilibili_memory.load_owner_memory"), \
             patch("src.bilibili_history_bridge.BilibiliHistoryWriter", return_value=history), \
             patch("src.bilibili_daily_note.BilibiliDailyNoteWriter", return_value=journal), \
             patch("src.bilibili_browser_browse.browser_browse_client", return_value=browser_context) as browse_client, \
             patch("src.bilibili_browse.save_report", return_value=(Path("fixture.json"), Path("fixture.md"))), \
             patch("src.bilibili_autobrowse.time.time", return_value=NOW):
            result = execute_browser_round(BINDING, NS(), self.policy, send=send, refresh_index=2,
                seen_bvids=set(), should_stop=lambda: next(stop_checks), home=self.store.home)
        manager_class.assert_called_once_with(BINDING, home=self.store.home)
        manager_class.return_value.open.assert_called_once_with(wait_for_controller=True)
        browse_client.assert_called_once_with(None, BINDING, manager=manager_class.return_value, short_locks=True)
        model.close.assert_called_once()
        self.assertEqual(len(result["usage"]), 2)
        self.assertEqual(diary.read_today(HistoryScope(self.store.scope))["verified_videos"], 1)
        return result, fixture, history

    def test_real_round_pipeline_browses_journals_and_submits_only_natural_share_and_link(self):
        result, fixture, history = self.execute_fixture()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["delivery_status"], "sent")
        fixture.account.send_private_message.assert_called_once()
        self.assertIn("觉得这段讲解挺有意思\nhttps://www.bilibili.com/video/", fixture.account.send_private_message.call_args.args[1])
        history.record_share.assert_called_once()

    def test_daily_share_limit_keeps_browsing_and_updating_journal(self):
        result, fixture, history = self.execute_fixture(quota=True)
        self.assertEqual(result["delivery_status"], "daily_limit")
        self.assertEqual(result["status"], "ok")
        history.record_share.assert_not_called()

    def test_preview_only_and_stop_request_do_not_submit_private_message(self):
        for send, stop in ((False, False), (True, True)):
            result, fixture, history = self.execute_fixture(send=send, stop=stop)
            fixture.account.send_private_message.assert_not_called()
            history.record_share.assert_not_called()
            self.assertIn(result["delivery_status"], {"disabled", "cancelled"})

    def test_changed_binding_blocks_before_model_or_browser(self):
        from src.bilibili_connector import BindingStore
        BindingStore(self.store.home / "binding.json").save(BilibiliBinding("other", "other", "101", "303"))
        with self.assertRaises(BilibiliConnectorError):
            execute_browser_round(BINDING, NS(), self.policy, send=True, refresh_index=1,
                                  seen_bvids=set(), should_stop=lambda: False, home=self.store.home)

    def test_browser_open_failure_backs_off_without_memory_model_or_browsing(self):
        from src.bilibili_connector import BindingStore
        BindingStore(self.store.home / "binding.json").save(BINDING)
        with patch("src.bilibili_browser.PersistentBrowser") as manager_class, \
             patch("src.bilibili_memory.load_owner_memory") as memory, \
             patch("src.bilibili_persona.PersonaModel") as model, \
             patch("src.bilibili_browser_browse.browser_browse_client") as browse:
            manager_class.return_value.open.side_effect = BilibiliConnectorError("PRIVATE_BROWSER_ERROR")
            result = self.run_once(lambda fresh, seen, stop: execute_browser_round(
                BINDING, NS(), self.policy, send=True, refresh_index=fresh,
                seen_bvids=seen, should_stop=stop, home=self.store.home))
        self.assertEqual(result["status"], "error")
        self.assertGreaterEqual(result["next_due"], NOW + 240 * 60)
        manager_class.return_value.open.assert_called_once_with(wait_for_controller=True)
        memory.assert_not_called()
        model.assert_not_called()
        browse.assert_not_called()
        self.assertEqual(self.store.today(NOW)["model_calls"], 0)
        self.assertNotIn("PRIVATE_BROWSER_ERROR", json.dumps(self.store.state()))

    def test_stop_before_round_does_not_reopen_browser(self):
        from src.bilibili_connector import BindingStore
        BindingStore(self.store.home / "binding.json").save(BINDING)
        with patch("src.bilibili_browser.PersistentBrowser") as manager_class:
            result = execute_browser_round(BINDING, NS(), self.policy, send=True, refresh_index=1,
                seen_bvids=set(), should_stop=lambda: True, home=self.store.home)
        self.assertEqual(result["status"], "cancelled")
        manager_class.assert_not_called()

    def test_stop_during_browser_open_does_not_read_memory_or_browse(self):
        from src.bilibili_connector import BindingStore
        BindingStore(self.store.home / "binding.json").save(BINDING)
        stopping = False
        def opened(**_):
            nonlocal stopping
            stopping = True
        with patch("src.bilibili_browser.PersistentBrowser") as manager_class, \
             patch("src.bilibili_memory.load_owner_memory") as memory, \
             patch("src.bilibili_persona.PersonaModel") as model, \
             patch("src.bilibili_browser_browse.browser_browse_client") as browse:
            manager_class.return_value.open.side_effect = opened
            result = execute_browser_round(BINDING, NS(), self.policy, send=True, refresh_index=1,
                seen_bvids=set(), should_stop=lambda: stopping, home=self.store.home)
        self.assertEqual(result["status"], "cancelled")
        manager_class.return_value.open.assert_called_once_with(wait_for_controller=True)
        memory.assert_not_called()
        model.assert_not_called()
        browse.assert_not_called()

    def test_reopened_browser_still_rejects_unverified_account_before_video_work(self):
        from src.bilibili_connector import BindingStore
        BindingStore(self.store.home / "binding.json").save(BINDING)
        browser_context = MagicMock()
        browser_context.__enter__.side_effect = BilibiliConnectorError("login_required")
        with patch("src.bilibili_browser.PersistentBrowser") as manager_class, \
             patch("src.bilibili_persona.persona_settings", return_value=("role", NS(), False)), \
             patch("src.bilibili_persona.PersonaModel") as model, \
             patch("src.bilibili_memory.load_owner_memory"), \
             patch("src.bilibili_history_bridge.BilibiliHistoryWriter"), \
             patch("src.bilibili_daily_note.BilibiliDailyNoteWriter"), \
             patch("src.bilibili_browser_browse.browser_browse_client", return_value=browser_context), \
             patch("src.bilibili_browse.preview") as browse, \
             patch("src.bilibili_share.share_one") as share:
            result = execute_browser_round(BINDING, NS(), self.policy, send=True, refresh_index=1,
                seen_bvids=set(), should_stop=lambda: False, home=self.store.home)
        self.assertEqual(result["status"], "error")
        manager_class.return_value.open.assert_called_once_with(wait_for_controller=True)
        browse.assert_not_called()
        share.assert_not_called()
        model.return_value.close.assert_called_once_with()

    def test_refresh_parameter_and_seen_filter_prevent_repeated_model_work(self):
        from test_bilibili_browse import BrowseTests, FakeModel, BV1, BV2
        fixture = BrowseTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        model = FakeModel()
        result = preview(fixture.browser, BINDING, model, refresh_index=7, seen_bvids={BV1, BV2})
        self.assertEqual(result["candidates"], [])
        self.assertEqual(model.usage, [])
        requests = [r for r in fixture.requests if r.url.path.endswith("/rcmd")]
        self.assertEqual(requests[0].url.params["fresh_idx"], "7")

    def test_worker_lifecycle_can_be_controlled_from_separate_cli_process_without_live_services(self):
        import time
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts/bilibili_autobrowse.py"
        environment = {**os.environ, "AIKE_BILIBILI_HOME": str(self.store.home)}
        code = (
            "from pathlib import Path; import os; "
            "from src.bilibili_autobrowse import AutoBrowseStore,BrowsePolicy,run_loop; "
            f"store=AutoBrowseStore(Path(os.environ['AIKE_BILIBILI_HOME']),{'a' * 64!r}); "
            f"run_loop(store,BrowsePolicy(),lambda *args:dict(status='ok',usage=[]),clock=lambda:{NOW!r})"
        )
        process = subprocess.Popen([sys.executable, "-u", "-c", code], cwd=root, env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            deadline = time.monotonic() + 10
            while not self.store.session_path.is_file() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            status = subprocess.run([sys.executable, str(script), "status"], cwd=root, env=environment, capture_output=True)
            self.assertEqual(status.returncode, 0)
            self.assertTrue(json.loads(status.stdout.splitlines()[0])["running"])
            stop = subprocess.run([sys.executable, str(script), "stop"], cwd=root, env=environment, capture_output=True)
            self.assertEqual(json.loads(stop.stdout)["status"], "stop_requested")
            _, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertFalse(self.store.is_running())
            self.assertEqual(self.store.state()["phase"], "stopped")
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
