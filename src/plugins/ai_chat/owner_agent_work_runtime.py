from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .agent_tasks import (
    AGENT_TASK_RESULT_LIMIT,
    AGENT_TASK_WORK_QUERY_SUMMARY_LIMIT,
    AgentTask,
    agent_task_status_label,
    claim_agent_task_for_work,
    complete_agent_task_work,
    create_agent_task,
    fail_agent_task_work,
)
from .development_context_report import (
    DEVELOPMENT_CONTEXT_REPORT_RESPONSE_LIMIT,
    DevelopmentContextReportPayload,
    redact_development_context_sensitive_text,
)


DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE = "development_context_report"
DEVELOPMENT_CONTEXT_REPORT_DISPLAY_NAME = "研发上下文报告"
DEVELOPMENT_CONTEXT_REPORT_RISK_LEVEL = "read_local"
DEVELOPMENT_CONTEXT_REPORT_COMMAND_PREFIX = "执行研发上下文任务"

WorkExecutor = Callable[[str], object | Awaitable[object]]


@dataclass(frozen=True)
class SanitizedAgentWorkResult:
    persisted_summary: str
    response_text: str


WorkResultSanitizer = Callable[[object], SanitizedAgentWorkResult]


@dataclass(frozen=True)
class OwnerAgentWorkContext:
    session_key: str
    user_id: str


@dataclass(frozen=True)
class AgentWorkSpec:
    name: str
    display_name: str
    risk_level: str
    required_arguments: tuple[str, ...]
    executor: WorkExecutor
    result_sanitizer: WorkResultSanitizer
    requires_approval: bool
    result_limit: int


@dataclass(frozen=True)
class OwnerAgentWorkExecution:
    work_type: str
    task: AgentTask | None
    outcome: str
    result_summary: str
    response_text: str = ""


def parse_development_context_report_command(query: str) -> str | None:
    stripped = query.strip()
    if stripped == DEVELOPMENT_CONTEXT_REPORT_COMMAND_PREFIX:
        return ""
    for separator in ("：", ":"):
        prefix = f"{DEVELOPMENT_CONTEXT_REPORT_COMMAND_PREFIX}{separator}"
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip()
    return None


def format_owner_agent_work_execution(execution: OwnerAgentWorkExecution) -> str:
    task = execution.task
    if task is None:
        return "研发上下文任务未创建；未执行任何执行器。"

    if execution.outcome == "completed":
        headline = f"研发上下文任务 #{task.id} 已完成。"
    elif execution.outcome == "failed":
        headline = f"研发上下文任务 #{task.id} 执行失败。"
    else:
        headline = f"研发上下文任务 #{task.id} 未进入执行。"

    return "\n".join(
        [
            headline,
            f"状态：{agent_task_status_label(task.status)}",
            "结果：",
            execution.response_text or execution.result_summary,
            f"查看：/agent 任务详情 {task.id}",
            "边界：只执行已注册的只读研发上下文报告；未开放 shell、文件写入、Web 写操作或自动重试。",
        ]
    )


def _normalize_query(query: str) -> str:
    if not isinstance(query, str):
        raise ValueError("work query must be text")
    without_controls = "".join(
        " " if ord(character) < 32 else character for character in query
    )
    compact = " ".join(without_controls.split())
    if not compact:
        raise ValueError("work query must be non-empty")
    return compact[:AGENT_TASK_WORK_QUERY_SUMMARY_LIMIT].rstrip()


def _first_count(text: str, labels: tuple[str, ...]) -> int | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*(\d+)", text)
        if match:
            return int(match.group(1))
    return None


def _sanitize_development_context_response(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("development context report response must be non-empty")
    normalized_lines: list[str] = []
    for line in text.splitlines():
        without_controls = "".join(
            " " if ord(character) < 32 else character for character in line
        )
        normalized_lines.append(without_controls.rstrip())
    normalized = redact_development_context_sensitive_text(
        "\n".join(normalized_lines).strip()
    )
    if not normalized:
        raise ValueError("development context report response became empty")
    return normalized[:DEVELOPMENT_CONTEXT_REPORT_RESPONSE_LIMIT].rstrip()


def _persisted_development_context_summary(
    *,
    project_count: int | None,
    memory_count: int | None,
    summary_mode: str = "legacy_count_only",
    current_status_anchor_included: bool | None = None,
    retrieval_warning_count: int = 0,
) -> str:
    lines = ["研发上下文报告已完成。"]
    if project_count is not None:
        lines.append(f"项目文档命中：{project_count}。")
    if memory_count is not None:
        lines.append(f"开发侧记忆命中：{memory_count}。")
    if project_count is None and memory_count is None:
        lines.append("执行器未返回可持久化的命中计数。")
    if current_status_anchor_included is not None:
        anchor_status = "已加载" if current_status_anchor_included else "缺失"
        lines.append(f"当前状态锚点：{anchor_status}。")
        lines.append(f"检索警告：{retrieval_warning_count}。")
    if summary_mode == "bounded_llm":
        lines.append("详细回复：受限主模型结构化总结，仅在本次主人私聊返回。")
    elif summary_mode == "deterministic_fallback":
        lines.append("详细回复：确定性回退摘要，仅在本次主人私聊返回。")
    lines.append("任务记录未保存原始 RAG 片段、路径、详细回复或异常文本。")
    return "\n".join(lines)[:AGENT_TASK_RESULT_LIMIT].rstrip()


def _sanitize_development_context_report(raw_result: object) -> SanitizedAgentWorkResult:
    if isinstance(raw_result, DevelopmentContextReportPayload):
        if raw_result.project_result_count < 0 or raw_result.memory_result_count < 0:
            raise ValueError("development context report counts must be non-negative")
        if raw_result.current_status_anchor_included is not None and not isinstance(
            raw_result.current_status_anchor_included,
            bool,
        ):
            raise ValueError("development context report anchor flag is invalid")
        if (
            not isinstance(raw_result.retrieval_warning_count, int)
            or isinstance(raw_result.retrieval_warning_count, bool)
            or raw_result.retrieval_warning_count < 0
        ):
            raise ValueError("development context report warning count is invalid")
        if raw_result.summary_mode not in {"bounded_llm", "deterministic_fallback"}:
            raise ValueError("development context report summary mode is invalid")
        persisted_summary = _persisted_development_context_summary(
            project_count=raw_result.project_result_count,
            memory_count=raw_result.memory_result_count,
            summary_mode=raw_result.summary_mode,
            current_status_anchor_included=raw_result.current_status_anchor_included,
            retrieval_warning_count=raw_result.retrieval_warning_count,
        )
        response_text = _sanitize_development_context_response(raw_result.report_text)
        return SanitizedAgentWorkResult(
            persisted_summary=persisted_summary,
            response_text=response_text,
        )

    if not isinstance(raw_result, str) or not raw_result.strip():
        raise ValueError("development context report executor returned no text")

    project_count = _first_count(raw_result, ("project docs:", "项目文档命中："))
    memory_count = _first_count(raw_result, ("memories:", "记忆命中："))
    persisted_summary = _persisted_development_context_summary(
        project_count=project_count,
        memory_count=memory_count,
    )
    return SanitizedAgentWorkResult(
        persisted_summary=persisted_summary,
        response_text=persisted_summary,
    )


def _development_context_report_spec(executor: WorkExecutor) -> AgentWorkSpec:
    return AgentWorkSpec(
        name=DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,
        display_name=DEVELOPMENT_CONTEXT_REPORT_DISPLAY_NAME,
        risk_level=DEVELOPMENT_CONTEXT_REPORT_RISK_LEVEL,
        required_arguments=("query",),
        executor=executor,
        result_sanitizer=_sanitize_development_context_report,
        requires_approval=False,
        result_limit=AGENT_TASK_RESULT_LIMIT,
    )


class OwnerAgentWorkRuntime:
    """Runs the one registered read-only work type without any QQ dependency."""

    def __init__(
        self,
        *,
        context: OwnerAgentWorkContext,
        development_context_report_executor: WorkExecutor,
    ) -> None:
        self.context = context
        spec = _development_context_report_spec(development_context_report_executor)
        self._work_specs = {spec.name: spec}

    @property
    def registered_work_types(self) -> tuple[str, ...]:
        return tuple(self._work_specs)

    def work_spec(self, work_type: str) -> AgentWorkSpec:
        normalized_work_type = str(work_type).strip()
        spec = self._work_specs.get(normalized_work_type)
        if spec is None:
            raise ValueError(f"unsupported owner agent work type: {normalized_work_type}")
        return spec

    async def execute(self, *, work_type: str, query: str) -> OwnerAgentWorkExecution:
        spec = self.work_spec(work_type)
        normalized_query = _normalize_query(query)
        task_id = create_agent_task(
            session_key=self.context.session_key,
            user_id=self.context.user_id,
            title=spec.display_name,
            goal=f"{spec.display_name}：{normalized_query}",
        )
        task, claimed = claim_agent_task_for_work(
            task_id=task_id,
            session_key=self.context.session_key,
            user_id=self.context.user_id,
            work_type=spec.name,
            query_summary=normalized_query,
        )
        if not claimed:
            return OwnerAgentWorkExecution(
                work_type=spec.name,
                task=task,
                outcome="not_claimed",
                result_summary="注册的只读工作任务未能领取，未执行执行器。",
                response_text="注册的只读工作任务未能领取，未执行执行器。",
            )

        try:
            value = spec.executor(normalized_query)
            raw_result = await value if inspect.isawaitable(value) else value
            sanitized_result = spec.result_sanitizer(raw_result)
        except Exception as exc:
            safe_error = f"{type(exc).__name__}: {spec.name} execution failed."
            failed_task, _ = fail_agent_task_work(
                task_id=task_id,
                session_key=self.context.session_key,
                user_id=self.context.user_id,
                work_type=spec.name,
                error_summary=safe_error,
            )
            return OwnerAgentWorkExecution(
                work_type=spec.name,
                task=failed_task,
                outcome="failed",
                result_summary=safe_error,
                response_text=safe_error,
            )

        result_summary = sanitized_result.persisted_summary
        completed_task, completed = complete_agent_task_work(
            task_id=task_id,
            session_key=self.context.session_key,
            user_id=self.context.user_id,
            work_type=spec.name,
            result=result_summary,
        )
        return OwnerAgentWorkExecution(
            work_type=spec.name,
            task=completed_task,
            outcome="completed" if completed else "not_completed",
            result_summary=result_summary,
            response_text=sanitized_result.response_text,
        )
