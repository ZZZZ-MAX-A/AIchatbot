"""Executable public-knowledge subgraph used by character chat only."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
import json
import re
import time

from ..encyclopedia import PUBLIC_ENCYCLOPEDIA_SERVICE
from ..encyclopedia_diagnostics import capture_query, note_candidates, wait_for_budget
from ..failure_diagnostics import classify_failure
from ..policy.risk import RiskLevel
from .tool_registry import ToolArgumentError, ToolContext, ToolRegistry, ToolResult, ToolSpec


class EncyclopediaNode(str, Enum):
    PLAN_QUERY = "plan_public_query"
    VALIDATE_REQUEST = "validate_encyclopedia_request"
    EXECUTE_LOOKUP = "execute_public_encyclopedia"
    BUILD_EVIDENCE = "build_encyclopedia_evidence"


_TRIVIAL_MESSAGE = re.compile(r"^(?:你好|您好|嗨|哈喽|早安|午安|晚安|早上好|晚上好|谢谢|谢谢你|好的|好|嗯|嗯嗯|哦|噢|收到|知道了|明白了|再见|拜拜|在吗|我回来了)[呀啊呢啦哦嘛吧！!。.,，~～\s]*$")
_EXPLICIT_LOOKUP = re.compile(r"查(?:一下|一查|查|询|找)|搜(?:一下|一搜|搜|索)|百科|词条|什么意思|是什么梗|谁是|是谁|什么角色|哪个作品|知不知道|知道.+[吗么嘛?？]|听(?:没听)?过|听说过")
_DIRECT_TERM = re.compile(r"^(?:(?:请|帮我|麻烦|爱可|凛音)[，,\s]*)*(?:查一下|查查|查询|搜索|搜一下|查一查)\s*[‘“「『\"]?([^\n？?！!，,。]{2,40}?)[’”」』\"]?(?:的(?:百科|词条|资料))?[。！!？?\s]*$")
_DIRECT_QUESTION = re.compile(
    r"^(?:(?:没有就|那就|就是|只是)?考考(?:爱可|凛音|你)[，,。\s]*)?"
    r"(?:(?:那|那么|对了|请问|话说)[，,\s]*)?"
    r"(?:爱可|凛音|你)(?:知不知道|知道|听没听过|有没有听说过|听说过|听过|了不了解|了解)\s*(.+)$"
)
_PRIVATE_OR_CONTEXTUAL_TERM = re.compile(
    r"的|怎么|如何|为什么|是谁|是什么|哪些|多少|吗|我|你|主人|今天|昨天|最近|"
    r"现在|几点|日期|日子|星期|天气|心情|感觉|事情|答案|秘密|住址|地址|电话|账号|密码|密钥|"
    r"同事|同学|朋友|家人|这个|那个|这件|那件|这里|那里|上次|刚才|\d{8,}|@|https?://|token|api[_ -]?key",
    re.I,
)


class EncyclopediaPlanError(ValueError):
    """A fixed diagnostic status; never include model output in observations."""

    def __init__(self, status: str):
        if status not in {"planner_empty_response", "planner_response_truncated", "planner_invalid_response"}:
            raise ValueError("unknown encyclopedia planner status")
        self.status = status
        super().__init__(status)


def should_plan_encyclopedia(text: str, *, automatic: bool) -> bool:
    text = text.strip()
    if not text or _TRIVIAL_MESSAGE.fullmatch(text):
        return False
    return automatic or bool(_EXPLICIT_LOOKUP.search(text))


def direct_lookup_request(text: str) -> tuple[list[str], str]:
    # Remove bounded scene actions only for title extraction. Chat keeps the original.
    if len(text) > 600:
        return [], ""
    text = re.sub(r"（[^（）\n]{0,300}）|\([^()\n]{0,300}\)", "", text).strip()
    if any(char in text for char in "（）()"):
        return [], ""
    match = _DIRECT_TERM.fullmatch(text)
    trigger = "direct_command"
    if match is None:
        match = _DIRECT_QUESTION.fullmatch(text)
        trigger = "direct_question"
    if match is None:
        return [], ""
    term = match.group(1).strip()
    if trigger == "direct_question":
        term = term.rstrip("。！!？?，, \t")
        term = re.sub(r"[吗么嘛]$", "", term).strip()
        term = re.sub(r"的(?:故事|剧情|背景|资料)$", "", term).strip()
    for opening, closing in (("《", "》"), ("“", "”"), ("‘", "’"), ("「", "」"), ("『", "』"), ('"', '"')):
        if term.startswith(opening) and term.endswith(closing):
            term = term[1:-1].strip()
            break
    # Be conservative with private references and ordinary conversational clauses.
    if not 2 <= len(term) <= 24 or _PRIVATE_OR_CONTEXTUAL_TERM.search(term):
        return [], ""
    if not re.fullmatch(r"[\w\u3400-\u9fff·・！!：:—\- ]+", term):
        return [], ""
    return [term], trigger


def direct_lookup_terms(text: str) -> list[str]:
    return direct_lookup_request(text)[0]


def validate_encyclopedia_arguments(arguments: dict) -> dict:
    terms = arguments.get("candidate_terms")
    if not isinstance(terms, list) or not 1 <= len(terms) <= 3:
        raise ToolArgumentError("encyclopedia requires one to three candidate terms")
    if any(not isinstance(term, str) or not term.strip() or len(term) > 80 for term in terms):
        raise ToolArgumentError("encyclopedia candidate terms must be short strings")
    for name in ("query", "context_hint"):
        if name in arguments and not isinstance(arguments[name], str):
            raise ToolArgumentError("encyclopedia context must be text")
    # The service receives public keywords only, never query text or memories.
    return {"candidate_terms": list(dict.fromkeys(term.strip() for term in terms))}


def create_chat_tool_registry(service=PUBLIC_ENCYCLOPEDIA_SERVICE) -> ToolRegistry:
    async def execute(arguments, _context):
        result = await service.lookup(arguments)
        return ToolResult(json.dumps(result, ensure_ascii=False), {"evidence": result})
    return ToolRegistry([ToolSpec(
        name="lookup_unknown_slang", description="Query public Moegirlpedia facts for character chat.",
        risk_level=RiskLevel.READ_EXTERNAL, required_arguments=("candidate_terms",),
        optional_arguments=("query", "context_hint"), executor=execute,
        argument_validator=validate_encyclopedia_arguments,
    )])


@dataclass(frozen=True)
class EncyclopediaGraphExecution:
    evidence: dict[str, object] | None
    observation: dict[str, object]


class EncyclopediaGraphRunner:
    def __init__(self, *, registry=None, plan_timeout_seconds=8, lookup_timeout_seconds=8):
        self.registry = registry or create_chat_tool_registry()
        self.plan_timeout_seconds = min(max(float(plan_timeout_seconds), 1), 30)
        self.lookup_timeout_seconds = min(max(float(lookup_timeout_seconds), 1), 30)

    async def run(self, *, arguments: dict | None = None, text: str = "", planner: Callable[[str], Awaitable[dict]] | None = None,
                  diagnostic_runs: list | None = None) -> EncyclopediaGraphExecution:
        # Publish the mutable run before await: deadline cancellation must not
        # erase the source request that was in progress or earlier successes.
        with capture_query(self.plan_timeout_seconds, self.lookup_timeout_seconds, diagnostic_runs) as diagnostics:
            execution = await self._run(arguments=arguments, text=text, planner=planner)
            diagnostics.update(outcome="completed", status=execution.observation["encyclopedia_status"])
            execution.observation["encyclopedia_runs"] = [diagnostics]
            return execution

    async def _run(self, *, arguments: dict | None, text: str, planner: Callable[[str], Awaitable[dict]] | None) -> EncyclopediaGraphExecution:
        started = time.monotonic()
        trace = []
        evidence = None
        status = "not_needed"
        plan_ms = 0
        lookup_ms = 0
        planner_used = False
        plan_needed = None
        failure_code = ""
        source_error_types = []
        trigger = "model_tool" if arguments is not None else "automatic_plan"
        try:
            if arguments is None:
                trace.append(EncyclopediaNode.PLAN_QUERY.value)
                terms, direct_trigger = direct_lookup_request(text)
                if terms:
                    arguments = {"candidate_terms": terms}
                    trigger = direct_trigger
                elif planner is not None:
                    planner_used = True
                    plan_started = time.monotonic()
                    try:
                        plan = await wait_for_budget(planner(text), self.plan_timeout_seconds, origin="plan_deadline")
                    finally:
                        plan_ms = round((time.monotonic() - plan_started) * 1000)
                    if not isinstance(plan, dict) or type(plan.get("needed")) is not bool:
                        raise ToolArgumentError("invalid encyclopedia plan")
                    plan_needed = plan["needed"]
                    if plan["needed"]:
                        arguments = {"candidate_terms": plan.get("candidate_terms")}
            if arguments is not None:
                trace.append(EncyclopediaNode.VALIDATE_REQUEST.value)
                self.registry.validate_arguments("lookup_unknown_slang", arguments)
                note_candidates(arguments["candidate_terms"])
                trace.append(EncyclopediaNode.EXECUTE_LOOKUP.value)
                lookup_started = time.monotonic()
                try:
                    result = await wait_for_budget(self.registry.execute("lookup_unknown_slang", arguments, ToolContext()), self.lookup_timeout_seconds, origin="lookup_deadline")
                finally:
                    lookup_ms = round((time.monotonic() - lookup_started) * 1000)
                evidence = result.metadata["evidence"]
                status = str(evidence.get("status", "source_unavailable"))
                source_error_types = evidence.get("source_errors", [])
        except asyncio.TimeoutError:
            status = "lookup_timeout" if EncyclopediaNode.EXECUTE_LOOKUP.value in trace else "planner_timeout"
            failure_code = "request_timeout"
        except EncyclopediaPlanError as exc:
            status = exc.status
            failure_code = "invalid_model_response"
        except ToolArgumentError:
            status = "invalid_arguments"
            failure_code = "data_validation_failed"
        except Exception as exc:
            status = "lookup_error" if EncyclopediaNode.EXECUTE_LOOKUP.value in trace else "planner_error"
            failure_code = classify_failure(exc).code
        trace.append(EncyclopediaNode.BUILD_EVIDENCE.value)
        if evidence is None and status != "not_needed":
            evidence = {"status": status, "uncertainty": "百科查询未获得可靠资料，不能声称已核实。"}
        observation = {
            "encyclopedia_trigger": trigger,
            "encyclopedia_planner_used": planner_used,
            "encyclopedia_plan_needed": plan_needed,
            "encyclopedia_lookup_attempted": EncyclopediaNode.EXECUTE_LOOKUP.value in trace,
            "encyclopedia_failure_code": failure_code,
            "encyclopedia_source_error_types": source_error_types,
            "encyclopedia_status": status, "encyclopedia_node_trace": tuple(trace),
            "encyclopedia_plan_ms": plan_ms, "encyclopedia_lookup_ms": lookup_ms,
            "encyclopedia_elapsed_ms": round((time.monotonic() - started) * 1000),
            "encyclopedia_evidence_count": len((evidence or {}).get("results", [])),
            "encyclopedia_cache_hit": bool((evidence or {}).get("cache_hit", False)),
        }
        return EncyclopediaGraphExecution(evidence, observation)
