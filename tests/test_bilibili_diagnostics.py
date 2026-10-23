from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

from src.bilibili_browse import _bounded_json, BrowseClient, diagnose
from src.bilibili_connector import BilibiliBinding, BilibiliClient, BilibiliCredentials, BilibiliConnectorError
from src.bilibili_diagnostics import DiagnosticLog

BV = "BV1xx411c7mD"
BINDING = BilibiliBinding("aike", "aike", "101", "202")


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.log = DiagnosticLog(Path(self.directory.name))

    def rows(self):
        return [json.loads(line) for line in self.log.path.read_text(encoding="utf-8").splitlines()]

    def test_error_response_records_fixed_signals_not_body_headers_or_values(self):
        secret = "synthetic-private-value"
        response = httpx.Response(412, headers={"content-type": "text/html", "set-cookie": secret,
                                               "location": "https://private.test/?secret=" + secret},
                                  text="<html>请求被拒绝，风控。" + secret + "</html>")
        with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
            with self.assertRaises(BilibiliConnectorError):
                _bounded_json(client, "https://api.bilibili.com/x/player/wbi/v2", diagnostics=self.log,
                              stage="player", headers={"cookie": secret}, params={"w_rid": secret, "bvid": BV})
        row = self.rows()[0]
        self.assertEqual(row["http_status"], 412)
        self.assertEqual(row["body_kind"], "html")
        self.assertEqual(row["body_signals"], ["请求被拒绝", "风控"])
        self.assertTrue(row["signed"])
        content = self.log.path.read_text(encoding="utf-8")
        for forbidden in (secret, BV, "cookie", "https://", "<html>"):
            self.assertNotIn(forbidden, content)

    def test_untrusted_fields_and_invalid_numeric_values_are_dropped(self):
        self.log.record("check", "player", check="player_identity", ok=False, token="private",
                        error_kind="private", elapsed_ms=float("nan"), http_status=True,
                        parameter_names=["bvid", "private", {}], body_signals=["风控", "private"])
        row = self.rows()[0]
        for key in ("token", "error_kind", "elapsed_ms", "http_status"):
            self.assertNotIn(key, row)
        self.assertEqual(row["parameter_names"], ["bvid"])
        self.assertEqual(row["body_signals"], ["风控"])

    def test_http_error_body_read_is_capped_and_hash_marks_prefix(self):
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(412, content=b"x" * 80000))) as client:
            with self.assertRaises(BilibiliConnectorError):
                _bounded_json(client, "https://api.bilibili.com/", diagnostics=self.log)
        self.assertEqual(self.rows()[0]["body_bytes"], 65536)
        self.assertTrue(self.rows()[0]["truncated"])

    def test_malformed_json_and_transport_errors_are_distinct_without_exception_text(self):
        def fail(request):
            raise httpx.ConnectError("private-network-error")
        for handler in (lambda r: httpx.Response(200, content=b"not-json"), fail):
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                with self.assertRaises(BilibiliConnectorError):
                    _bounded_json(client, "https://api.bilibili.com/", diagnostics=self.log)
        rows = self.rows()
        self.assertIn("invalid_json", [r.get("outcome") for r in rows])
        self.assertEqual(rows[-1]["error_kind"], "connect")
        self.assertNotIn("private-network-error", self.log.path.read_text(encoding="utf-8"))

    def test_log_failure_preserves_original_http_error(self):
        obstacle = Path(self.directory.name) / "file"
        obstacle.write_text("fixture", encoding="utf-8")
        self.log = DiagnosticLog(obstacle)
        with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(412))) as client:
            with self.assertRaisesRegex(BilibiliConnectorError, "HTTP 412"):
                _bounded_json(client, "https://api.bilibili.com/", diagnostics=self.log)
        self.assertEqual(self.log.write_failures, 1)

    def test_size_and_retention_bound_only_own_log_files(self):
        directory = Path(self.directory.name)
        unrelated = directory / "unrelated.jsonl"
        unrelated.write_text("keep", encoding="utf-8")
        for _ in range(23):
            log = DiagnosticLog(directory)
            log.record("run_start", "runtime")
        self.assertEqual(len(list(directory.glob("browse-*.jsonl"))), 20)
        self.assertEqual(unrelated.read_text(), "keep")
        tiny = DiagnosticLog(directory, max_bytes=1)
        tiny.record("run_start", "runtime")
        self.assertFalse(tiny.path.exists())
        self.assertEqual(tiny.write_failures, 1)

    def browser(self, *, blocked=True, mid=101, business_code=0):
        self.requests = []
        def handler(request):
            self.requests.append(request)
            path = request.url.path
            if path.endswith("/nav"):
                data = {"mid": mid, "isLogin": True, "wbi_img": {
                    "img_url": "https://i0.hdslb.com/" + "a" * 32 + ".png",
                    "sub_url": "https://i0.hdslb.com/" + "b" * 32 + ".png"}}
            elif path.endswith("/view"):
                data = {"bvid": BV, "aid": 1234, "owner": {"name": "fixture"},
                        "pages": [{"cid": 11, "duration": 60}]}
            elif path == "/x/player/wbi/v2":
                if blocked:
                    return httpx.Response(412, text="<html>请求被拒绝，风控</html>")
                data = {"bvid": BV, "aid": 1234, "cid": 11, "subtitle": {"subtitles": []}}
            else:
                self.fail("Unexpected request")
            return httpx.Response(200, json={"code": business_code, "data": data, "message": "private-message"})
        transport = httpx.Client(transport=httpx.MockTransport(handler))
        self.addCleanup(transport.close)
        account = BilibiliClient(BilibiliCredentials("test-only-cookie", "a" * 32), client=transport)
        browser = BrowseClient(account, diagnostics=self.log)
        self.addCleanup(browser.close)
        return browser

    def test_diagnose_checks_identity_and_stops_at_412_without_legacy_or_model(self):
        result = diagnose(self.browser(), BINDING, BV)
        self.assertEqual(result["status"], "source_error")
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["messages_sent"], 0)
        self.assertEqual(len(self.requests), 4)
        self.assertTrue(all(r.method == "GET" for r in self.requests))
        self.assertEqual(result["requests"][-1]["http_status"], 412)
        self.assertEqual(result["checks"][-2], {"check": "signing_encoding", "ok": True})
        self.assertNotIn("/x/player/v2", [r.url.path for r in self.requests])
        self.assertNotIn("private-message", self.log.path.read_text(encoding="utf-8"))

    def test_binding_failure_prevents_detail_and_player(self):
        result = diagnose(self.browser(mid=999), BINDING, BV)
        self.assertEqual(result["status"], "source_error")
        self.assertEqual(len(self.requests), 1)

    def test_business_code_recorded_without_server_message(self):
        result = diagnose(self.browser(business_code=-101), BINDING, BV)
        self.assertEqual(result["requests"][0]["business_code"], -101)
        self.assertIn("business_error", [row.get("outcome") for row in self.rows()])
        self.assertNotIn("private-message", json.dumps(self.rows()))

    def test_no_subtitles_is_unavailable_not_a_successful_content_review(self):
        result = diagnose(self.browser(blocked=False), BINDING, BV)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["segments"], 0)

    def test_bad_video_or_page_rejected_before_network(self):
        browser = self.browser()
        for bvid, page in (("bad", 1), (BV, 0), (BV, True)):
            with self.assertRaises(BilibiliConnectorError):
                diagnose(browser, BINDING, bvid, page=page)
        self.assertFalse(self.requests)

    def test_cli_diagnose_does_not_import_model_or_memory(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("bili_cli_fixture", root / "scripts/bilibili_browse.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        blocked_modules = {"src.bilibili_persona": None, "src.bilibili_memory": None, "nonebot": None}
        with patch.dict(sys.modules, blocked_modules), patch.object(cli.BindingStore, "load", return_value=BINDING), \
                patch.object(cli.CredentialStore, "load", return_value=BilibiliCredentials("test-only-cookie", "a" * 32)), \
                patch.object(cli, "BrowseClient", return_value=self.browser()), \
                patch.object(cli, "diagnose", return_value={"status": "source_error", "diagnostics": {"write_failures": 0}}), \
                patch("builtins.print"):
            self.assertEqual(cli.main(["diagnose", "--bvid", BV]), 1)


if __name__ == "__main__":
    unittest.main()
