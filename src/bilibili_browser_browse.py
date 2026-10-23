"""Keep discovery interfaces and use the fixed browser for native subtitle requests."""
from __future__ import annotations

from contextlib import contextmanager, nullcontext

import httpx

from .bilibili_browser import BrowserCDP, PersistentBrowser, account_status, profile_lock, controller_lock
from .bilibili_browser_probe import capture_player
from .bilibili_browser_transport import BrowserAccountClient
from .bilibili_browse import BrowseClient, integer
from .bilibili_connector import BilibiliConnectorError
from .bilibili_diagnostics import DiagnosticLog, response_facts


class BrowserBrowseClient(BrowseClient):
    subtitle_transport = "persistent_browser_native"

    def __init__(self, account, browser, *, diagnostics, lock=None):
        super().__init__(account, diagnostics=diagnostics)
        self.browser = browser
        self.lock = lock

    def player(self, video: dict, page: dict) -> dict:
        with controller_lock(self.lock) if self.lock is not None else nullcontext():
            return self._player(video, page)

    def _player(self, video: dict, page: dict) -> dict:
        captured = capture_player(self.browser, video["bvid"], page["page"], self.diagnostics)
        if captured["reason"] != "captured":
            raise BilibiliConnectorError("固定浏览器未返回可用的原生字幕信息，未重试或回退接口")
        native = captured["video"]
        native_page = native["pages"][0]
        data = captured["player"]
        matches = (native["bvid"] == video["bvid"] and native["aid"] == video["aid"]
                   and native_page["cid"] == page["cid"] and native_page["page"] == page["page"]
                   and native_page["duration"] == page["duration"]
                   and data.get("bvid") == video["bvid"] and integer(data.get("aid")) == video["aid"]
                   and integer(data.get("cid")) == page["cid"])
        self.diagnostics.record("check", "player", check="player_identity", ok=matches)
        if not matches:
            raise BilibiliConnectorError("网页元数据、候选详情与字幕播放身份不一致")
        return data


@contextmanager
def browser_browse_client(account, binding, *, manager=None, short_locks=False):
    manager = manager if manager is not None else PersistentBrowser(binding)
    with nullcontext() if short_locks else profile_lock(manager.lock):
        with controller_lock(manager.lock) if short_locks else nullcontext():
            manager.prepare()
        diagnostics = DiagnosticLog(manager.home / "logs")
        with BrowserCDP(manager.profile) as browser:
            with controller_lock(manager.lock) if short_locks else nullcontext():
                status, headers, raw = browser.account_response()
            diagnostics.record("http_response", "nav", **response_facts(httpx.Response(status, headers=headers), raw,
                                                                        truncated=False, elapsed_ms=0))
            state, code = account_status(status, raw, binding)
            manager.save_status(state, http_status=status, business_code=code)
            diagnostics.record("check", "nav", check="account_binding", ok=state == "logged_in")
            if state != "logged_in":
                raise BilibiliConnectorError("固定浏览器登录失效、账号不符或检查被拒绝，停止预览")
            lock = manager.lock if short_locks else None
            native_account = BrowserAccountClient(browser, binding, home=manager.home, lock=lock) if account is None else account
            client = BrowserBrowseClient(native_account, browser, diagnostics=diagnostics, lock=lock)
            try:
                yield client
            finally:
                client.close()
                if account is None:
                    native_account.close()
