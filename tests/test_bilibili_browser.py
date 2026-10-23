from __future__ import annotations

import base64
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.bilibili_browser import (
    BrowserCDP, LOGIN_URL, MAX_BYTES, NAV_URL, PersistentBrowser,
    account_status, debugger_url, profile_lock,
)
from src.bilibili_connector import BilibiliBinding, BilibiliConnectorError

ROOT = Path(__file__).resolve().parents[1]
BINDING = BilibiliBinding("aike", "aike", "12345678901", "23456789012")


class PersistentBrowserTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name).resolve()
        self.browser = PersistentBrowser(BINDING, home=self.home)

    def test_prepare_reuses_fixed_profile_and_stores_only_binding_digest(self):
        self.browser.prepare()
        fixture = self.browser.profile / "fixture"
        fixture.write_text("saved-session", encoding="utf-8")
        other = PersistentBrowser(BINDING, home=self.home)
        other.prepare()
        self.assertEqual(other.profile, self.browser.profile)
        self.assertEqual(fixture.read_text(), "saved-session")
        marker = self.browser.marker.read_text()
        self.assertNotIn(BINDING.aike_mid, marker)
        self.assertNotIn(BINDING.owner_mid, marker)

    def test_binding_changes_refuse_to_reuse_or_overwrite_profile(self):
        self.browser.prepare()
        original = self.browser.marker.read_bytes()
        for changed in (
            BilibiliBinding("other", "aike", BINDING.aike_mid, BINDING.owner_mid),
            BilibiliBinding("aike", "other", BINDING.aike_mid, BINDING.owner_mid),
            BilibiliBinding("aike", "aike", "34567890123", BINDING.owner_mid),
            BilibiliBinding("aike", "aike", BINDING.aike_mid, "34567890123"),
        ):
            with self.subTest(changed=changed), self.assertRaises(BilibiliConnectorError):
                PersistentBrowser(changed, home=self.home).prepare()
            self.assertEqual(self.browser.marker.read_bytes(), original)

    def test_nonempty_unbound_profile_and_corrupt_marker_are_rejected(self):
        self.browser.profile.mkdir()
        fixture = self.browser.profile / "fixture"
        fixture.write_text("keep", encoding="utf-8")
        with self.assertRaises(BilibiliConnectorError):
            self.browser.prepare()
        self.assertFalse(self.browser.marker.exists())
        for content in ("broken", "[]", '{"version":2}'):
            self.browser.marker.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(BilibiliConnectorError):
                self.browser.prepare()
        self.assertEqual(fixture.read_text(), "keep")

    def test_profile_must_stay_outside_repository(self):
        with self.assertRaises(BilibiliConnectorError):
            PersistentBrowser(BINDING, home=ROOT / "private-browser-test")

    def test_redirected_profile_is_rejected_before_marker_write(self):
        original = Path.resolve
        def resolve(path, *args, **kwargs):
            if path == self.browser.profile:
                return self.home / "elsewhere"
            return original(path, *args, **kwargs)
        with patch.object(Path, "resolve", resolve), self.assertRaises(BilibiliConnectorError):
            self.browser.prepare()
        self.assertFalse(self.browser.marker.exists())

    def test_os_lock_blocks_overlapping_controller_and_releases_after_failure(self):
        with self.assertRaisesRegex(RuntimeError, "fixture"):
            with profile_lock(self.browser.lock):
                with self.assertRaises(BilibiliConnectorError):
                    with profile_lock(self.browser.lock):
                        self.fail("overlapping controller acquired lock")
                raise RuntimeError("fixture")
        with profile_lock(self.browser.lock):
            pass

    def test_debugger_endpoint_is_strictly_loopback(self):
        self.browser.profile.mkdir()
        endpoint = self.browser.profile / "DevToolsActivePort"
        identifier = "/devtools/browser/12345678-1234-1234-1234-123456789abc"
        endpoint.write_text("12345\n" + identifier, encoding="utf-8")
        self.assertEqual(debugger_url(self.browser.profile), "ws://127.0.0.1:12345" + identifier)
        for content in ("", "0\n" + identifier, "65536\n" + identifier,
                        "１２３\n" + identifier, "12345\nws://outside.test/",
                        "12345\n/devtools/page/" + "a" * 36, "x" * 513):
            endpoint.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(BilibiliConnectorError):
                debugger_url(self.browser.profile)

    def test_open_reuses_existing_instance_without_launching_process(self):
        with patch("src.bilibili_browser.BrowserCDP") as cdp, patch("src.bilibili_browser.subprocess.Popen") as launch:
            result = self.browser.open()
        self.assertTrue(result["reused_process"])
        self.assertFalse(result["account_verified"])
        launch.assert_not_called()
        cdp.assert_called_once_with(self.browser.profile)

    @unittest.skipUnless(sys.platform == "win32", "Windows Edge launch")
    def test_launch_uses_persistent_default_profile_and_visible_manual_login(self):
        ready = MagicMock()
        with patch("src.bilibili_browser.BrowserCDP", side_effect=[BilibiliConnectorError("not-open"), ready]), \
             patch("src.bilibili_browser.edge_executable", return_value=Path("C:/fixture/msedge.exe")), \
             patch("src.bilibili_browser.subprocess.Popen") as launch:
            result = self.browser.open()
        self.assertFalse(result["reused_process"])
        args = launch.call_args.args[0]
        self.assertIn("--user-data-dir=" + str(self.browser.profile), args)
        self.assertIn("--profile-directory=Default", args)
        self.assertIn("--remote-debugging-address=127.0.0.1", args)
        self.assertIn("--remote-debugging-port=0", args)
        self.assertEqual(args[-1], LOGIN_URL)
        self.assertNotIn("--incognito", args)
        self.assertNotIn("--headless", args)
        self.assertEqual(launch.call_args.kwargs["startupinfo"].wShowWindow, 1)

    def test_account_classification_including_wrong_account_and_blocked_responses(self):
        cases = [
            (200, {"code": 0, "data": {"isLogin": True, "mid": int(BINDING.aike_mid)}}, "logged_in"),
            (200, {"code": 0, "data": {"isLogin": True, "mid": BINDING.owner_mid}}, "account_mismatch"),
            (200, {"code": -101}, "login_required"),
            (200, {"code": 0, "data": {"isLogin": False}}, "login_required"),
            (412, {"code": -412}, "account_request_blocked"),
            (200, {"code": -352}, "account_request_blocked"),
            (412, [], "account_request_blocked"),
            (200, [], "account_response_invalid"),
            (200, {"code": False, "data": {}}, "account_response_invalid"),
            (200, {"code": 0, "data": []}, "account_response_invalid"),
            (200, {"code": 0, "data": {"isLogin": True, "mid": True}}, "account_response_invalid"),
        ]
        for status, payload, expected in cases:
            with self.subTest(status=status, expected=expected):
                self.assertEqual(account_status(status, json.dumps(payload).encode(), BINDING)[0], expected)
        for status, expected in ((200, "account_response_invalid"), (412, "account_request_blocked")):
            self.assertEqual(account_status(status, b"<html>blocked</html>", BINDING), (expected, None))

    def test_check_writes_only_safe_status_and_diagnostics(self):
        payload = {"code": 0, "data": {"isLogin": True, "mid": BINDING.aike_mid,
                   "uname": "synthetic-private-name"}, "message": "synthetic-private-message"}
        with patch("src.bilibili_browser.BrowserCDP") as cdp:
            cdp.return_value.__enter__.return_value.account_response.return_value = (
                200, {"set-cookie": "synthetic-private-cookie", "content-type": "application/json"}, json.dumps(payload).encode())
            result = self.browser.check()
        self.assertEqual(result["status"], "logged_in")
        self.assertTrue(result["account_verified"])
        self.assertEqual(result["model_calls"], 0)
        self.assertEqual(result["messages_sent"], 0)
        saved = self.browser.state.read_text(encoding="utf-8")
        saved += Path(result["diagnostics"]["path"]).read_text(encoding="utf-8")
        for forbidden in (BINDING.aike_mid, BINDING.owner_mid, "synthetic-private", "set-cookie"):
            self.assertNotIn(forbidden, saved)
        self.assertEqual(result["diagnostics"]["write_failures"], 0)

    def test_check_failure_records_unreachable_without_raw_exception(self):
        with patch("src.bilibili_browser.BrowserCDP", side_effect=BilibiliConnectorError("fixture")), \
             self.assertRaises(BilibiliConnectorError):
            self.browser.check()
        self.assertEqual(json.loads(self.browser.state.read_text())["status"], "browser_unreachable")
        self.assertNotIn("fixture", self.browser.state.read_text())

    def test_status_handles_damaged_history_without_live_account_request(self):
        self.browser.prepare()
        for content in ('{"status":[]}', '{"status":{}}', '[]', 'broken', '{"status":"logged_in"}'):
            self.browser.state.write_text(content, encoding="utf-8")
            with patch("src.bilibili_browser.BrowserCDP") as cdp:
                result = self.browser.status()
            self.assertFalse(result["live_account_check"])
            cdp.return_value.__enter__.return_value.account_response.assert_not_called()
            self.assertEqual(result["last_check_status"], "logged_in" if "logged_in" in content else "not_checked")

    def test_close_uses_only_dedicated_endpoint_and_retains_profile(self):
        self.browser.prepare()
        fixture = self.browser.profile / "fixture"
        fixture.write_text("keep", encoding="utf-8")
        with patch("src.bilibili_browser.BrowserCDP") as cdp:
            browser = cdp.return_value.__enter__.return_value
            browser.sequence = 7
            result = self.browser.close()
        cdp.assert_called_once_with(self.browser.profile)
        command = json.loads(browser.socket.send.call_args.args[0])
        self.assertEqual(command, {"id": 8, "method": "Browser.close"})
        self.assertEqual(result["status"], "browser_closed")
        self.assertEqual(fixture.read_text(), "keep")

    def test_close_socket_failure_is_safe(self):
        with patch("src.bilibili_browser.BrowserCDP") as cdp:
            browser = cdp.return_value.__enter__.return_value
            browser.sequence = 1
            browser.socket.send.side_effect = RuntimeError("synthetic-private-value")
            with self.assertRaises(BilibiliConnectorError) as caught:
                self.browser.close()
        self.assertNotIn("synthetic-private", str(caught.exception))


class BrowserCDPTests(unittest.TestCase):
    def setUp(self):
        self.browser = object.__new__(BrowserCDP)
        self.browser.sequence = 0
        self.browser.events = []
        self.browser.socket = MagicMock()

    def test_connect_uses_loopback_bounded_messages_and_no_proxy(self):
        with patch("src.bilibili_browser.debugger_url", return_value="ws://127.0.0.1:12345/fixture"), \
             patch("websockets.sync.client.connect") as connect:
            with BrowserCDP(Path("fixture")):
                pass
        self.assertEqual(connect.call_args.kwargs["max_size"], 6 * MAX_BYTES)
        self.assertIsNone(connect.call_args.kwargs["proxy"])

    def test_receive_rejects_nonobject_and_broken_protocol_without_raw_text(self):
        for raw in ('[]', '"synthetic-private"', 'null', 'broken'):
            self.browser.socket.recv.return_value = raw
            with self.subTest(raw=raw), self.assertRaises(BilibiliConnectorError) as caught:
                self.browser.receive()
            self.assertNotIn("synthetic-private", str(caught.exception))
        self.browser.socket.recv.side_effect = TimeoutError()
        self.assertIsNone(self.browser.receive())

    def test_call_keeps_events_and_returns_only_its_response(self):
        self.browser.socket.recv.side_effect = [
            json.dumps({"method": "Page.event", "sessionId": "fixture"}),
            json.dumps({"id": 1, "result": {"ok": True}}),
        ]
        self.assertEqual(self.browser.call("Browser.getVersion"), {"ok": True})
        self.assertEqual(len(self.browser.events), 1)

    def test_call_protocol_error_or_bad_result_is_safe(self):
        for response in ({"id": 1, "error": {"message": "synthetic-private"}}, {"id": 1, "result": []}):
            self.browser.sequence = 0
            self.browser.socket.recv.return_value = json.dumps(response)
            with self.subTest(response=response), self.assertRaises(BilibiliConnectorError) as caught:
                self.browser.call("Browser.getVersion")
            self.assertNotIn("synthetic-private", str(caught.exception))

    def account(self, body, *, encoded=False):
        self.calls = []
        def call(method, params=None, session=None, **kwargs):
            self.calls.append((method, params, session))
            if method == "Target.createTarget":
                return {"targetId": "tab"}
            if method == "Target.attachToTarget":
                return {"sessionId": "session"}
            if method == "Page.navigate":
                self.browser.events += [
                    {"sessionId": "other", "method": "Network.responseReceived", "params": {}},
                    {"sessionId": "session", "method": "Network.responseReceived", "params": {
                        "requestId": "request", "response": {"url": NAV_URL, "status": 200, "headers": {}}}},
                    {"sessionId": "session", "method": "Network.loadingFinished", "params": {"requestId": "request"}},
                ]
            if method == "Network.getResponseBody":
                return {"body": body, "base64Encoded": encoded}
            return {}
        with patch.object(self.browser, "call", side_effect=call):
            return self.browser.account_response()

    def test_account_read_uses_default_context_and_closes_temporary_tab(self):
        result = self.account('{"code":-101}')
        self.assertEqual(result, (200, {}, b'{"code":-101}'))
        self.assertEqual(self.calls[0], ("Target.createTarget", {"url": "about:blank"}, None))
        self.assertEqual(self.calls[-1], ("Target.closeTarget", {"targetId": "tab"}, None))
        self.assertEqual(sum(name == "Page.navigate" for name, _, _ in self.calls), 1)
        self.assertFalse(any("Cookie" in name or "BrowserContext" in name for name, _, _ in self.calls))

    def test_account_body_limit_encoding_and_cleanup_on_failure(self):
        self.assertEqual(self.account(base64.b64encode(b"fixture").decode(), encoded=True)[2], b"fixture")
        for body, encoded in (("x" * (MAX_BYTES + 1), False), ("!invalid-base64", True), ([], False)):
            with self.subTest(encoded=encoded, body_type=type(body).__name__), self.assertRaises(BilibiliConnectorError):
                self.account(body, encoded=encoded)
            self.assertEqual(self.calls[-1][0], "Target.closeTarget")


class BrowserCLITests(unittest.TestCase):
    def test_cli_help_imports_no_bot_memory_or_persona_modules(self):
        script = (
            "import importlib.util,sys; "
            "s=importlib.util.spec_from_file_location('browser_cli','scripts/bilibili_browser.py'); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "assert not any(k.startswith(('nonebot','src.plugins.ai_chat','src.bilibili_memory','src.bilibili_persona')) for k in sys.modules); "
            "m.main(['--help'])"
        )
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("subtitle-check", result.stdout)

    def test_cli_account_mismatch_is_nonzero(self):
        spec = importlib.util.spec_from_file_location("browser_cli_test", ROOT / "scripts/bilibili_browser.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        for status, expected in (("logged_in", 0), ("account_mismatch", 1), ("login_required", 1)):
            with patch.object(cli, "BindingStore") as bindings, patch.object(cli, "PersistentBrowser") as browsers, redirect_stdout(io.StringIO()):
                bindings.return_value.load.return_value = BINDING
                browsers.return_value.check.return_value = {"status": status}
                self.assertEqual(cli.main(["check"]), expected)


if __name__ == "__main__":
    unittest.main()
