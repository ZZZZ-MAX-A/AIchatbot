from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .agent_tasks import (
    AGENT_TASK_RESULT_LIMIT,
    AGENT_TASK_WORK_QUERY_SUMMARY_LIMIT,
    AgentTask,
    claim_agent_task_for_work,
    complete_agent_task_work,
    create_agent_task,
    fail_agent_task_work,
)


DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE = "development_context_report"
DEVELOPMENT_CONTEXT_REPORT_DISPLAY_NAME = "研发上下文报告"
DEVELOPMENT_CONTEXT_REPORT_RISK_LEVEL = "read_local"

WorkExecutor = Callable[[str], str | Awaitable[str]]
WorkResultSanitizer = Callable[[str], str]


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


def _sanitize_development_context_report(raw_result: str) -> str:
    if not isinstance(raw_result, str) or not raw_result.strip():
        raise ValueError("development context report executor returned no text")

    project_count = _first_count(raw_result, ("project docs:", "项目文档命中："))
    memory_count = _first_count(raw_result, ("memories:", "记忆命中："))
    lines = ["研发上下文报告已完成。"]
    if project_count is not None:
        lines.append(f"项目文档命中：{project_count}。")
    if memory_count is not None:
        lines.append(f"开发侧记忆命中：{memory_count}。")
    if project_count is None and memory_count is None:
        lines.append("执行器未返回可持久化的命中计数。")
    lines.append("任务记录未保存原始 RAG 片段、路径或异常文本。")
    return "\n".join(lines)[:AGENT_TASK_RESULT_LIMIT].rstrip()


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
            )

        try:
            value = spec.executor(normalized_query)
            raw_result = await value if inspect.isawaitable(value) else value
            result_summary = spec.result_sanitizer(raw_result)
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
            )

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
        )
