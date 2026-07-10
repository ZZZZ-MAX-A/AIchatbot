from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeAlias

from .owner_agent_runtime import (
    OwnerAgentContext,
    create_owner_agent_approval_request,
    execute_owner_agent_task_command,
    format_owner_agent_task_read,
    run_owner_agent_task_command,
)
from .owner_agent_work_runtime import (
    DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,
    OwnerAgentWorkContext,
    OwnerAgentWorkExecution,
    OwnerAgentWorkRuntime,
)
from .owner_read_runtime import OwnerReadRuntime, run_owner_read_command
from .owner_write_runtime import OwnerWriteRuntime, run_owner_write_command


EventValue: TypeAlias = Callable[[Any], str]
EventTextProvider: TypeAlias = Callable[[Any], str | Awaitable[str]]
LinesProvider: TypeAlias = Callable[[], list[str]]
TextProvider: TypeAlias = Callable[[], str]
GraphRunner: TypeAlias = Callable[..., Any]
AccessProvider: TypeAlias = Callable[[], Any]
AccessListFormatter: TypeAlias = Callable[[str, Any], str]
AccessOperation: TypeAlias = Callable[[str, str], bool]
ClearImageCache: TypeAlias = Callable[[], int]
SelectRoleCard: TypeAlias = Callable[[str], Any]
AddManualMemory: TypeAlias = Callable[..., int]
SubjectLabel: TypeAlias = Callable[[str, str], str]
ClearSessionSummaries: TypeAlias = Callable[[str], int]
DeleteSessionSummary: TypeAlias = Callable[[str, int], bool]
DevelopmentContextReportForEvent: TypeAlias = Callable[[Any, str], str | Awaitable[str]]


@dataclass(frozen=True)
class OwnerRuntimeFactory:
    session_key_from_event: EventValue
    user_id_from_event: EventValue
    bot_status_lines: LinesProvider
    ops_health_reply_for_event: EventTextProvider
    vision_troubleshoot_reply_for_event: EventTextProvider
    memory_rag_troubleshoot_reply_for_event: EventTextProvider
    run_diagnostics_graph: GraphRunner
    run_memory_retrieval_graph: GraphRunner
    run_memory_admin_graph: GraphRunner
    load_persona_prompt: TextProvider
    persona_status_lines: LinesProvider
    role_card_list_lines: LinesProvider
    model_config_status_lines: LinesProvider
    access_overview_lines: LinesProvider
    rag_index_detail_lines: LinesProvider
    main_agent_observation_lines: LinesProvider
    root_graph_observation_lines: LinesProvider
    current_access: AccessProvider
    list_lines: AccessListFormatter
    clear_image_cache: ClearImageCache
    clear_error_log: TextProvider
    add_access_item: AccessOperation
    remove_access_item: AccessOperation
    select_role_card: SelectRoleCard
    add_manual_memory: AddManualMemory
    subject_label: SubjectLabel
    clear_session_summaries: ClearSessionSummaries
    delete_session_summary: DeleteSessionSummary
    owner_user_id_default: str = ""
    fact_memory_type: str = "fact_summary"
    preference_memory_type: str = "preference_summary"
    development_context_report_for_event: DevelopmentContextReportForEvent | None = None

    def agent_context(self, event: Any) -> OwnerAgentContext:
        return OwnerAgentContext(
            session_key=self.session_key_from_event(event),
            user_id=self.user_id_from_event(event),
        )

    def read_runtime(self, event: Any) -> OwnerReadRuntime:
        async def run_owner_read_diagnostics(view):
            return (
                await self.run_diagnostics_graph(event)
                if view is None
                else await self.run_diagnostics_graph(event, view)
            )

        async def run_owner_read_memory_retrieval(action, query: str = ""):
            return await self.run_memory_retrieval_graph(event, action, query=query)

        async def run_owner_read_memory_admin(action):
            return await self.run_memory_admin_graph(event, action)

        return OwnerReadRuntime(
            bot_status_lines=self.bot_status_lines,
            ops_health_reply=lambda: self.ops_health_reply_for_event(event),
            vision_troubleshoot_reply=lambda: self.vision_troubleshoot_reply_for_event(event),
            memory_rag_troubleshoot_reply=lambda: self.memory_rag_troubleshoot_reply_for_event(event),
            run_diagnostics=run_owner_read_diagnostics,
            run_memory_retrieval=run_owner_read_memory_retrieval,
            run_memory_admin=run_owner_read_memory_admin,
            load_persona_prompt=self.load_persona_prompt,
            persona_status_lines=self.persona_status_lines,
            role_card_list_lines=self.role_card_list_lines,
            model_config_status_lines=self.model_config_status_lines,
            access_overview_lines=self.access_overview_lines,
            rag_index_detail_lines=self.rag_index_detail_lines,
            main_agent_observation_lines=self.main_agent_observation_lines,
            root_graph_observation_lines=self.root_graph_observation_lines,
            group_whitelist_reply=lambda: self.list_lines(
                "群白名单",
                self.current_access().group_whitelist,
            ),
            private_whitelist_reply=lambda: self.list_lines(
                "私聊白名单",
                self.current_access().private_whitelist,
            ),
            blacklist_reply=lambda: self.list_lines(
                "黑名单",
                self.current_access().user_blacklist,
            ),
        )

    def write_runtime(self) -> OwnerWriteRuntime:
        return OwnerWriteRuntime(
            clear_image_cache=self.clear_image_cache,
            clear_error_log=self.clear_error_log,
            add_access_item=self.add_access_item,
            remove_access_item=self.remove_access_item,
            select_role_card=self.select_role_card,
            add_manual_memory=self.add_manual_memory,
            subject_label=self.subject_label,
            clear_session_summaries=self.clear_session_summaries,
            delete_session_summary=self.delete_session_summary,
            owner_user_id_default=self.owner_user_id_default,
            fact_memory_type=self.fact_memory_type,
            preference_memory_type=self.preference_memory_type,
        )

    def work_runtime(self, event: Any) -> OwnerAgentWorkRuntime:
        executor = self.development_context_report_for_event
        if executor is None:
            raise RuntimeError("development_context_report executor was not injected")
        context = self.agent_context(event)
        return OwnerAgentWorkRuntime(
            context=OwnerAgentWorkContext(
                session_key=context.session_key,
                user_id=context.user_id,
            ),
            development_context_report_executor=lambda query: executor(event, query),
        )

    async def execute_development_context_report(
        self,
        event: Any,
        query: str,
    ) -> OwnerAgentWorkExecution:
        return await self.work_runtime(event).execute(
            work_type=DEVELOPMENT_CONTEXT_REPORT_WORK_TYPE,
            query=query,
        )

    def run_task_command(
        self,
        event: Any,
        query: str,
        *,
        approval_resume_tool_registry_factory,
    ) -> str | None:
        return run_owner_agent_task_command(
            self.agent_context(event),
            query,
            approval_resume_tool_registry_factory=approval_resume_tool_registry_factory,
        )

    def format_task_read(self, event: Any, command: str, reference: str) -> str:
        return format_owner_agent_task_read(
            self.agent_context(event),
            command,
            reference,
        )

    def execute_task_command(
        self,
        event: Any,
        command: str,
        reference: str,
        goal: str,
        *,
        approval_resume_tool_registry_factory,
    ) -> str:
        return execute_owner_agent_task_command(
            self.agent_context(event),
            command,
            reference,
            goal,
            approval_resume_tool_registry_factory=approval_resume_tool_registry_factory,
        )

    def create_approval_request(
        self,
        event: Any,
        *,
        query: str,
        requested_tool: str,
        arguments: dict[str, Any],
        risk_level: Any,
        policy_reason: str,
    ) -> str:
        return create_owner_agent_approval_request(
            self.agent_context(event),
            query=query,
            requested_tool=requested_tool,
            arguments=arguments,
            risk_level=risk_level,
            policy_reason=policy_reason,
        )

    async def run_read_command(self, event: Any, command: str, context: Any) -> str:
        return await run_owner_read_command(
            self.read_runtime(event),
            command,
            context,
        )

    def run_write_command(self, command: str, context: Any) -> str:
        return run_owner_write_command(
            self.write_runtime(),
            command,
            context,
        )
