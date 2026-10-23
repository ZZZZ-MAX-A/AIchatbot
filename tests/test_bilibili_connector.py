from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.bilibili_connector import (
    BilibiliBinding, BilibiliClient, BilibiliConnectorError,
    BilibiliCredentials, BindingStore, CredentialStore, DeliveryStore,
)

spec = importlib.util.spec_from_file_location("bilibili_cli", REPO_ROOT / "scripts/bilibili_connect.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class BilibiliConnectorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.environment = patch.dict(os.environ, {"AIKE_BILIBILI_HOME": str(self.home)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.credentials = BilibiliCredentials("synthetic-session", "a" * 32, "synthetic-device")
        self.binding = BilibiliBinding("aike", "aike", "456", "789")
        self.requests = []
        self.mid = 456
        self.relation_attribute = 6
        self.post_response = {"code": 0, "data": {"msg_key": "synthetic"}}
        self.post_error = None
        self.http = httpx.Client(transport=httpx.MockTransport(self.handler))
        self.addCleanup(self.http.close)
        self.client = BilibiliClient(self.credentials, client=self.http)

    def handler(self, request):
        self.requests.append(request)
        if request.url.path.endswith("/nav"):
            return httpx.Response(200, json={"code": 0, "data": {"isLogin": True, "mid": self.mid, "uname": "test"}})
        if request.url.path == "/x/relation":
            self.assertEqual(request.url.params["fid"], "789")
            return httpx.Response(200, json={"code": 0, "data": {"attribute": self.relation_attribute}})
        self.assertEqual(request.method, "POST")
        self.assertEqual(str(request.url), BilibiliClient.DM_ENDPOINT)
        # The send must be reserved on disk before it leaves the client.
        self.assertEqual(DeliveryStore().recent()[0][1], "pending")
        if self.post_error:
            raise self.post_error
        if isinstance(self.post_response, httpx.Response):
            return self.post_response
        return httpx.Response(200, json=self.post_response)

    def send(self, **kwargs):
        return self.client.send_private_message(self.binding, "发现一个有意思的视频 https://www.bilibili.com/video/BV-example", **kwargs)

    @unittest.skipUnless(sys.platform == "win32", "Windows DPAPI")
    def test_credential_store_dpapi_round_trip_and_no_plaintext(self):
        store = CredentialStore()
        store.save(self.credentials)
        self.assertEqual(store.load(), self.credentials)
        saved = store.path.read_text(encoding="utf-8")
        self.assertNotIn(self.credentials.sessdata, saved)
        self.assertNotIn(self.credentials.bili_jct, saved)
        self.assertEqual(json.loads(saved)["format"], "dpapi-v1")

    def test_credentials_repr_hides_secrets_and_rejects_header_injection(self):
        self.assertNotIn(self.credentials.sessdata, repr(self.credentials))
        self.assertNotIn(self.credentials.bili_jct, repr(self.credentials))
        for value in ("", "value\r\nInjected: yes", "value;another=cookie", "中文"):
            with self.subTest(value=value), self.assertRaises(BilibiliConnectorError):
                BilibiliCredentials(value, "a" * 32).validate()
        with self.assertRaises(BilibiliConnectorError):
            BilibiliCredentials("session", "not-a-csrf").validate()

    def test_binding_round_trip_and_uid_validation(self):
        store = BindingStore()
        store.save(self.binding)
        self.assertEqual(store.load(), self.binding)
        for uid in ("456", "0", "0789", "１２３", "-1"):
            with self.subTest(uid=uid), self.assertRaises(BilibiliConnectorError):
                BilibiliBinding("aike", "aike", "456", uid).validate()

    def test_corrupt_stores_fail_with_safe_error(self):
        for store in (CredentialStore(), BindingStore()):
            for raw in ("not-json", "[]", '{"format":"dpapi-v1","blob":"broken"}'):
                store.path.write_text(raw, encoding="utf-8")
                with self.subTest(store=type(store).__name__, raw=raw), self.assertRaises(BilibiliConnectorError):
                    store.load()

    def test_dry_run_has_no_post_or_delivery_state(self):
        result = self.send()
        self.assertTrue(result.dry_run)
        self.assertFalse(result.sent)
        self.assertEqual([r.method for r in self.requests], ["GET", "GET"])
        self.assertFalse((self.home / "deliveries.sqlite3").exists())
        self.assertFalse((self.home / "device-id").exists())

    def test_success_payload_and_duplicate_prevention_across_clients(self):
        result = self.send(dry_run=False)
        self.assertTrue(result.sent)
        post = self.requests[-1]
        form = parse_qs(post.content.decode())
        self.assertEqual(form["msg[sender_uid]"], ["456"])
        self.assertEqual(form["msg[receiver_id]"], ["789"])
        self.assertEqual(form["msg[msg_type]"], ["1"])
        self.assertEqual(form["csrf"], [self.credentials.bili_jct])
        self.assertIn("https://www.bilibili.com/video/", json.loads(form["msg[content]"][0])["content"])
        self.assertTrue(form["msg[dev_id]"][0].startswith("WEB-"))
        self.assertEqual(DeliveryStore().recent()[0][1], "sent")
        self.client = BilibiliClient(self.credentials, client=self.http)
        with self.assertRaisesRegex(BilibiliConnectorError, "已阻止重复发送"):
            self.send(dry_run=False)
        self.assertEqual(sum(r.method == "POST" for r in self.requests), 1)

    def test_unknown_delivery_not_retried_for_network_http_or_parse_errors(self):
        cases = (httpx.ReadTimeout("synthetic"), httpx.Response(502), httpx.Response(200, text="not-json"), {"message": "no code"})
        for index, response in enumerate(cases):
            self.post_error = response if isinstance(response, Exception) else None
            self.post_response = response
            with self.subTest(response=type(response).__name__):
                for _ in range(2):
                    with self.assertRaises(BilibiliConnectorError):
                        self.send(dry_run=False, delivery_key=f"failure-{index}")
                self.assertEqual(DeliveryStore().recent()[0][1], "unknown")
        self.assertEqual(sum(r.method == "POST" for r in self.requests), len(cases))

    def test_platform_error_persisted_and_not_retried(self):
        self.post_response = {"code": -111, "message": self.credentials.sessdata}
        with self.assertRaisesRegex(BilibiliConnectorError, "code=-111") as caught:
            self.send(dry_run=False)
        self.assertNotIn(self.credentials.sessdata, str(caught.exception))
        self.assertEqual(DeliveryStore().recent()[0][1], "failed")
        with self.assertRaisesRegex(BilibiliConnectorError, "已阻止重复发送"):
            self.send(dry_run=False)

    def test_wrong_account_nonmutual_and_invalid_text_block_before_post(self):
        self.mid = 999
        with self.assertRaisesRegex(BilibiliConnectorError, "不一致"):
            self.send(dry_run=False)
        self.mid = 456
        self.relation_attribute = 2
        with self.assertRaisesRegex(BilibiliConnectorError, "互相关注"):
            self.send(dry_run=False)
        for text in ("", "x" * 301):
            with self.assertRaises(BilibiliConnectorError):
                self.client.send_private_message(self.binding, text, dry_run=False)
        self.assertFalse(any(r.method == "POST" for r in self.requests))
        self.assertFalse((self.home / "deliveries.sqlite3").exists())

    def test_account_expiry_malformed_responses_and_redirect_are_safe(self):
        cases = (
            httpx.Response(200, json={"code": -101}),
            httpx.Response(200, json={"code": 0, "data": []}),
            httpx.Response(200, json={"code": 0, "data": {"isLogin": False}}),
            httpx.Response(200, json={"code": 0, "data": {"isLogin": True, "mid": "bad"}}),
            httpx.Response(302, headers={"Location": "https://example.com/"}),
        )
        for response in cases:
            requests = []
            def handler(request):
                requests.append(request)
                return response
            with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as http:
                with self.assertRaises(BilibiliConnectorError):
                    BilibiliClient(self.credentials, client=http).account()
                self.assertEqual(len(requests), 1)

    def test_crash_reservation_blocks_replay(self):
        ledger = DeliveryStore()
        request_id = ledger.reserve("crashed-job")
        with self.assertRaisesRegex(BilibiliConnectorError, "pending"):
            DeliveryStore().reserve("crashed-job")
        self.assertEqual(ledger.recent()[0][:2], (request_id, "pending"))

    def test_concurrent_reservations_allow_only_one_attempt(self):
        def reserve(_):
            try:
                return DeliveryStore().reserve("one-job")
            except BilibiliConnectorError:
                return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(reserve, range(8)))
        self.assertEqual(sum(value is not None for value in results), 1)
        self.assertEqual(len(DeliveryStore().recent()), 1)

    def test_ledger_failure_prevents_post_and_result_write_failure_blocks_replay(self):
        with patch.object(self.client.deliveries, "reserve", side_effect=sqlite3.OperationalError("synthetic")):
            with self.assertRaises(sqlite3.Error):
                self.send(dry_run=False)
        self.assertFalse(any(r.method == "POST" for r in self.requests))
        with patch.object(self.client.deliveries, "finish", side_effect=sqlite3.OperationalError("synthetic")):
            with self.assertRaises(sqlite3.Error):
                self.send(dry_run=False)
        self.assertEqual(DeliveryStore().recent()[0][1], "pending")
        with self.assertRaisesRegex(BilibiliConnectorError, "已阻止重复发送"):
            self.send(dry_run=False)
        self.assertEqual(sum(r.method == "POST" for r in self.requests), 1)

    def test_explicit_job_id_deduplicates_even_if_text_changes(self):
        self.send(dry_run=False, delivery_key="job-one")
        with self.assertRaisesRegex(BilibiliConnectorError, "已阻止重复发送"):
            self.client.send_private_message(self.binding, "changed", dry_run=False, delivery_key="job-one")
        self.send(dry_run=False, delivery_key="intentional-new-job")
        self.assertEqual(sum(r.method == "POST" for r in self.requests), 2)

    def test_cli_binding_checks_live_self_uid_before_saving(self):
        with patch.object(cli.CredentialStore, "load", return_value=self.credentials), patch.object(cli, "BilibiliClient", return_value=self.client), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = cli.main(["bind-owner", "--aike-uid", "999", "--owner-uid", "789"])
        self.assertEqual(result, 2)
        self.assertFalse(BindingStore().path.exists())

    def test_cli_preview_and_local_send_records(self):
        BindingStore().save(self.binding)
        with patch.object(cli.CredentialStore, "load", return_value=self.credentials), patch.object(cli, "BilibiliClient", return_value=self.client), redirect_stdout(io.StringIO()) as output:
            result = cli.main(["send", "--text", "synthetic test"])
        self.assertEqual(result, 0)
        self.assertIn("未发送私信", output.getvalue())
        self.assertFalse(any(r.method == "POST" for r in self.requests))

    @unittest.skipUnless(sys.platform == "win32", "Windows DPAPI")
    def test_cli_login_validates_before_storing_without_printing_cookies(self):
        with patch.object(cli, "_hidden_input", side_effect=[self.credentials.sessdata, self.credentials.bili_jct, self.credentials.buvid3]), patch.object(cli, "BilibiliClient", return_value=self.client), patch("builtins.input", return_value="yes"), redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cli.main(["login"]), 0)
        self.assertEqual(CredentialStore().load(), self.credentials)
        self.assertNotIn(self.credentials.sessdata, output.getvalue())
        self.assertNotIn(self.credentials.bili_jct, output.getvalue())

    def test_cli_can_launch_outside_repo_and_missing_config_is_friendly(self):
        script = str(REPO_ROOT / "scripts/bilibili_connect.py")
        help_result = subprocess.run([sys.executable, script, "--help"], cwd=self.home, capture_output=True)
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        status = subprocess.run([sys.executable, script, "status"], cwd=self.home, capture_output=True)
        self.assertEqual(status.returncode, 2)
        self.assertNotIn(b"Traceback", status.stderr)


if __name__ == "__main__":
    unittest.main()
