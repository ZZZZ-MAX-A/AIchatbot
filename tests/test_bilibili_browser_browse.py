from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.bilibili_browser import PersistentBrowser, profile_lock
from src.bilibili_browser_browse import BrowserBrowseClient, browser_browse_client
from src.bilibili_connector import BilibiliBinding, BilibiliConnectorError
from src.bilibili_diagnostics import DiagnosticLog

BV = "BV1xx411c7mD"
BINDING = BilibiliBinding("aike", "aike", "101", "202")
VIDEO = {"bvid": BV, "aid": 123, "pages": [{"page": 1, "cid": 345, "duration": 90}]}


class BrowserBrowseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.log = DiagnosticLog(self.home / "logs")
        self.account = MagicMock()
        self.browser = MagicMock()
        self.client = BrowserBrowseClient(self.account, self.browser, diagnostics=self.log)
        self.addCleanup(self.client.close)
        self.captured = {"reason": "captured", "video": copy.deepcopy(VIDEO),
                         "player": {"bvid": BV, "aid": 123, "cid": 345}}

    def test_player_uses_native_capture_and_keeps_candidate_api_unused(self):
        with patch("src.bilibili_browser_browse.capture_player", return_value=self.captured) as capture:
            result = self.client.player(VIDEO, VIDEO["pages"][0])
        self.assertEqual(result["cid"], 345)
        capture.assert_called_once_with(self.browser, BV, 1, self.log)
        self.account._client.get.assert_not_called()
        self.assertEqual(self.client.subtitle_transport, "persistent_browser_native")

    def test_native_failure_has_no_interface_fallback(self):
        with patch("src.bilibili_browser_browse.capture_player", return_value={"reason": "player_http_rejected"}), \
             self.assertRaises(BilibiliConnectorError):
            self.client.player(VIDEO, VIDEO["pages"][0])
        self.account._client.get.assert_not_called()

    def test_both_web_metadata_and_native_player_must_match_candidate(self):
        cases = [
            ("video", "aid", 999), ("video", "bvid", "BV2xx411c7mD"),
            ("player", "aid", 999), ("player", "cid", 999),
            ("page", "duration", 999), ("page", "page", 2), ("page", "cid", 999),
        ]
        for section, key, value in cases:
            captured = copy.deepcopy(self.captured)
            target = captured["video"]["pages"][0] if section == "page" else captured[section]
            target[key] = value
            with self.subTest(section=section, key=key), \
                 patch("src.bilibili_browser_browse.capture_player", return_value=captured), \
                 self.assertRaises(BilibiliConnectorError):
                self.client.player(VIDEO, VIDEO["pages"][0])

    def test_binding_mismatch_prevents_preview_and_releases_controller(self):
        manager = PersistentBrowser(BINDING, home=self.home)
        with patch("src.bilibili_browser_browse.BrowserCDP") as cdp:
            cdp.return_value.__enter__.return_value.account_response.return_value = (
                200, {}, json.dumps({"code": 0, "data": {"isLogin": True, "mid": 999}}).encode())
            with self.assertRaises(BilibiliConnectorError):
                with browser_browse_client(self.account, BINDING, manager=manager):
                    self.fail("wrong account reached preview")
        self.assertEqual(json.loads(manager.state.read_text())["status"], "account_mismatch")
        self.assertTrue(cdp.return_value.__exit__.called)

    def test_context_uses_existing_profile_and_closes_only_connection(self):
        manager = PersistentBrowser(BINDING, home=self.home)
        with patch("src.bilibili_browser_browse.BrowserCDP") as cdp:
            cdp.return_value.__enter__.return_value.account_response.return_value = (
                200, {}, json.dumps({"code": 0, "data": {"isLogin": True, "mid": 101}}).encode())
            with browser_browse_client(self.account, BINDING, manager=manager) as client:
                self.assertIs(client.browser, cdp.return_value.__enter__.return_value)
        cdp.assert_called_once_with(manager.profile)
        self.assertEqual(json.loads(manager.state.read_text())["status"], "logged_in")
        self.assertEqual(cdp.return_value.__enter__.return_value.call.call_count, 0)

    def test_short_lock_session_releases_controller_while_caller_generates_reply(self):
        manager = PersistentBrowser(BINDING, home=self.home)
        with patch("src.bilibili_browser_browse.BrowserCDP") as cdp:
            cdp.return_value.__enter__.return_value.account_response.return_value = (
                200, {}, json.dumps({"code": 0, "data": {"isLogin": True, "mid": 101}}).encode())
            with browser_browse_client(self.account, BINDING, manager=manager, short_locks=True) as client:
                with profile_lock(manager.lock):
                    self.assertEqual(client.lock, manager.lock)


if __name__ == "__main__":
    unittest.main()
