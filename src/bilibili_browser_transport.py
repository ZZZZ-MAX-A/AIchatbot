"""Small allowlisted HTTP bridge to the dedicated browser; cookies stay in Edge."""
from __future__ import annotations

import json
from contextlib import nullcontext
import time
from urllib.parse import parse_qs

import httpx

from .bilibili_connector import BilibiliClient, BilibiliConnectorError, DeliveryStore
from .bilibili_browser import controller_lock

READ_PATHS = {"/x/web-interface/nav", "/x/relation", "/x/web-interface/view",
              "/x/web-interface/wbi/index/top/feed/rcmd", "/x/polymer/web-dynamic/v1/feed/all"}
INBOX_PATH = "/svr_sync/v1/svr_sync/fetch_session_msgs"
ORIGIN_PAGES = {"https://api.bilibili.com": "https://api.bilibili.com/x/web-interface/nav",
                "https://api.vc.bilibili.com": "https://api.vc.bilibili.com/session_svr/v1/session_svr/single_unread?build=0&mobi_app=web"}
FETCH_SCRIPT = """(async () => {
  const spec = SPEC;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    let body;
    const headers = {};
    if (spec.method === 'POST') {
      const csrf = document.cookie.split(';').map(x => x.trim()).find(x => x.startsWith('bili_jct='));
      if (!csrf) return {error:'csrf_missing'};
      body = new URLSearchParams(spec.body);
      body.set('csrf', decodeURIComponent(csrf.slice('bili_jct='.length)));
      headers['Content-Type'] = 'application/x-www-form-urlencoded';
    }
    const response = await fetch(spec.url, {method:spec.method, credentials:'include', redirect:'error',
                                          signal:controller.signal, headers, body});
    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let count = 0, text = '';
    if (reader) {
      while (true) {
        const part = await reader.read();
        if (part.done) break;
        count += part.value.byteLength;
        if (count > 2097152) { await reader.cancel(); return {error:'too_large'}; }
        text += decoder.decode(part.value, {stream:true});
      }
      text += decoder.decode();
    }
    return {status:response.status, headers:{'content-type':response.headers.get('content-type') || '',
            date:response.headers.get('date') || ''}, body:text};
  } catch (e) { return {error:controller.signal.aborted ? 'timeout' : 'network'}; }
  finally { clearTimeout(timer); }
})()"""


class BrowserTransport(httpx.BaseTransport):
    def __init__(self, browser, binding, *, lock=None):
        self.browser = browser
        self.binding = binding
        self.tabs = {}
        self.lock = lock

    def session(self, origin: str) -> str:
        if origin in self.tabs:
            return self.tabs[origin][1]
        target = self.browser.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        try:
            session = self.browser.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
            self.tabs[origin] = (target, session)
            self.browser.call("Page.enable", session=session)
            self.browser.call("Page.navigate", {"url": ORIGIN_PAGES[origin]}, session)
            for _ in range(20):
                result = self.browser.call("Runtime.evaluate", {"expression": "location.origin", "returnByValue": True}, session)
                if result.get("result", {}).get("value") == origin:
                    return session
                time.sleep(0.1)
            raise BilibiliConnectorError("浏览器接口页面未就绪")
        except Exception:
            self.tabs.pop(origin, None)
            try:
                self.browser.call("Target.closeTarget", {"targetId": target}, timeout=3)
            except BilibiliConnectorError:
                pass
            raise

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        url = request.url
        is_read = request.method == "GET" and url.host == "api.bilibili.com" and url.path in READ_PATHS
        is_inbox = request.method == "GET" and url.host == "api.vc.bilibili.com" and url.path == INBOX_PATH
        is_send = request.method == "POST" and str(url) == BilibiliClient.DM_ENDPOINT
        if url.scheme != "https" or url.port not in (None, 443) or url.userinfo or not (is_read or is_inbox or is_send):
            raise httpx.RequestError("Browser request is outside the allowed routes", request=request)
        if is_inbox:
            params = url.params
            allowed = {"talker_id", "session_type", "size", "end_seqno", "build", "mobi_app"}
            if (set(params) - allowed or len(params.multi_items()) != len(params)
                    or params.get("talker_id") != self.binding.owner_mid or params.get("session_type") != "1"
                    or not params.get("size", "").isdigit() or not 1 <= int(params["size"]) <= 50
                    or ("end_seqno" in params and (not params["end_seqno"].isdigit() or len(params["end_seqno"]) > 19))):
                raise httpx.RequestError("Browser inbox target or query is invalid", request=request)
        body = request.content.decode("utf-8") if is_send else ""
        if is_send:
            values = parse_qs(body)
            if (values.get("msg[sender_uid]") != [self.binding.aike_mid] or
                    values.get("msg[receiver_id]") != [self.binding.owner_mid] or "csrf" in values):
                raise httpx.RequestError("Browser message target or credential boundary is invalid", request=request)
        with controller_lock(self.lock) if self.lock is not None else nullcontext():
            return self._fetch(request, body)

    def _fetch(self, request, body):
        url = request.url
        try:
            session = self.session(f"https://{url.host}")
            spec = json.dumps({"url": str(url), "method": request.method, "body": body})
            result = self.browser.call("Runtime.evaluate", {"expression": FETCH_SCRIPT.replace("SPEC", spec),
                                       "awaitPromise": True, "returnByValue": True}, session, timeout=25)
            data = result.get("result", {}).get("value")
            if not isinstance(data, dict) or "error" in data:
                if isinstance(data, dict) and data.get("error") == "timeout":
                    raise httpx.ReadTimeout("Browser request timed out", request=request)
                raise httpx.RequestError("Browser request failed", request=request)
            if (type(data.get("status")) is not int or not 100 <= data["status"] <= 599 or
                    not isinstance(data.get("body"), str) or len(data["body"].encode("utf-8")) > 2097152):
                raise httpx.RequestError("Browser response is invalid or too large", request=request)
            headers = data.get("headers", {})
            return httpx.Response(data["status"], content=data["body"].encode("utf-8"),
                                  headers={k: v for k, v in headers.items() if k in {"content-type", "date"} and isinstance(v, str)},
                                  request=request)
        except BilibiliConnectorError:
            raise httpx.RequestError("Browser control failed", request=request) from None

    def close(self):
        with controller_lock(self.lock) if self.lock is not None else nullcontext():
            self._close_tabs()

    def _close_tabs(self):
        for target, _ in list(self.tabs.values()):
            try:
                self.browser.call("Target.closeTarget", {"targetId": target}, timeout=3)
            except BilibiliConnectorError:
                pass
        self.tabs.clear()


class BrowserAccountClient(BilibiliClient):
    def __init__(self, browser, binding, *, home=None, lock=None):
        binding.validate()
        self._client = httpx.Client(transport=BrowserTransport(browser, binding, lock=lock), follow_redirects=False, trust_env=False)
        self._owns_client = True
        self.deliveries = DeliveryStore(home / "deliveries.sqlite3") if home is not None else DeliveryStore()

    @property
    def headers(self):
        return {}

    def _post_private_form(self, form):
        return self._client.post(self.DM_ENDPOINT, data=form, follow_redirects=False)
