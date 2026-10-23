from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import urlsplit

import httpx

from src.bilibili_browser_transport import BrowserAccountClient, BrowserTransport, FETCH_SCRIPT
from src.bilibili_connector import BilibiliBinding

BINDING = BilibiliBinding("aike", "aike", "101", "202")


class BrowserTransportTests(unittest.TestCase):
    def setUp(self):
        self.browser = MagicMock()
        self.origin = ""
        self.response = {"status": 200, "headers": {"content-type": "application/json", "set-cookie": "private"},
                         "body": json.dumps({"code": 0, "data": {"isLogin": True, "mid": 101}})}
        self.expressions = []
        def call(method, params=None, session=None, **kwargs):
            if method == "Target.createTarget":
                return {"targetId": "fixture-target"}
            if method == "Target.attachToTarget":
                return {"sessionId": "fixture-session"}
            if method == "Page.navigate":
                parts = urlsplit(params["url"])
                self.origin = parts.scheme + "://" + parts.netloc
            if method == "Runtime.evaluate":
                if params["expression"] == "location.origin":
                    return {"result": {"value": self.origin}}
                self.expressions.append(params["expression"])
                return {"result": {"value": self.response}}
            return {}
        self.browser.call.side_effect = call
        self.transport = BrowserTransport(self.browser, BINDING)
        self.addCleanup(self.transport.close)

    def test_get_uses_ambient_browser_credentials_with_bounded_response(self):
        result = self.transport.handle_request(httpx.Request("GET", "https://api.bilibili.com/x/web-interface/nav"))
        self.assertEqual(result.status_code, 200)
        self.assertNotIn("set-cookie", result.headers)
        self.assertIn("credentials:'include'", self.expressions[0])
        self.assertIn("2097152", self.expressions[0])
        self.assertIn("redirect:'error'", self.expressions[0])

    def test_other_hosts_paths_credentials_and_methods_are_rejected_before_cdp(self):
        for method, url in (("GET", "https://outside.test/x/web-interface/nav"),
                            ("POST", "https://api.bilibili.com/x/relation/modify"),
                            ("GET", "https://api.bilibili.com/x/player/v2"),
                            ("GET", "https://api.bilibili.com/x/player/wbi/v2"),
                            ("GET", "http://api.bilibili.com/x/web-interface/nav"),
                            ("GET", "https://user:pass@api.bilibili.com/x/web-interface/nav")):
            with self.subTest(method=method, url=url), self.assertRaises(httpx.RequestError):
                self.transport.handle_request(httpx.Request(method, url))
        self.browser.call.assert_not_called()

    def test_post_only_uses_pinned_sender_receiver_and_no_exported_csrf(self):
        endpoint = "https://api.vc.bilibili.com/web_im/v1/web_im/send_msg"
        for values in ({"msg[sender_uid]": "999", "msg[receiver_id]": "202"},
                       {"msg[sender_uid]": "101", "msg[receiver_id]": "999"},
                       {"msg[sender_uid]": "101", "msg[receiver_id]": "202", "csrf": "not-allowed"}):
            with self.assertRaises(httpx.RequestError):
                self.transport.handle_request(httpx.Request("POST", endpoint, data=values))
        self.browser.call.assert_not_called()
        self.transport.handle_request(httpx.Request("POST", endpoint, data={"msg[sender_uid]": "101", "msg[receiver_id]": "202"}))
        self.assertEqual(self.origin, "https://api.vc.bilibili.com")
        self.assertIn("body.set('csrf'", self.expressions[-1])
        self.assertNotIn("cookie:", self.expressions[-1])

    def test_session_reused_and_only_own_targets_closed(self):
        request = httpx.Request("GET", "https://api.bilibili.com/x/web-interface/nav")
        self.transport.handle_request(request)
        self.transport.handle_request(request)
        self.assertEqual(sum(c.args[0] == "Target.createTarget" for c in self.browser.call.call_args_list), 1)
        self.transport.close()
        self.assertEqual(self.transport.tabs, {})
        self.browser.call.assert_called_with("Target.closeTarget", {"targetId": "fixture-target"}, timeout=3)

    def test_timeout_or_invalid_responses_never_retried(self):
        for response in ({"error": "timeout"}, {"error": "csrf_missing"}, {"error": "too_large"},
                         {"status": True, "body": "x"}, {"status": 200, "body": "x" * 2097153}):
            self.response = response
            before = len(self.expressions)
            with self.assertRaises(httpx.RequestError):
                self.transport.handle_request(httpx.Request("GET", "https://api.bilibili.com/x/web-interface/nav"))
            self.assertEqual(len(self.expressions) - before, 1)

    def test_inbox_read_is_limited_to_bound_owner_and_allowed_parameters(self):
        url = "https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs"
        base = {"talker_id": "202", "session_type": "1", "size": "50"}
        for values in ({**base, "talker_id": "999"}, {**base, "session_type": "2"},
                       {**base, "size": "51"}, {**base, "csrf": "not-allowed"},
                       {**base, "end_seqno": "-1"}):
            with self.assertRaises(httpx.RequestError):
                self.transport.handle_request(httpx.Request("GET", url, params=values))
        self.browser.call.assert_not_called()
        self.transport.handle_request(httpx.Request("GET", url, params=base))
        self.assertEqual(self.origin, "https://api.vc.bilibili.com")

    def test_repeated_owner_query_cannot_bypass_inbox_target_check(self):
        with self.assertRaises(httpx.RequestError):
            self.transport.handle_request(httpx.Request("GET", "https://api.vc.bilibili.com/svr_sync/v1/svr_sync/fetch_session_msgs",
                params=[("talker_id", "202"), ("talker_id", "999"), ("session_type", "1"), ("size", "50")]))
        self.browser.call.assert_not_called()

    def test_browser_client_needs_no_stored_cookie_and_uses_existing_account_validation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"AIKE_BILIBILI_HOME": directory}), \
             patch("src.bilibili_connector.CredentialStore.load", side_effect=AssertionError("must not read old cookies")):
            with BrowserAccountClient(self.browser, BINDING) as account:
                self.assertEqual(account.account().mid, "101")
                self.assertEqual(account.headers, {})
                self.assertFalse(hasattr(account, "credentials"))


if __name__ == "__main__":
    unittest.main()
