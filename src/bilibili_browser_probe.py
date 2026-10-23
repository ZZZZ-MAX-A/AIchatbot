"""One video page in the existing profile; capture native player data, never summarize."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import parse_qs, urlsplit

import httpx

from .bilibili_browser import BrowserCDP, MAX_BYTES, PersistentBrowser, account_status, profile_lock
from .bilibili_browse import BV, BrowseClient, integer, text
from .bilibili_connector import BilibiliConnectorError, _atomic_write
from .bilibili_diagnostics import DiagnosticLog, response_facts

PLAYER_PATH = "/x/player/wbi/v2"
NO_PLAY = """(() => {
  HTMLMediaElement.prototype.play = function() { this.pause(); return Promise.resolve(); };
  document.addEventListener('play', e => { if (e.target.pause) e.target.pause(); }, true);
})();"""


def endpoint(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.hostname == "api.bilibili.com" and parts.path == PLAYER_PATH:
        return "player"
    if parts.scheme == "https" and parts.hostname == "www.bilibili.com" and parts.path.startswith("/video/"):
        return "detail"
    return "other"


class RequestPolicy:
    """Let the page sign its own first player GET; block writes, media and retries."""

    def __init__(self, bvid: str):
        self.bvid = bvid
        self.player_requests = 0
        self.blocked = 0

    def allow(self, request: dict, resource_type: str) -> bool:
        url = str(request.get("url", ""))
        parts = urlsplit(url)
        allowed = request.get("method") in {"GET", "HEAD", "OPTIONS"}
        path = parts.path.lower()
        if resource_type == "Media" or (parts.hostname or "").endswith(".bilivideo.com"):
            allowed = False
        if any(token in path for token in ("/playurl", "/history/", "/history", "/heartbeat", "/x/click-interface/")):
            allowed = False
        if path.endswith((".m4s", ".mp4", ".flv", ".m3u8", ".mp3", ".aac")) or path == "/x/player/v2":
            allowed = False
        if endpoint(url) == "player":
            query = parse_qs(parts.query)
            if request.get("method") != "GET" or self.player_requests or query.get("bvid", [self.bvid]) != [self.bvid]:
                allowed = False
            if allowed:
                self.player_requests += 1
        if not allowed:
            self.blocked += 1
        return allowed


def response_bytes(result: dict) -> bytes:
    value = result.get("body")
    if not isinstance(value, str) or len(value) > 2 * MAX_BYTES:
        raise BilibiliConnectorError("网页响应超过读取上限")
    try:
        raw = base64.b64decode(value, validate=True) if result.get("base64Encoded") else value.encode("utf-8")
    except (ValueError, UnicodeError):
        raise BilibiliConnectorError("网页响应编码异常") from None
    if len(raw) > MAX_BYTES:
        raise BilibiliConnectorError("网页响应超过读取上限")
    return raw


def normalized_video(data: dict, bvid: str, page: int) -> dict:
    if not isinstance(data, dict) or data.get("bvid") != bvid or not integer(data.get("aid")):
        raise BilibiliConnectorError("网页视频身份无效")
    selected = data.get("selected_page")
    if (not isinstance(selected, dict) or integer(selected.get("page")) != page or
            not integer(selected.get("cid")) or not integer(selected.get("duration"))):
        raise BilibiliConnectorError("网页分 P 身份无效")
    return {"bvid": bvid, "aid": integer(data["aid"]), "title": text(data.get("title")),
            "sources": [], "total_pages": integer(data.get("total_pages")),
            "pages": [{"page": page, "cid": integer(selected["cid"]), "duration": integer(selected["duration"]),
                       "title": text(selected.get("part"))}]}


class NativeEvidence(BrowseClient):
    """Reuse the established CDN and full-track validation, with no API fallback."""

    def __init__(self, captured: dict, diagnostics: DiagnosticLog):
        self.captured = captured
        self.diagnostics = diagnostics
        self.subtitles = httpx.Client(timeout=20, follow_redirects=False)
        self._owns_subtitles = True

    def player(self, video: dict, page: dict) -> dict:
        valid = (self.captured.get("bvid") == video["bvid"] and integer(self.captured.get("aid")) == video["aid"]
                 and integer(self.captured.get("cid")) == page["cid"])
        self.diagnostics.record("check", "player", check="player_identity", ok=valid)
        if not valid:
            raise BilibiliConnectorError("网页字幕信息与视频/分 P 身份不一致")
        return self.captured


def capture_player(browser: BrowserCDP, bvid: str, page: int, log: DiagnosticLog, *, timeout: float = 40) -> dict:
    target = browser.call("Target.createTarget", {"url": "about:blank"})["targetId"]
    policy = RequestPolicy(bvid)
    try:
        session = browser.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
        browser.call("Network.enable", {"maxResourceBufferSize": MAX_BYTES, "maxTotalBufferSize": 4 * MAX_BYTES}, session)
        browser.call("Page.enable", session=session)
        browser.call("Page.addScriptToEvaluateOnNewDocument", {"source": NO_PLAY}, session)
        browser.call("Fetch.enable", {"patterns": [{"urlPattern": "*", "requestStage": "Request"}]}, session)
        browser.events.clear()
        # Fetch interception must be pumped while navigation is pending.
        browser.send_command("Page.navigate", {"url": f"https://www.bilibili.com/video/{bvid}/?p={page}"}, session)
        deadline = time.monotonic() + timeout
        responses, finished = {}, set()
        page_status = None
        while time.monotonic() < deadline:
            events, browser.events = browser.events, []
            for event in events:
                if event.get("sessionId") != session:
                    continue
                params = event.get("params", {})
                method = event.get("method")
                if method == "Fetch.requestPaused":
                    allowed = policy.allow(params.get("request", {}), params.get("resourceType", ""))
                    browser.call("Fetch.continueRequest" if allowed else "Fetch.failRequest",
                                 {"requestId": params["requestId"], **({} if allowed else {"errorReason": "BlockedByClient"})}, session)
                elif method == "Network.responseReceived":
                    response = params.get("response", {})
                    stage = endpoint(response.get("url", ""))
                    if stage == "detail" and params.get("type") == "Document":
                        page_status = int(response["status"])
                    elif stage == "player":
                        responses[params["requestId"]] = response
                elif method == "Network.loadingFinished":
                    finished.add(params["requestId"])
            for request_id, response in responses.items():
                if request_id not in finished:
                    continue
                raw = response_bytes(browser.call("Network.getResponseBody", {"requestId": request_id}, session))
                status = int(response["status"])
                log.record("http_response", "player", signed=True,
                           **response_facts(httpx.Response(status, headers=response.get("headers", {})), raw,
                                            truncated=False, elapsed_ms=0))
                result = {"page_http_status": page_status, "player_http_status": status,
                          "native_player_requests": policy.player_requests, "blocked_requests": policy.blocked}
                if status != 200:
                    return {**result, "reason": "player_http_rejected"}
                try:
                    payload = json.loads(raw)
                except (ValueError, UnicodeError, RecursionError):
                    return {**result, "reason": "player_invalid_json"}
                if not isinstance(payload, dict) or type(payload.get("code")) is not int:
                    return {**result, "reason": "player_invalid_structure"}
                result["player_business_code"] = payload["code"]
                if payload["code"] != 0 or not isinstance(payload.get("data"), dict):
                    return {**result, "reason": "player_business_error"}
                expression = """JSON.stringify((() => {
                  const v = window.__INITIAL_STATE__?.videoData;
                  if (!v) return null;
                  return {bvid:v.bvid, aid:v.aid, title:v.title, total_pages:v.pages?.length,
                          selected_page:v.pages?.[PAGE_INDEX]};
                })())""".replace("PAGE_INDEX", str(page - 1))
                snapshot = browser.call("Runtime.evaluate", {"expression": expression, "returnByValue": True}, session)
                value = snapshot.get("result", {}).get("value")
                if not isinstance(value, str) or len(value) > 65536:
                    return {**result, "reason": "page_metadata_unavailable"}
                try:
                    video = normalized_video(json.loads(value), bvid, page)
                except (ValueError, BilibiliConnectorError):
                    return {**result, "reason": "page_identity_invalid"}
                return {**result, "reason": "captured", "video": video, "player": payload["data"]}
            row = browser.receive()
            if row and "method" in row:
                browser.events.append(row)
        return {"reason": "player_not_observed", "page_http_status": page_status,
                "native_player_requests": policy.player_requests, "blocked_requests": policy.blocked}
    finally:
        try:
            browser.call("Target.closeTarget", {"targetId": target}, timeout=3)
        except BilibiliConnectorError:
            pass


def probe(manager: PersistentBrowser, bvid: str, *, page: int = 1) -> dict:
    if not isinstance(bvid, str) or not BV.fullmatch(bvid) or type(page) is not int or not 1 <= page <= 1000:
        raise BilibiliConnectorError("需要有效 BVID 和 1–1000 范围的分 P")
    with profile_lock(manager.lock):
        manager.prepare()
        log = DiagnosticLog(manager.home / "logs")
        log.record("run_start", "runtime")
        report = {"schema_version": 1, "time_utc": datetime.now(timezone.utc).isoformat(),
                  "status": "source_error", "reason": "browser_unavailable", "transport": "persistent_browser_native",
                  "bvid": bvid, "page": page, "model_calls": 0, "messages_sent": 0, "segments": 0, "characters": 0,
                  "content_reviewed": False, "share_eligible": False}
        try:
            with BrowserCDP(manager.profile) as browser:
                status, headers, raw = browser.account_response()
                log.record("http_response", "nav", **response_facts(httpx.Response(status, headers=headers), raw,
                                                                    truncated=False, elapsed_ms=0))
                state, code = account_status(status, raw, manager.binding)
                manager.save_status(state, http_status=status, business_code=code)
                log.record("check", "nav", check="account_binding", ok=state == "logged_in")
                if state != "logged_in":
                    report.update(reason=state)
                else:
                    captured = capture_player(browser, bvid, page, log)
                    report.update({key: value for key, value in captured.items() if key not in {"video", "player"}})
                    if captured["reason"] == "captured":
                        video = captured["video"]
                        source = NativeEvidence(captured["player"], log)
                        try:
                            evidence = source.evidence(video, max_pages=1)
                        finally:
                            source.close()
                        evidence["partial"] = evidence["partial"] or page != 1 or video["total_pages"] != 1
                        report.update(video=video, evidence=evidence, segments=len(evidence["segments"]), characters=evidence["characters"])
                        source_status = evidence["pages"][0]["status"]
                        report.update(status="ok" if source_status == "available" else "unavailable" if source_status in {"empty", "unavailable"} else "source_error",
                                      reason="validated_subtitles" if source_status == "available" else "no_subtitles" if source_status in {"empty", "unavailable"} else "evidence_rejected")
        except BilibiliConnectorError:
            # No protocol errors, URLs or response fragments enter the public result.
            log.record("validation_failed", "diagnose", check="response_structure", outcome="source_error")
        log.record("run_end", "diagnose", outcome=report["status"], segments=report["segments"], characters=report["characters"])
        report["diagnostics"] = log.public_status()
        report["requests"] = [{k: event[k] for k in ("stage", "http_status", "business_code", "body_kind", "body_signals") if k in event}
                              for event in log.events if event["event"] == "http_response"]
        path = manager.home / "diagnostics" / f"browser-subtitle-{log.trace_id}.json"
        _atomic_write(path, json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        public = {k: v for k, v in report.items() if k not in {"video", "evidence", "bvid", "page"}}
        return {**public, "report_path": str(path)}
