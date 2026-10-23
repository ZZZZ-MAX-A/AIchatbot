from __future__ import annotations

import base64
import importlib.util
import io
import json
from contextlib import redirect_stderr
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import httpx

from src.bilibili_browser import MAX_BYTES, PersistentBrowser
from src.bilibili_browser_probe import (
    NativeEvidence, RequestPolicy, capture_player, endpoint, normalized_video, probe, response_bytes,
)
from src.bilibili_connector import BilibiliBinding, BilibiliConnectorError
from src.bilibili_diagnostics import DiagnosticLog

BV = "BV1xx411c7mD"
BINDING = BilibiliBinding("aike", "aike", "12345678901", "23456789012")
PLAYER_URL = "https://api.bilibili.com/x/player/wbi/v2?bvid=" + BV + "&cid=345&w_rid=synthetic-signature"
VIDEO = {"bvid": BV, "aid": 123, "title": "synthetic-title", "total_pages": 1,
         "selected_page": {"page": 1, "cid": 345, "duration": 90, "part": "part"}}


class BrowserProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.log = DiagnosticLog(self.home / "logs")

    def test_endpoint_allows_only_expected_https_hosts_and_paths(self):
        self.assertEqual(endpoint(PLAYER_URL), "player")
        self.assertEqual(endpoint("https://www.bilibili.com/video/" + BV), "detail")
        for url in ("http://api.bilibili.com/x/player/wbi/v2", "https://fake.test/x/player/wbi/v2",
                    "https://api.bilibili.com/x/player/v2"):
            self.assertEqual(endpoint(url), "other")

    def test_policy_blocks_writes_media_history_and_old_endpoint(self):
        policy = RequestPolicy(BV)
        for method, url, kind in (
            ("POST", "https://api.bilibili.com/x/relation/modify", "XHR"),
            ("DELETE", "https://api.bilibili.com/anything", "Fetch"),
            ("GET", "https://cdn.test/resource", "Media"),
            ("GET", "https://cn.test.bilivideo.com/segment", "XHR"),
            ("GET", "https://cdn.test/video.m4s?key=private", "Fetch"),
            ("GET", "https://api.bilibili.com/x/player/playurl", "XHR"),
            ("GET", "https://api.bilibili.com/x/v2/history/report", "XHR"),
            ("GET", "https://api.bilibili.com/x/click-interface/web/heartbeat", "XHR"),
            ("GET", "https://api.bilibili.com/x/player/v2", "XHR"),
        ):
            with self.subTest(method=method, kind=kind):
                self.assertFalse(policy.allow({"method": method, "url": url}, kind))
        self.assertEqual(policy.player_requests, 0)
        self.assertEqual(policy.blocked, 9)
        self.assertTrue(policy.allow({"method": "GET", "url": "https://s1.hdslb.com/player.js"}, "Script"))

    def test_policy_allows_one_matching_player_get_and_blocks_retry(self):
        policy = RequestPolicy(BV)
        self.assertFalse(policy.allow({"method": "GET", "url": PLAYER_URL.replace(BV, "BV2xx411c7mD")}, "XHR"))
        self.assertTrue(policy.allow({"method": "GET", "url": PLAYER_URL}, "XHR"))
        self.assertFalse(policy.allow({"method": "GET", "url": PLAYER_URL}, "XHR"))
        self.assertEqual(policy.player_requests, 1)

    def test_response_body_bounds_and_encoding(self):
        self.assertEqual(response_bytes({"body": "fixture"}), b"fixture")
        self.assertEqual(response_bytes({"body": base64.b64encode(b"fixture").decode(), "base64Encoded": True}), b"fixture")
        for data in ({"body": []}, {"body": "!broken", "base64Encoded": True}, {"body": "x" * (MAX_BYTES + 1)}):
            with self.subTest(kind=type(data["body"]).__name__), self.assertRaises(BilibiliConnectorError):
                response_bytes(data)

    def test_normalize_validates_selected_page_and_sanitizes_metadata(self):
        video = normalized_video(VIDEO, BV, 1)
        self.assertEqual(video["pages"], [{"page": 1, "cid": 345, "duration": 90, "title": "part"}])
        self.assertNotIn("selected_page", video)
        for data in (None, [], {**VIDEO, "bvid": "wrong"}, {**VIDEO, "selected_page": None},
                     {**VIDEO, "selected_page": {"page": 2, "cid": 345, "duration": 90}}):
            with self.subTest(kind=type(data).__name__), self.assertRaises(BilibiliConnectorError):
                normalized_video(data, BV, 1)

    def capture(self, *, status=200, payload=None, raw=None, metadata=VIDEO):
        self.browser = MagicMock()
        self.browser.events = []
        self.commands = []
        def event(method, params):
            return {"sessionId": "session", "method": method, "params": params}
        def send(*args, **kwargs):
            self.commands.append((args, kwargs))
            self.browser.events.append(event("Fetch.requestPaused", {
                "requestId": "fetch-doc", "request": {"method": "GET", "url": "https://www.bilibili.com/video/" + BV},
                "resourceType": "Document"}))
        def call(method, params=None, session=None, **kwargs):
            self.commands.append(((method, params, session), kwargs))
            if method == "Target.createTarget":
                return {"targetId": "tab"}
            if method == "Target.attachToTarget":
                return {"sessionId": "session"}
            if method == "Fetch.continueRequest":
                if params["requestId"] == "fetch-doc":
                    self.browser.events += [
                        event("Network.responseReceived", {"requestId": "doc", "type": "Document", "response": {
                            "status": 200, "url": "https://www.bilibili.com/video/" + BV}}),
                        event("Fetch.requestPaused", {"requestId": "fetch-player", "resourceType": "XHR",
                              "request": {"method": "GET", "url": PLAYER_URL}}),
                    ]
                else:
                    self.browser.events += [
                        event("Network.responseReceived", {"requestId": "player", "response": {
                            "status": status, "url": PLAYER_URL, "headers": {"content-type": "application/json"}}}),
                        event("Network.loadingFinished", {"requestId": "player"}),
                    ]
            if method == "Network.getResponseBody":
                return {"body": raw if raw is not None else json.dumps(payload if payload is not None else {
                    "code": 0, "data": {"bvid": BV, "aid": 123, "cid": 345}})}
            if method == "Runtime.evaluate":
                return {"result": {"value": json.dumps(metadata)}}
            return {}
        self.browser.call.side_effect = call
        self.browser.send_command.side_effect = send
        self.browser.receive.return_value = None
        return capture_player(self.browser, BV, 1, self.log)

    def test_capture_intercepts_before_async_navigation_and_uses_native_response(self):
        result = self.capture()
        self.assertEqual(result["reason"], "captured")
        self.assertEqual(result["native_player_requests"], 1)
        self.assertEqual(result["video"]["bvid"], BV)
        names = [args[0] for args, kwargs in self.commands]
        self.assertLess(names.index("Fetch.enable"), names.index("Page.navigate"))
        self.assertEqual(names[-1], "Target.closeTarget")
        self.browser.send_command.assert_called_once()
        self.assertFalse(any("Cookie" in name or "BrowserContext" in name for name in names))

    def test_capture_classifies_412_and_never_evaluates_metadata_or_retries(self):
        result = self.capture(status=412, payload={"code": -412, "message": "synthetic-private"})
        self.assertEqual(result["reason"], "player_http_rejected")
        self.assertNotIn("player", result)
        self.assertNotIn("Runtime.evaluate", [args[0] for args, kwargs in self.commands])
        log = self.log.path.read_text(encoding="utf-8")
        for forbidden in ("synthetic-private", "synthetic-signature", PLAYER_URL):
            self.assertNotIn(forbidden, log)

    def test_capture_rejects_invalid_or_failed_business_responses_and_metadata(self):
        for kwargs, reason in (
            ({"raw": "<html>blocked</html>"}, "player_invalid_json"),
            ({"payload": []}, "player_invalid_structure"),
            ({"payload": {"code": -352}}, "player_business_error"),
            ({"metadata": None}, "page_identity_invalid"),
            ({"metadata": {**VIDEO, "bvid": "wrong"}}, "page_identity_invalid"),
        ):
            with self.subTest(reason=reason):
                self.assertEqual(self.capture(**kwargs)["reason"], reason)
                self.assertEqual(self.commands[-1][0][0], "Target.closeTarget")

    def native(self, captured, entries):
        self.requests = []
        def respond(request):
            self.requests.append(request)
            self.assertNotIn("cookie", request.headers)
            return httpx.Response(200, json={"body": entries})
        client = httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(client.close)
        with patch("src.bilibili_browser_probe.httpx.Client", return_value=client):
            return NativeEvidence(captured, self.log)

    def test_native_evidence_reuses_identity_cdn_and_full_track_validation(self):
        captured = {"bvid": BV, "aid": 123, "cid": 345, "subtitle": {"subtitles": [
            {"lan": "ai-zh", "ai_type": 1, "subtitle_url": "https://aisubtitle.hdslb.com/fixture?auth_key=synthetic"}]}}
        source = self.native(captured, [{"from": 0, "to": 5, "content": "synthetic caption"}])
        result = source.evidence(normalized_video(VIDEO, BV, 1), max_pages=1)
        self.assertEqual(result["pages"][0]["status"], "available")
        self.assertEqual(len(result["segments"]), 1)
        self.assertTrue(result["pages"][0]["identity_verified"])
        self.assertNotIn("auth_key", json.dumps(result))
        self.assertEqual(len(self.requests), 1)

    def test_native_identity_mismatch_blocks_cdn_and_produces_no_evidence(self):
        source = self.native({"bvid": BV, "aid": 123, "cid": 999}, [])
        result = source.evidence(normalized_video(VIDEO, BV, 1), max_pages=1)
        self.assertEqual(result["pages"][0]["status"], "error")
        self.assertEqual(result["segments"], [])
        self.assertEqual(self.requests, [])

    def test_native_invalid_timeline_discards_entire_track(self):
        source = self.native({"bvid": BV, "aid": 123, "cid": 345, "subtitle": {"subtitles": [
            {"lan": "zh", "subtitle_url": "https://aisubtitle.hdslb.com/fixture"}]}},
            [{"from": 0, "to": 5, "content": "valid-prefix"}, {"from": 6, "to": 999, "content": "invalid"}])
        result = source.evidence(normalized_video(VIDEO, BV, 1), max_pages=1)
        self.assertEqual(result["pages"][0]["status"], "error")
        self.assertEqual(result["segments"], [])
        self.assertEqual(result["characters"], 0)

    def test_probe_binding_failure_prevents_video_navigation_and_saves_safe_report(self):
        manager = PersistentBrowser(BINDING, home=self.home)
        with patch("src.bilibili_browser_probe.BrowserCDP") as cdp, \
             patch("src.bilibili_browser_probe.capture_player") as capture:
            cdp.return_value.__enter__.return_value.account_response.return_value = (200, {}, json.dumps({
                "code": 0, "data": {"isLogin": True, "mid": BINDING.owner_mid, "uname": "synthetic-private"}}).encode())
            result = probe(manager, BV)
        self.assertEqual(result["reason"], "account_mismatch")
        capture.assert_not_called()
        saved = Path(result["report_path"]).read_text(encoding="utf-8")
        for forbidden in (BINDING.aike_mid, BINDING.owner_mid, "synthetic-private"):
            self.assertNotIn(forbidden, saved)
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["messages_sent"], 0)

    def test_successful_probe_keeps_captions_private_and_does_not_allow_sharing(self):
        manager = PersistentBrowser(BINDING, home=self.home)
        client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
            "body": [{"from": 1, "to": 2, "content": "synthetic-private-caption"}]})))
        self.addCleanup(client.close)
        captured = {"reason": "captured", "video": normalized_video(VIDEO, BV, 1),
                    "player": {"bvid": BV, "aid": 123, "cid": 345, "subtitle": {"subtitles": [
                        {"lan": "zh", "subtitle_url": "https://aisubtitle.hdslb.com/fixture?auth_key=synthetic"}]}}}
        with patch("src.bilibili_browser_probe.BrowserCDP") as cdp, \
             patch("src.bilibili_browser_probe.capture_player", return_value=captured) as capture, \
             patch("src.bilibili_browser_probe.httpx.Client", return_value=client):
            cdp.return_value.__enter__.return_value.account_response.return_value = (200, {}, json.dumps({
                "code": 0, "data": {"isLogin": True, "mid": BINDING.aike_mid}}).encode())
            result = probe(manager, BV)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["segments"], 1)
        self.assertFalse(result["content_reviewed"])
        self.assertFalse(result["share_eligible"])
        self.assertNotIn("synthetic-private-caption", json.dumps(result))
        saved = Path(result["report_path"]).read_text(encoding="utf-8")
        self.assertIn("synthetic-private-caption", saved)
        self.assertNotIn("auth_key", saved)
        capture.assert_called_once()

    def test_invalid_probe_arguments_rejected_before_touching_browser(self):
        manager = PersistentBrowser(BINDING, home=self.home)
        for bvid, page in (("invalid", 1), (BV, 0), (BV, True), (BV, 1001)):
            with patch("src.bilibili_browser_probe.BrowserCDP") as cdp, self.assertRaises(BilibiliConnectorError):
                probe(manager, bvid, page=page)
            cdp.assert_not_called()

    def test_cli_requires_bvid_before_loading_binding(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("probe_cli", root / "scripts/bilibili_browser.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        with patch.object(cli, "BindingStore") as bindings, redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["subtitle-check"])
        bindings.assert_not_called()


if __name__ == "__main__":
    unittest.main()
