"""Public encyclopedia retrieval; no persona prompts, memories or QQ clients."""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import re
import time

import httpx

from .encyclopedia_diagnostics import capture_source_request, current_query, current_request, note_candidates


# Public facts only. Persona identity and speaking style remain in chat.
PUBLIC_ENCYCLOPEDIA_QUERY_RULE = (
    "当前用户句子中出现公共人物或角色名、作品名、技能名、剧情专名、网络梗等公共专名时，"
    "应查询相关百科词条；即使已经知道相关知识，也应查询，不以模型是否熟悉或确定作为触发条件。"
    "根据本句提到的公共名称选择候选，可用标准名称、别名及关联作品消歧；不要为了查询编造候选。"
    "不含上述公共专名的普通常识、日常问候、情绪倾诉或陪伴互动不查询。"
    "用户对当前聊天角色的称呼、私人熟人或经历、账号、密码和本机配置不作为公共词条。"
)


UNKNOWN_SLANG_TOOL: dict[str, object] = {
    "type": "function",
    "function": {
        "name": "lookup_unknown_slang",
        "description": (
            PUBLIC_ENCYCLOPEDIA_QUERY_RULE
            + "选择查询时应调用本工具取得资料，再结合当前问题自然补充相关事实。"
            "模型应在候选词中同时提供原始写法、标准名称、可能的别名或音译，以及关联作品；"
            "工具仅返回可核对的页面事实和来源信息，没有可靠资料时返回未找到。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "包含该表达的完整用户消息。",
                },
                "candidate_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "最多三个查询候选：可包含原始表达、标准中文名、别名/音译、"
                        "关联人物或作品名。对于作品剧情或专题问题，优先提供核心作品名和可能的专题页关键词。"
                    ),
                    "maxItems": 3,
                },
                "context_hint": {
                    "type": "string",
                    "description": "当前句子中与该表达相关的公共语境线索。",
                },
            },
            "required": ["query", "candidate_terms", "context_hint"],
            "additionalProperties": False,
        },
    },
}

MOEGIRL_API_URL = "https://zh.moegirl.org.cn/api.php"
MOEGIRL_USER_AGENT = "AIChatbot-TrendRAG/0.1 (contact: local administrator)"
MOEGIRL_TIMEOUT_SECONDS = 8.0
MOEGIRL_MAX_TERMS = 3
MOEGIRL_MAX_SEARCH_RESULTS = 5
MOEGIRL_MAX_EVIDENCE = 6
MOEGIRL_MAX_CONTENT_CHARS = 6000
MOEGIRL_MAX_TOTAL_CONTENT_CHARS = 8000
_PRIVATE_QUERY = re.compile(r"\d{8,}|\S+@\S+|https?://|(?:密码|密钥|token|api[_ -]?key)\s*[:：=]", re.I)


def _normalise_tool_terms(arguments: dict[str, object]) -> list[str]:
    raw_terms = arguments.get("candidate_terms", [])
    if not isinstance(raw_terms, list):
        return []
    terms: list[str] = []
    for item in raw_terms:
        value = str(item).strip()
        if value and value not in terms and not _PRIVATE_QUERY.search(value):
            terms.append(value[:80])
    return terms[:MOEGIRL_MAX_TERMS]


async def _moegirl_request(client: httpx.AsyncClient, params: dict[str, object]) -> object:
    async def trace_transport(name, _info):
        # httpcore trace info contains addresses and buffers: record no payload.
        event = current_request()
        phases = {"connect_tcp": "connect", "start_tls": "tls", "send_request_headers": "send_headers",
                  "send_request_body": "send_body", "receive_response_headers": "receive_headers",
                  "receive_response_body": "receive_body", "response_closed": "close"}
        parts = name.split(".")
        if event is not None and len(parts) >= 3 and parts[-2] in phases:
            if parts[-1] == "failed":
                event["transport_failure_phase"] = phases[parts[-2]]
            elif parts[-1] == "started" and "transport_failure_phase" not in event:
                event["transport_phase"] = phases[parts[-2]]

    response = await client.get(
        MOEGIRL_API_URL,
        params={**params, "format": "json"},
        extensions={"trace": trace_transport},
    )
    event = current_request()
    if event is not None:
        content_type = response.headers.get("content-type", "").lower()
        event.update(http_status=response.status_code, response_bytes=len(response.content),
                     content_type="json" if "json" in content_type else "html" if "html" in content_type else "text" if "text/" in content_type else "other")
    response.raise_for_status()
    try:
        data = response.json()
    except ValueError:
        if event is not None:
            event["response_kind"] = "invalid_json"
        raise
    if event is not None:
        event["response_kind"] = "object" if isinstance(data, dict) else "list" if isinstance(data, list) else "unsupported"
    if isinstance(data, dict) and "error" in data:
        if event is not None:
            event["response_kind"] = "api_error"
        error = data.get("error")
        code = error.get("code") if isinstance(error, dict) else "unknown"
        if event is not None:
            event["api_error"] = (
                "internal_api_error" if str(code).startswith("internal_api_error_") else
                code if isinstance(code, str) and code in {"maxlag", "ratelimited", "readonly", "permissiondenied", "badtitle", "missingtitle", "readapidenied"} else "unknown"
            )
        raise RuntimeError(f"萌娘百科 API error: {code}")
    if not isinstance(data, (dict, list)):
        raise ValueError("萌娘百科 API returned an unsupported response")
    return data


async def _fetch_public_data(client, params, *, phase, candidate_index):
    with capture_source_request(phase, candidate_index) as event:
        data = await _moegirl_request(client, params)
        if isinstance(data, dict):
            query = data.get("query")
            pages = query.get("pages") if isinstance(query, dict) else None
            if isinstance(pages, dict):
                event["page_count"] = len(pages)
                event["usable_pages"] = sum(isinstance(page, dict) and "missing" not in page and isinstance(page.get("extract"), str) and bool(page["extract"].strip()) for page in pages.values())
        elif phase == "search" and isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
            event["search_results"] = len(data[1])
        return data


def _page_url(title: str) -> str:
    from urllib.parse import quote

    return "https://zh.moegirl.org.cn/" + quote(title, safe="")


def _extract_pages(data: dict[str, object], requested_term: str) -> list[dict[str, object]]:
    query = data.get("query")
    pages = query.get("pages", {}) if isinstance(query, dict) else {}
    redirects = query.get("redirects", []) if isinstance(query, dict) else []
    redirect_from = {
        str(item.get("to")): str(item.get("from"))
        for item in redirects
        if isinstance(item, dict) and item.get("from") and item.get("to")
    } if isinstance(redirects, list) else {}
    results: list[dict[str, object]] = []
    if not isinstance(pages, dict):
        return results
    for page in pages.values():
        if not isinstance(page, dict) or "missing" in page:
            continue
        title = str(page.get("title", requested_term))
        content = page.get("extract", "")
        content = content if isinstance(content, str) else ""
        if not content.strip():
            continue
        results.append({
            "term": requested_term,
            "title": title,
            "pageid": page.get("pageid"),
            "content": content[:MOEGIRL_MAX_CONTENT_CHARS],
            "url": _page_url(title),
            "match_type": "redirect" if title in redirect_from else "exact",
            "redirect_from": redirect_from.get(title),
            "lastrevid": page.get("lastrevid"),
            "touched": page.get("touched"),
            "length": page.get("length"),
            "source": "moegirlpedia",
        })
    return results


async def _lookup_unknown_slang(arguments: dict[str, object]) -> dict[str, object]:
    """Look up candidate expressions in Moegirlpedia for the current turn."""
    terms = _normalise_tool_terms(arguments)
    if current_query() is not None:
        current_query()["source_timeout_ms"] = round(MOEGIRL_TIMEOUT_SECONDS * 1000)
    observed_at = datetime.now(timezone.utc).isoformat()
    if not terms:
        return {
            "status": "not_found",
            "candidate_terms": [],
            "observed_at": observed_at,
            "uncertainty": "模型没有提供可查询的候选表达。",
        }

    evidence: list[dict[str, object]] = []
    source_errors: list[str] = []
    empty_pages = False
    try:
        async with httpx.AsyncClient(
            timeout=MOEGIRL_TIMEOUT_SECONDS,
            headers={
                "User-Agent": MOEGIRL_USER_AGENT,
                "Accept": "application/json",
            },
        ) as client:
            for candidate_index, term in enumerate(terms, start=1):
                if len(evidence) >= MOEGIRL_MAX_EVIDENCE:
                    break
                exact_data = await _fetch_public_data(client, {
                    "action": "query",
                    "titles": term,
                    "redirects": 1,
                    "prop": "info|extracts",
                    "explaintext": 1,
                }, phase="exact", candidate_index=candidate_index)
                exact_pages = (
                    _extract_pages(exact_data, term)
                    if isinstance(exact_data, dict)
                    else []
                )
                if isinstance(exact_data, dict):
                    raw_pages = exact_data.get("query", {}).get("pages", {})
                    if isinstance(raw_pages, dict) and not exact_pages:
                        empty_pages = empty_pages or any(isinstance(p, dict) and "missing" not in p for p in raw_pages.values())
                if exact_pages:
                    evidence.extend(exact_pages[:1])
                    if current_query() is not None:
                        current_query()["evidence_collected"] = len(evidence)
                    continue

                search_data = await _fetch_public_data(client, {
                    "action": "opensearch",
                    "search": term,
                    "limit": MOEGIRL_MAX_SEARCH_RESULTS,
                    "namespace": 0,
                }, phase="search", candidate_index=candidate_index)
                search_titles = (
                    search_data[1]
                    if isinstance(search_data, list) and len(search_data) > 1
                    else []
                )
                if not isinstance(search_titles, list):
                    continue
                for title in [str(item).strip() for item in search_titles[:MOEGIRL_MAX_SEARCH_RESULTS] if str(item).strip()]:
                    if len(evidence) >= MOEGIRL_MAX_EVIDENCE:
                        break
                    if any(item.get("title") == title for item in evidence):
                        continue
                    page_data = await _fetch_public_data(client, {
                        "action": "query",
                        "titles": title,
                        "redirects": 1,
                        "prop": "info|extracts",
                        "explaintext": 1,
                    }, phase="search_page", candidate_index=candidate_index)
                    pages = (
                        _extract_pages(page_data, term)
                        if isinstance(page_data, dict)
                        else []
                    )
                    if pages:
                        pages[0]["match_type"] = "opensearch"
                        evidence.append(pages[0])
                        if current_query() is not None:
                            current_query()["evidence_collected"] = len(evidence)
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        source_errors.append(type(exc).__name__)

    if evidence:
        remaining = MOEGIRL_MAX_TOTAL_CONTENT_CHARS
        bounded = []
        for item in evidence:
            if remaining <= 0:
                break
            item["content"] = str(item["content"])[:remaining]
            remaining -= len(item["content"])
            bounded.append(item)
        evidence = bounded
        status = "partial" if source_errors else "found"
        return {
            "status": status,
            "candidate_terms": terms,
            "results": evidence,
            "observed_at": observed_at,
            "source_errors": source_errors,
            "uncertainty": "词条内容是公共背景证据，不代表用户当前一定在引用该词条。",
        }
    return {
        "status": "source_unavailable" if source_errors else "no_content" if empty_pages else "not_found",
        "candidate_terms": terms,
        "observed_at": observed_at,
        "source_errors": source_errors,
        "uncertainty": (
            "萌娘百科查询失败，不能据此确认表达含义。"
            if source_errors else "萌娘百科返回了页面，但没有可用正文，不能据此确认。"
            if empty_pages else "萌娘百科没有找到可核对的页面。"
        ),
    }


class EncyclopediaService:
    """Bounded process cache of public evidence; no chat text or disk writes."""

    def __init__(self, *, ttl_seconds: float = 1800, max_entries: int = 128):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._cache: OrderedDict[tuple[str, ...], tuple[float, dict[str, object]]] = OrderedDict()

    async def lookup(self, arguments: dict[str, object]) -> dict[str, object]:
        terms = _normalise_tool_terms(arguments)
        note_candidates(terms)
        diagnostics = current_query()
        key = tuple(term.casefold() for term in terms)
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached is not None and now - cached[0] < self.ttl_seconds:
            self._cache.move_to_end(key)
            result = deepcopy(cached[1])
            result["cache_hit"] = True
            if diagnostics is not None:
                diagnostics.update(cache="hit", evidence_collected=len(result.get("results", [])))
            return result
        if cached is not None:
            del self._cache[key]
        if diagnostics is not None:
            diagnostics["cache"] = "miss"
        result = await _lookup_unknown_slang({"candidate_terms": terms})
        result["cache_hit"] = False
        if key and result.get("status") == "found":
            self._cache[key] = (now, deepcopy(result))
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)
        return result


PUBLIC_ENCYCLOPEDIA_SERVICE = EncyclopediaService()
