"""Bounded, read-only video discovery and evidence-based local previews.

This module never sends messages, plays videos or updates watch history. The
account transport is shared with the connector; browsing is implemented here.
"""
from __future__ import annotations

from datetime import datetime, timezone
import html
import hashlib
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Protocol
from urllib.parse import urlencode, urlsplit
import uuid

import httpx

from .bilibili_connector import (
    BilibiliBinding, BilibiliClient, BilibiliConnectorError, _atomic_write,
    connector_home,
)
from .bilibili_diagnostics import DiagnosticLog, response_facts

BV = re.compile(r"BV[0-9A-Za-z]{10}\Z")
MAX_BYTES = 2 * 1024 * 1024
MIXIN_ORDER = (46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,
               29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,
               25,54,21,56,59,6,63,57,62,11,36,20,34,44,52)


def sign_wbi(params: dict, image_key: str, sub_key: str, timestamp: int) -> dict:
    if not re.fullmatch(r"[0-9a-f]{32}", image_key) or not re.fullmatch(r"[0-9a-f]{32}", sub_key):
        raise BilibiliConnectorError("WBI 签名键格式无效")
    combined = image_key + sub_key
    mixed = "".join(combined[n] for n in MIXIN_ORDER)[:32]
    data = {k: re.sub(r"[!'()*]", "", str(v)) for k, v in {**params, "wts": timestamp}.items()}
    data = dict(sorted(data.items()))
    data["w_rid"] = hashlib.md5((urlencode(data) + mixed).encode(), usedforsecurity=False).hexdigest()
    return data


def text(value: Any, limit: int = 200) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", " ", html.unescape(str(value or "")))[:limit].strip()


def integer(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def markdown_text(value: str) -> str:
    """Render external text literally, including image/HTML-like video titles."""
    return re.sub(r"([\\`*{}\[\]()<>_#!|])", r"\\\1", value)


def _bounded_json(client: httpx.Client, url: str, *, diagnostics: DiagnosticLog | None = None,
                  stage: str = "other", **kwargs: Any) -> dict:
    """Stream with a decoded-byte cap, including compressed responses."""
    started = time.monotonic()
    params = kwargs.get("params", {})
    request_facts = {"parameter_names": list(params), "signed": "w_rid" in params}
    try:
        with client.stream("GET", url, follow_redirects=False, **kwargs) as response:
            raw = bytearray()
            cap = MAX_BYTES if response.status_code == 200 else 65536
            truncated = False
            for chunk in response.iter_bytes(chunk_size=65536):
                room = cap - len(raw)
                raw.extend(chunk[:room])
                if len(chunk) > room:
                    truncated = True
                    break
            outcome = "http_rejected" if response.status_code != 200 else "too_large" if truncated else "ok"
            if diagnostics:
                facts = response_facts(response, raw, truncated=truncated, elapsed_ms=int((time.monotonic() - started) * 1000))
                if outcome == "ok" and facts["body_kind"] != "json":
                    outcome = "invalid_json"
                diagnostics.record("http_response", stage, **request_facts, **facts, outcome=outcome)
            if response.status_code != 200:
                raise BilibiliConnectorError(f"读取失败：HTTP {response.status_code}")
            if truncated:
                raise BilibiliConnectorError("响应超过读取上限")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            return data
    except httpx.HTTPError as exc:
        if diagnostics:
            kind = "timeout" if isinstance(exc, httpx.TimeoutException) else "proxy" if isinstance(exc, httpx.ProxyError) else (
                "connect" if isinstance(exc, httpx.ConnectError) else "transport")
            diagnostics.record("http_error", stage, **request_facts, outcome="network_error", error_kind=kind,
                               elapsed_ms=int((time.monotonic() - started) * 1000))
        raise BilibiliConnectorError("读取失败：网络或 JSON 格式错误") from exc
    except (ValueError, UnicodeError, RecursionError) as exc:
        if diagnostics:
            diagnostics.record("validation_failed", stage, check="response_structure", outcome="invalid_json")
        raise BilibiliConnectorError("读取失败：网络或 JSON 格式错误") from exc


class BrowseClient:
    def __init__(self, account: BilibiliClient, *, subtitles: httpx.Client | None = None,
                 diagnostics: DiagnosticLog | None = None):
        self.account_client = account
        self.diagnostics = diagnostics if diagnostics is not None else DiagnosticLog()
        # Separate client: account cookies must never reach a CDN.
        self.subtitles = subtitles or httpx.Client(timeout=20, follow_redirects=False)
        self._owns_subtitles = subtitles is None
        self._wbi_keys: tuple[str, str] | None = None
        self.diagnostics.record("run_start", "runtime")

    def close(self) -> None:
        if self._owns_subtitles:
            self.subtitles.close()

    def player(self, video: dict, page: dict) -> dict:
        """Use the signed player endpoint only; never fall back to legacy v2."""
        if self._wbi_keys is None:
            navigation = self.get("/x/web-interface/nav", {})
            if navigation.get("isLogin") is not True:
                self.diagnostics.record("validation_failed", "nav", check="login_state", ok=False)
                raise BilibiliConnectorError("字幕读取前登录态检查失败")
            images = navigation.get("wbi_img") or {}
            keys = tuple(urlsplit(str(images.get(name, ""))).path.rsplit("/", 1)[-1].split(".")[0]
                         for name in ("img_url", "sub_url"))
            self._wbi_keys = keys
        try:
            params = sign_wbi({"aid": video["aid"], "bvid": video["bvid"], "cid": page["cid"]},
                              *self._wbi_keys, int(time.time()))
        except BilibiliConnectorError:
            self.diagnostics.record("validation_failed", "player", check="player_signing", error_kind="signing", ok=False)
            raise
        encoded = str(httpx.Request("GET", self.account_client.API_BASE + "/x/player/wbi/v2", params=params).url.query, "ascii")
        encoding_ok = encoded == urlencode(params)
        self.diagnostics.record("check", "player", check="signing_encoding", ok=encoding_ok)
        if not encoding_ok:
            raise BilibiliConnectorError("签名参数与请求编码不一致")
        data = self.get("/x/player/wbi/v2", params)
        identity_ok = (data.get("bvid") == video["bvid"] and integer(data.get("aid")) == video["aid"] and
                       integer(data.get("cid")) == page["cid"])
        self.diagnostics.record("check" if identity_ok else "validation_failed", "player", check="player_identity", ok=identity_ok)
        if not identity_ok:
            raise BilibiliConnectorError("字幕播放信息与视频/分 P 身份不一致")
        return data

    def get(self, path: str, params: dict) -> dict:
        stage = {"/x/web-interface/nav": "nav", "/x/web-interface/view": "detail", "/x/player/wbi/v2": "player",
                 "/x/web-interface/wbi/index/top/feed/rcmd": "home", "/x/polymer/web-dynamic/v1/feed/all": "following"}.get(path, "other")
        payload = _bounded_json(self.account_client._client, self.account_client.API_BASE + path,
                                params=params, headers=self.account_client.headers, diagnostics=self.diagnostics, stage=stage)
        if type(payload.get("code")) is not int or payload["code"] != 0:
            self.diagnostics.record("validation_failed", stage, check="business_code", outcome="business_error",
                                    business_code=payload.get("code"))
            raise BilibiliConnectorError("B 站业务响应失败（登录态、风控或接口变更）")
        if not isinstance(payload.get("data"), dict):
            self.diagnostics.record("validation_failed", stage, check="response_structure", error_kind="structure")
            raise BilibiliConnectorError("B 站 data 格式异常")
        return payload["data"]

    def verify_binding(self, binding: BilibiliBinding) -> None:
        binding.validate()
        navigation = self.get("/x/web-interface/nav", {})
        logged_in = navigation.get("isLogin") is True
        matches = str(navigation.get("mid")) == binding.aike_mid
        self.diagnostics.record("check" if logged_in else "validation_failed", "nav", check="login_state", ok=logged_in)
        self.diagnostics.record("check" if matches else "validation_failed", "nav", check="account_binding", ok=matches)
        if not logged_in or not matches:
            raise BilibiliConnectorError("登录态无效或账号与绑定的爱可 UID 不一致，停止浏览")

    def discover(self, binding: BilibiliBinding, per_source: int = 6, *, refresh_index: int = 1) -> dict:
        binding.validate()
        if not 1 <= per_source <= 8:
            raise BilibiliConnectorError("每个来源数量须为 1–8")
        if type(refresh_index) is not int or not 1 <= refresh_index <= 1000000:
            raise BilibiliConnectorError("推荐刷新序号无效")
        self.verify_binding(binding)
        candidates: dict[str, dict] = {}
        sources = {}
        for source, path, params in (
            ("home", "/x/web-interface/wbi/index/top/feed/rcmd", {"ps": per_source, "fresh_type": 3, "fresh_idx": refresh_index}),
            ("following", "/x/polymer/web-dynamic/v1/feed/all", {"type": "video"}),
        ):
            try:
                data = self.get(path, params)
                rows = data.get("item" if source == "home" else "items")
                if not isinstance(rows, list):
                    raise BilibiliConnectorError("候选列表格式异常")
                normalized = normalize_feed(source, rows)[:per_source]
                sources[source] = {"status": "ok" if normalized else "empty", "returned": len(rows), "accepted": len(normalized)}
                for item in normalized:
                    if item["bvid"] in candidates:
                        candidates[item["bvid"]]["sources"].append(source)
                    else:
                        candidates[item["bvid"]] = item
            except (BilibiliConnectorError, TypeError, AttributeError):
                sources[source] = {"status": "error", "error": "候选读取失败；请检查登录态、风控或接口格式"}
        return {"sources": sources, "candidates": list(candidates.values())}

    def detail(self, candidate: dict) -> dict:
        bvid = candidate["bvid"]
        data = self.get("/x/web-interface/view", {"bvid": bvid})
        if data.get("bvid") != bvid or not integer(data.get("aid")) or not isinstance(data.get("pages"), list):
            raise BilibiliConnectorError("视频详情标识或分 P 格式异常")
        pages = []
        for index, page in enumerate(data["pages"]):
            if not isinstance(page, dict) or not integer(page.get("cid")):
                raise BilibiliConnectorError("视频分 P 格式异常")
            pages.append({"page": index + 1, "cid": integer(page["cid"]),
                          "title": text(page.get("part")), "duration": integer(page.get("duration"))})
        if not pages:
            raise BilibiliConnectorError("视频没有可读分 P")
        owner = data.get("owner")
        if not isinstance(owner, dict):
            raise BilibiliConnectorError("视频作者格式异常")
        return {"bvid": bvid, "aid": integer(data["aid"]), "url": f"https://www.bilibili.com/video/{bvid}",
                "sources": candidate["sources"], "title": text(data.get("title")),
                "description": text(data.get("desc"), 2000),
                "uploader": text(owner.get("name"), 80),
                "category": text(data.get("tname"), 80), "duration": integer(data.get("duration")),
                "pages": pages, "detail_status": "ok"}

    def evidence(self, video: dict, *, max_pages: int = 2, char_budget: int = 12000) -> dict:
        if not 1 <= max_pages <= 2 or not 1 <= char_budget <= 12000:
            raise BilibiliConnectorError("字幕预算超出限制")
        pages, segments, remaining = [], [], char_budget
        for page in video["pages"][:max_pages]:
            if remaining <= 0:
                break
            info = {"page": page["page"], "status": "unavailable", "language": "", "automatic": False,
                    "truncated": False, "last_caption_end": 0.0, "duration": page["duration"],
                    "identity_verified": False, "endpoint": "/x/player/wbi/v2"}
            pages.append(info)
            try:
                player = self.player(video, page)
                info["identity_verified"] = True
                tracks = (player.get("subtitle") or {}).get("subtitles", [])
                if not isinstance(tracks, list):
                    raise BilibiliConnectorError("字幕轨格式异常")
                tracks = [t for t in tracks if isinstance(t, dict) and t.get("subtitle_url")]
                if not tracks:
                    continue
                tracks.sort(key=lambda t: (not str(t.get("lan", "")).startswith(("zh", "ai-zh")), bool(t.get("ai_type"))))
                track = tracks[0]
                url = safe_subtitle_url(track["subtitle_url"])
                body = _bounded_json(self.subtitles, url, headers={"User-Agent": BilibiliClient.USER_AGENT},
                                     diagnostics=self.diagnostics, stage="subtitle_cdn")
                entries = body.get("body")
                if not isinstance(entries, list):
                    raise BilibiliConnectorError("字幕正文格式异常")
                normalized = []
                previous_start = -1.0
                for entry in entries:
                    if not isinstance(entry, dict):
                        raise BilibiliConnectorError("字幕条目格式异常")
                    start, end = float(entry.get("from", -1)), float(entry.get("to", -1))
                    if (not math.isfinite(start) or not math.isfinite(end) or not 0 <= start <= end or
                            start + 0.05 < previous_start or page["duration"] <= 0 or
                            end > page["duration"] + max(3, page["duration"] * 0.02)):
                        self.diagnostics.record("validation_failed", "evidence", check="subtitle_timeline", error_kind="timeline")
                        raise BilibiliConnectorError("字幕时间轴超出分 P 时长或顺序异常")
                    previous_start = start
                    normalized.append((start, end, text(entry.get("content"), char_budget + 1)))
                info.update(track_fingerprint=hashlib.sha256(json.dumps(entries, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                            track_lines=len(entries), track_last_end=max((r[1] for r in normalized), default=0.0))
                info.update(language=text(track.get("lan"), 30), automatic=bool(track.get("ai_type")) or str(track.get("lan", "")).startswith("ai-"))
                for start, end, content in normalized:
                    if not content:
                        continue
                    if len(content) > remaining:
                        info["truncated"] = True
                        break
                    segments.append({"id": f"S{len(segments) + 1}", "page": page["page"],
                                     "start": start, "end": end, "text": content})
                    remaining -= len(content)
                    info["last_caption_end"] = end
                info["status"] = "available" if any(s["page"] == page["page"] for s in segments) else "empty"
                self.diagnostics.record("check", "evidence", check="subtitle_timeline", ok=True)
            except (BilibiliConnectorError, TypeError, ValueError, OverflowError, AttributeError, KeyError) as exc:
                # Discard partially parsed failed tracks rather than presenting them as complete.
                removed = [s for s in segments if s["page"] == page["page"]]
                remaining += sum(len(s["text"]) for s in removed)
                segments[:] = [s for s in segments if s["page"] != page["page"]]
                info.update(status="error", last_caption_end=0.0,
                            error=str(exc) if isinstance(exc, BilibiliConnectorError) else "字幕数据结构异常")
                self.diagnostics.record("validation_failed", "evidence", check="evidence", ok=False)
        partial = len(pages) != len(video["pages"]) or any(p["status"] != "available" or p["truncated"] for p in pages)
        return {"basis": "subtitles" if segments else "metadata_only", "partial": partial,
                "total_pages": len(video["pages"]), "pages": pages, "segments": segments,
                "characters": char_budget - remaining, "visuals_reviewed": False,
                "full_video_understanding": False, "provenance_version": 2}


def safe_subtitle_url(value: str) -> str:
    url = "https:" + value if value.startswith("//") else value
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or
        not parsed.hostname.endswith(".hdslb.com") or parsed.username or parsed.password or
        parsed.port not in (None, 443) or parsed.fragment):
        raise BilibiliConnectorError("字幕地址不在允许的 HTTPS CDN 范围")
    return url


def diagnose(client: BrowseClient, binding: BilibiliBinding, bvid: str, *, page: int = 1) -> dict:
    """One read-only source trace, without discovery, memory, model calls or sends."""
    from urllib.request import getproxies

    if not BV.fullmatch(bvid) or type(page) is not int or not 1 <= page <= 1000:
        raise BilibiliConnectorError("诊断需要有效 BVID 和 1–1000 范围的分 P")
    log = client.diagnostics
    proxies = getproxies()
    log.record("check", "runtime", proxy_configured=any(proxies.get(k) for k in ("http", "https", "all")),
               http_proxy_configured=bool(proxies.get("http")), https_proxy_configured=bool(proxies.get("https")),
               all_proxy_configured=bool(proxies.get("all")), no_proxy_configured=bool(proxies.get("no")),
               trust_env=client.account_client._client.trust_env)
    result = {"status": "error", "model_calls": 0, "messages_sent": 0, "segments": 0, "characters": 0}
    try:
        client.verify_binding(binding)
        video = client.detail({"bvid": bvid, "sources": []})
        if page > len(video["pages"]):
            raise BilibiliConnectorError("视频不存在指定分 P")
        video["pages"] = [video["pages"][page - 1]]
        evidence = client.evidence(video, max_pages=1)
        status = evidence["pages"][0]["status"]
        result.update(status="source_error" if status == "error" else "ok" if status == "available" else "unavailable",
                      segments=len(evidence["segments"]), characters=evidence["characters"])
    except BilibiliConnectorError:
        # The log already identifies the failing stage; do not serialize exception text.
        result["status"] = "source_error"
    log.record("run_end", "diagnose", outcome=result["status"], segments=result["segments"], characters=result["characters"])
    result["diagnostics"] = log.public_status()
    result["requests"] = [{k: event[k] for k in ("stage", "http_status", "business_code", "body_kind", "body_signals",
                          "outcome", "server_clock_delta_seconds", "error_kind") if k in event}
                          for event in log.events if event["event"] in {"http_response", "http_error"}]
    result["checks"] = [{"check": event["check"], "ok": event["ok"]} for event in log.events
                        if event["event"] in {"check", "validation_failed"} and "check" in event and "ok" in event]
    return result


def normalize_feed(source: str, rows: list) -> list[dict]:
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if source == "home":
            if row.get("goto") != "av" or row.get("business_info") or row.get("is_ad"):
                continue
            video = row
        else:
            if row.get("type") != "DYNAMIC_TYPE_AV":
                continue
            major = ((row.get("modules") or {}).get("module_dynamic") or {}).get("major") or {}
            video = major.get("archive") or {}
        bvid = video.get("bvid", "")
        if not isinstance(bvid, str) or not BV.fullmatch(bvid) or bvid in seen:
            continue
        seen.add(bvid)
        result.append({"bvid": bvid, "title": text(video.get("title")), "sources": [source]})
    return result


class JsonModel(Protocol):
    usage: list[dict]
    model: str

    def ask(self, task: str, data: dict) -> dict: ...


def validate_selection(payload: dict, candidates: list[dict], maximum: int) -> list[dict]:
    decisions = payload.get("decisions")
    expected = {c["bvid"] for c in candidates}
    if not isinstance(decisions, list) or len(decisions) != len(expected):
        raise BilibiliConnectorError("筛选结果没有覆盖全部候选")
    seen, selected = set(), 0
    for item in decisions:
        if (not isinstance(item, dict) or not isinstance(item.get("bvid"), str) or item["bvid"] not in expected or item["bvid"] in seen or
            type(item.get("select")) is not bool or not isinstance(item.get("reason"), str) or
            not 1 <= len(item["reason"].strip()) <= 240):
            raise BilibiliConnectorError("筛选结果格式或视频标识无效")
        seen.add(item["bvid"])
        selected += item["select"]
    if selected > maximum:
        raise BilibiliConnectorError("筛选结果超出视频数量预算")
    return decisions


def validate_summary(payload: dict, evidence: dict) -> dict:
    alignment = payload.get("content_alignment")
    reason = payload.get("alignment_reason")
    if (not isinstance(alignment, str) or alignment not in {"consistent", "uncertain", "mismatch"} or not isinstance(reason, str) or
            not 1 <= len(reason.strip()) <= 240):
        raise BilibiliConnectorError("总结缺少视频与字幕内容一致性判断")
    if alignment != "consistent":
        if payload.get("worth_sharing") is not False or payload.get("claims") != []:
            raise BilibiliConnectorError("来源不一致或不确定时不得输出内容总结")
        return {"worth_sharing": False, "why_share": "字幕与视频内容无法确认一致，不生成分享。",
                "claims": [], "content_alignment": alignment, "alignment_reason": reason}
    claims = payload.get("claims")
    impression = payload.get("viewing_impression", "")
    if not isinstance(impression, str) or len(impression.strip()) > 100:
        raise BilibiliConnectorError("观影感想格式无效")
    if (type(payload.get("worth_sharing")) is not bool or not isinstance(payload.get("why_share"), str) or
        not 1 <= len(payload["why_share"].strip()) <= 100 or not isinstance(claims, list) or not 1 <= len(claims) <= 3):
        raise BilibiliConnectorError("总结格式无效")
    lookup = {s["id"]: s for s in evidence["segments"]}
    for claim in claims:
        if not isinstance(claim, dict):
            raise BilibiliConnectorError("总结论据格式无效")
        statement, quote, source = claim.get("text"), claim.get("quote"), claim.get("segment_id")
        if (not isinstance(statement, str) or not 1 <= len(statement.strip()) <= 160 or
            not isinstance(quote, str) or not 4 <= len(quote.strip()) <= 200 or
            not isinstance(source, str) or source not in lookup or quote not in lookup[source]["text"]):
            raise BilibiliConnectorError("总结缺少可核对的字幕引用")
    return {"worth_sharing": payload["worth_sharing"], "why_share": payload["why_share"], "claims": claims,
            "content_alignment": alignment, "alignment_reason": reason, "viewing_impression": impression.strip()}


def share_draft(video: dict, summary: dict, evidence: dict) -> str:
    """Send the persona's message and link; retain evidence in the local report."""
    return f"{summary['why_share'].strip()}\n{video['url']}"


def preview(client: BrowseClient, binding: BilibiliBinding, model: JsonModel | None = None,
            *, per_source: int = 6, max_selected: int = 2, refresh_index: int = 1,
            seen_bvids: set[str] | None = None) -> dict:
    if not 1 <= max_selected <= 2:
        raise BilibiliConnectorError("单次精选数量须为 1–2")
    report = (client.discover(binding, per_source) if refresh_index == 1
              else client.discover(binding, per_source, refresh_index=refresh_index))
    report["skipped_seen"] = sum(c["bvid"] in (seen_bvids or set()) for c in report["candidates"])
    report["candidates"] = [c for c in report["candidates"] if c["bvid"] not in (seen_bvids or set())]
    report["refresh_index"] = refresh_index
    memory_status = model.memory_status() if model and hasattr(model, "memory_status") else {"enabled": False, "status": "disabled"}
    report.update(schema_version=3, run_id=uuid.uuid4().hex,
                  created_at=datetime.now(timezone.utc).isoformat(), mode="preview" if model else "inspect",
                  messages_sent=0, qq_memories_loaded=memory_status.get("status") == "loaded",
                  qq_memory=memory_status, subtitle_transport=getattr(client, "subtitle_transport", "api"), results=[], errors=[])
    candidates = []
    for candidate in report["candidates"]:
        try:
            candidates.append(client.detail(candidate))
        except BilibiliConnectorError:
            candidates.append({**candidate, "detail_status": "error"})
    report["candidates"] = candidates
    available = [c for c in candidates if c["detail_status"] == "ok"]
    if model and available:
        try:
            raw = model.ask("select", {"max_selected": max_selected, "candidates": available})
            decisions = validate_selection(raw, available, max_selected)
            by_id = {d["bvid"]: d for d in decisions}
            for candidate in available:
                candidate["decision"] = by_id[candidate["bvid"]]
            for candidate in available:
                if not candidate["decision"]["select"]:
                    continue
                evidence = client.evidence(candidate)
                result = {"bvid": candidate["bvid"], "title": candidate["title"], "url": candidate["url"],
                          "selection_reason": candidate["decision"]["reason"], "evidence": evidence,
                          "status": "metadata_only", "draft": "", "eligible_to_share": False}
                report["results"].append(result)
                if evidence["basis"] == "metadata_only":
                    result["note"] = "只有标题/简介依据；无可用字幕，尚未生成内容总结。"
                    if any(p["status"] == "error" for p in evidence["pages"]):
                        result.update(status="source_error", note="字幕来源或读取异常，停止总结和分享")
                    continue
                if any(p["status"] == "error" for p in evidence["pages"]):
                    result.update(status="source_error", note="部分分 P 字幕来源异常，停止本视频总结和分享")
                    continue
                try:
                    # Compact tuples keep timestamped evidence but avoid repeating
                    # object keys for hundreds of subtitle lines in model input.
                    compact = {k: v for k, v in evidence.items() if k != "segments"}
                    compact["segment_columns"] = ["id", "page", "start", "end", "text"]
                    compact["segments"] = [[s[k] for k in compact["segment_columns"]] for s in evidence["segments"]]
                    summary = validate_summary(model.ask("summarize", {"video": candidate, "evidence": compact}), evidence)
                    client.diagnostics.record("check", "summary", check="content_alignment",
                                              ok=summary["content_alignment"] == "consistent",
                                              content_alignment=summary["content_alignment"], worth_sharing=summary["worth_sharing"])
                    result.update(summary=summary, status="summarized", eligible_to_share=summary["worth_sharing"],
                                  reviewed_at=datetime.now(timezone.utc).isoformat())
                    if summary["content_alignment"] != "consistent":
                        result.update(status="source_" + summary["content_alignment"],
                                      note=summary["alignment_reason"])
                        continue
                    if not summary["worth_sharing"]:
                        result.update(status="not_recommended", note="模型已否决分享，保留判断供排查，不生成分享草稿")
                        continue
                    result["draft"] = share_draft(candidate, summary, evidence)
                except BilibiliConnectorError:
                    client.diagnostics.record("validation_failed", "summary", check="summary_structure", ok=False)
                    result.update(status="summary_error", note="模型总结或引用校验失败，未生成分享草稿")
        except BilibiliConnectorError:
            client.diagnostics.record("validation_failed", "selection", check="selection_structure", ok=False)
            report["errors"].append("模型筛选或结构校验失败，未生成精选")
    report["model"] = model.model if model else None
    report["usage"] = list(model.usage) if model else []
    report["status"] = "error" if (report["errors"] or all(s["status"] == "error" for s in report["sources"].values()) or
                                  any(r["status"] in {"summary_error", "source_error", "source_mismatch", "source_uncertain"} for r in report["results"]) or
                                  (candidates and not available)) else "ok"
    if report["status"] == "ok" and (any(s["status"] == "error" for s in report["sources"].values()) or
                                      any(c["detail_status"] == "error" for c in candidates)):
        report["status"] = "partial"
    client.diagnostics.record("run_end", "preview", outcome="source_error" if report["status"] == "error" else report["status"])
    report["diagnostics"] = client.diagnostics.public_status()
    return report


def save_report(report: dict, directory: Path | None = None) -> tuple[Path, Path]:
    directory = directory or connector_home() / "previews"
    stem = report["created_at"][:10] + "-" + report["run_id"]
    json_path, md_path = directory / (stem + ".json"), directory / (stem + ".md")
    lines = ["# 爱可 B 站浏览预览", "", f"时间：{report['created_at']}",
             f"状态：{report['status']}；模式：{report['mode']}；平台报告发送成功：{report.get('messages_sent', 0)}", "",
             "本轮只读取推荐、详情与字幕，未播放画面。", "",
             "QQ 记忆状态：" + json.dumps(report.get("qq_memory", {"enabled": False, "status": "disabled"}), ensure_ascii=False),
             "记忆正文只用于本轮模型上下文，不另存到报告。用量中的 QQ 记忆 token 为本地粗估，供应商输入 token 才是实际整包用量。", "", "## 来源", ""]
    if report.get("withdrawal_reason"):
        lines[2:2] = ["**本报告已撤回，原总结及分享草稿不可作为视频内容依据。**", "",
                      markdown_text(report["withdrawal_reason"]), ""]
    for name, source in report["sources"].items():
        lines.append(f"- {name}: {source['status']}；候选 {source.get('accepted', 0)}")
    lines += ["", "## 候选和选择理由", ""]
    for candidate in report["candidates"]:
        decision = candidate.get("decision")
        reason = ("选中：" if decision["select"] else "略过：") + decision["reason"] if decision else "未筛选 / 详情读取失败"
        lines.append(f"- {markdown_text(text(candidate['title']))} ({candidate['bvid']}) — {markdown_text(text(reason, 300))}")
    for result in report["results"]:
        ev = result["evidence"]
        lines += ["", f"## {markdown_text(text(result['title']))}", "", result["url"], "",
                  f"状态：{result['status']}；值得分享：{result['eligible_to_share']}；依据：{ev['basis']}；字幕读取范围不完整：{ev['partial']}", "",
                  result.get("note", ""), "", "分享正文（提交情况见私信状态）：", "", markdown_text(result["draft"]), "", "字幕覆盖与引用：", ""]
        for page in ev["pages"]:
            lines.append(f"- P{page['page']}: {page['status']}，{page['language']}，自动字幕={page['automatic']}，截断={page['truncated']}，末条结束={page['last_caption_end']}s / 分P时长={page['duration']}s")
            if page.get("error"):
                lines.append("  读取错误：" + markdown_text(page["error"]))
        summary = result.get("summary", {})
        if summary.get("content_alignment"):
            lines.append("- 视频/字幕主题一致性：" + summary["content_alignment"] + "；" + markdown_text(summary["alignment_reason"]))
        segments = {s["id"]: s for s in ev["segments"]}
        for claim in result.get("summary", {}).get("claims", []):
            s = segments[claim["segment_id"]]
            lines.append(f"- {markdown_text(text(claim['text']))} [P{s['page']} {s['start']}–{s['end']}s {s['id']}] 引用：{markdown_text(text(claim['quote']))}")
    if report.get("delivery"):
        lines += ["", "## 私信提交状态", "", json.dumps(report["delivery"], ensure_ascii=False),
                  "主人已确认实际收到。" if report["delivery"].get("owner_received_confirmed") is True
                  else "平台报告成功不代表主人已确认实际收到。"]
    if "daily_note" in report:
        lines += ["", "## 今日观影小记状态", "", json.dumps(report["daily_note"], ensure_ascii=False),
                  "小记独立留在本机，只记录有依据的字幕阅读内容，不表示实际发送私信。"]
    lines += ["", "## 模型用量", "", json.dumps(report["usage"], ensure_ascii=False), "", *report["errors"], ""]
    _atomic_write(json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    _atomic_write(md_path, "\n".join(lines))
    return json_path, md_path
