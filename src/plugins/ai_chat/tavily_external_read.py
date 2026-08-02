from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from .external_research_synthesis import (
    current_status_evidence_coverage,
    ExternalResearchLlmCall,
    ExternalResearchSynthesis,
    format_external_research_default_response,
    format_external_research_response,
    select_external_research_evidence,
    synthesize_external_research_answer,
)
from .external_read_security import (
    adapt_external_read_scene_plan,
    adapt_recent_external_read_search_plan,
    ExternalReadBudget,
    ExternalReadPolicyError,
    ExternalReadStagePolicyError,
    ExternalReadSearchPlan,
    ExternalReadTemporalQuery,
    ExternalReadTimeWindow,
    external_read_query_requires_next_status,
    normalize_external_read_query,
    normalize_external_read_search_query,
    resolve_external_read_secondary_time_window,
    rewrite_external_read_temporal_query,
)
from .external_search import (
    ExternalSearchExecution,
    combine_external_search_executions,
    constrain_external_search_to_official_sources,
    constrain_external_search_to_time_window,
    execute_external_search,
    tag_external_search_stage,
)
from .owner_agent_work_runtime import ExternalReadReportPayload
from .tavily_http_transport import PinnedTavilyHttpTransport
from .tavily_search import TavilyBasicSearchProvider, TavilySearchTransport


@dataclass(frozen=True)
class ExternalReadStageMetrics:
    search_stage_count: int
    official_stage_candidate_count: int
    official_stage_result_count: int
    media_stage_candidate_count: int = 0
    media_stage_result_count: int = 0


def _stage_policy_error(
    error: ExternalReadPolicyError,
    *,
    search_stage: str,
    provider_request_count: int,
) -> ExternalReadStagePolicyError:
    return ExternalReadStagePolicyError(
        error.category,
        error.detail,
        search_stage=search_stage,
        provider_request_count=provider_request_count,
    )


def build_external_read_stage_query(
    question: str,
    *,
    time_window: ExternalReadTimeWindow | None,
    stage: str,
) -> str:
    del time_window
    if stage not in {"official", "media_fallback", "primary", "secondary"}:
        raise ValueError("external read search stage is invalid")
    return normalize_external_read_search_query(question)


def _legacy_external_read_search_plan(question: str) -> ExternalReadSearchPlan:
    query = normalize_external_read_search_query(question)
    return ExternalReadSearchPlan(
        primary_query=query,
        primary_source_scope="official",
        primary_evidence_role="official_confirmation",
        secondary_query=query,
        secondary_source_scope="news",
        secondary_evidence_role="reported_candidate",
        secondary_mode="if_no_results",
        planning_mode="legacy_fixed",
        scene="official_update",
    )


def _provider_options_for_scope(
    source_scope: str,
    *,
    time_window: ExternalReadTimeWindow | None,
    planned_time_range: str = "",
) -> dict[str, str]:
    options = {
        "topic": "news" if source_scope == "news" else "general",
        "search_depth": "basic" if source_scope == "news" else "advanced",
    }
    if time_window is not None:
        options.update(
            {
                "start_date": time_window.start_iso,
                "end_date": time_window.end_iso,
            }
        )
    elif planned_time_range:
        options["time_range"] = planned_time_range
    return options


def _apply_stage_constraints(
    execution: ExternalSearchExecution,
    *,
    source_scope: str,
    time_window: ExternalReadTimeWindow | None,
    query: str,
    search_stage: str,
    evidence_role: str,
) -> ExternalSearchExecution:
    constrained = execution
    if source_scope == "official":
        constrained = constrain_external_search_to_official_sources(
            constrained,
            query=query,
        )
    if time_window is not None:
        constrained = constrain_external_search_to_time_window(
            constrained,
            time_window=time_window,
            query=query,
        )
    return tag_external_search_stage(
        constrained,
        search_stage=search_stage,
        evidence_role=evidence_role,
    )


async def _execute_planned_stage(
    provider: TavilyBasicSearchProvider,
    budget: ExternalReadBudget,
    *,
    query: str,
    source_scope: str,
    planned_time_range: str,
    evidence_role: str,
    time_window: ExternalReadTimeWindow | None,
    search_stage: str,
) -> ExternalSearchExecution:
    execution = await execute_external_search(
        provider,
        query,
        budget=budget,
        provider_search_options=_provider_options_for_scope(
            source_scope,
            time_window=time_window,
            planned_time_range=planned_time_range,
        ),
    )
    return _apply_stage_constraints(
        execution,
        source_scope=source_scope,
        time_window=time_window,
        query=query,
        search_stage=search_stage,
        evidence_role=evidence_role,
    )


def external_search_execution_to_report_payload(
    execution: ExternalSearchExecution,
    *,
    synthesis: ExternalResearchSynthesis,
    response_text: str,
    detail_text: str = "",
    stage_metrics: ExternalReadStageMetrics,
    search_plan: ExternalReadSearchPlan,
) -> ExternalReadReportPayload:
    """Convert ephemeral search evidence to the formal owner work payload."""
    if not isinstance(execution, ExternalSearchExecution):
        raise TypeError("external search execution is invalid")
    return ExternalReadReportPayload(
        provider_name=execution.provider_name,
        result_count=len(execution.results),
        source_host_count=execution.source_host_count,
        dropped_result_count=execution.dropped_result_count,
        external_request_count=execution.external_request_count,
        response_truncated=execution.response_truncated,
        status_category=(
            "no_results"
            if not execution.results
            else "completed"
            if synthesis.status == "completed"
            else "synthesis_fallback"
        ),
        error_category="none",
        report_text=response_text,
        detail_text=detail_text,
        provider_request_count=execution.external_request_count,
        synthesis_request_count=synthesis.request_count,
        synthesis_status=synthesis.status,
        synthesis_error_category=synthesis.error_category,
        owner_quality_status=(
            "owner_quality_pending" if execution.results else "not_applicable"
        ),
        provider_candidate_count=execution.provider_candidate_count,
        dropped_missing_date_count=execution.dropped_missing_date_count,
        dropped_outside_window_count=execution.dropped_outside_window_count,
        dropped_weak_only_count=execution.dropped_weak_only_count,
        dropped_conflicting_date_count=execution.dropped_conflicting_date_count,
        dropped_injection_count=execution.dropped_injection_count,
        dropped_sanitization_count=execution.dropped_sanitization_count,
        dropped_source_policy_count=execution.dropped_source_policy_count,
        official_content_strong_count=sum(
            result.date_evidence_strength == "official_content_strong"
            for result in execution.results
        ),
        search_stage_count=stage_metrics.search_stage_count,
        official_stage_candidate_count=(
            stage_metrics.official_stage_candidate_count
        ),
        official_stage_result_count=stage_metrics.official_stage_result_count,
        media_stage_candidate_count=stage_metrics.media_stage_candidate_count,
        media_stage_result_count=stage_metrics.media_stage_result_count,
        planning_mode=search_plan.planning_mode,
        scene=search_plan.scene,
        primary_source_scope=search_plan.primary_source_scope,
        secondary_source_scope=(
            search_plan.secondary_source_scope
            if stage_metrics.search_stage_count == 2
            else ""
        ),
        secondary_mode=(
            search_plan.secondary_mode
            if stage_metrics.search_stage_count == 2
            else "none"
        ),
    )


@dataclass(frozen=True)
class TavilyExternalReadExecutor:
    """Fixed-provider executor with a bounded MainAgent-authored search plan."""

    provider: TavilyBasicSearchProvider
    budget: ExternalReadBudget
    synthesis_call: ExternalResearchLlmCall | None = None
    today_provider: Callable[[], date] = date.today

    async def __call__(
        self,
        query: str,
        *,
        trusted_temporal_query: ExternalReadTemporalQuery | None = None,
        search_plan: ExternalReadSearchPlan | None = None,
    ) -> ExternalReadReportPayload:
        trusted_current_date = self.today_provider()
        if trusted_temporal_query is None:
            temporal_query = rewrite_external_read_temporal_query(
                query,
                reference_date=trusted_current_date,
            )
        else:
            temporal_query = ExternalReadTemporalQuery(
                query=normalize_external_read_query(trusted_temporal_query.query),
                time_window=trusted_temporal_query.time_window,
                search_question=normalize_external_read_query(
                    trusted_temporal_query.search_question
                    or trusted_temporal_query.query
                ),
            )
        plan = search_plan or _legacy_external_read_search_plan(
            temporal_query.search_question or temporal_query.query
        )
        plan = adapt_external_read_scene_plan(
            plan,
            source_query=query,
        )
        plan = adapt_recent_external_read_search_plan(
            plan,
            source_query=query,
            time_window=temporal_query.time_window,
        )
        current_status_requires_candidate = (
            plan.scene == "current_status"
            and external_read_query_requires_next_status(query)
        )
        secondary_time_window = resolve_external_read_secondary_time_window(
            primary_time_window=temporal_query.time_window,
            search_plan=plan,
            reference_date=trusted_current_date,
        )
        primary_stage_name = (
            "official" if plan.planning_mode == "legacy_fixed" else "primary"
        )
        secondary_stage_name = (
            "media_fallback"
            if plan.planning_mode == "legacy_fixed"
            else "secondary"
        )
        primary_query = build_external_read_stage_query(
            plan.primary_query,
            time_window=temporal_query.time_window,
            stage=primary_stage_name,
        )
        secondary_query = ""
        if plan.secondary_mode != "none":
            secondary_query = build_external_read_stage_query(
                plan.secondary_query,
                time_window=temporal_query.time_window,
                stage=secondary_stage_name,
            )

        if plan.secondary_mode == "always":
            stage_outcomes = await asyncio.gather(
                _execute_planned_stage(
                    self.provider,
                    self.budget,
                    query=primary_query,
                    source_scope=plan.primary_source_scope,
                    planned_time_range=plan.primary_time_range,
                    evidence_role=plan.primary_evidence_role,
                    time_window=temporal_query.time_window,
                    search_stage=primary_stage_name,
                ),
                _execute_planned_stage(
                    self.provider,
                    self.budget,
                    query=secondary_query,
                    source_scope=plan.secondary_source_scope,
                    planned_time_range=plan.secondary_time_range,
                    evidence_role=plan.secondary_evidence_role,
                    time_window=secondary_time_window,
                    search_stage=secondary_stage_name,
                ),
                return_exceptions=True,
            )
            primary_outcome, secondary_outcome = stage_outcomes
            if isinstance(primary_outcome, ExternalReadPolicyError):
                raise _stage_policy_error(
                    primary_outcome,
                    search_stage=primary_stage_name,
                    provider_request_count=2,
                ) from primary_outcome
            if isinstance(secondary_outcome, ExternalReadPolicyError):
                raise _stage_policy_error(
                    secondary_outcome,
                    search_stage=secondary_stage_name,
                    provider_request_count=2,
                ) from secondary_outcome
            if not isinstance(primary_outcome, ExternalSearchExecution):
                raise TypeError("primary external search outcome is invalid")
            if not isinstance(secondary_outcome, ExternalSearchExecution):
                raise TypeError("secondary external search outcome is invalid")
            primary_execution = primary_outcome
            secondary_execution = secondary_outcome
        else:
            try:
                primary_execution = await _execute_planned_stage(
                    self.provider,
                    self.budget,
                    query=primary_query,
                    source_scope=plan.primary_source_scope,
                    planned_time_range=plan.primary_time_range,
                    evidence_role=plan.primary_evidence_role,
                    time_window=temporal_query.time_window,
                    search_stage=primary_stage_name,
                )
            except ExternalReadPolicyError as exc:
                raise _stage_policy_error(
                    exc,
                    search_stage=primary_stage_name,
                    provider_request_count=1,
                ) from exc
            secondary_execution = None
        stage_metrics = ExternalReadStageMetrics(
            search_stage_count=1,
            official_stage_candidate_count=(
                primary_execution.provider_candidate_count
            ),
            official_stage_result_count=len(primary_execution.results),
        )
        execution = primary_execution
        should_run_secondary = plan.secondary_mode == "always" or (
            plan.secondary_mode == "if_no_results"
            and not primary_execution.results
        )
        if should_run_secondary:
            if secondary_execution is None:
                try:
                    secondary_execution = await _execute_planned_stage(
                        self.provider,
                        self.budget,
                        query=secondary_query,
                        source_scope=plan.secondary_source_scope,
                        planned_time_range=plan.secondary_time_range,
                        evidence_role=plan.secondary_evidence_role,
                        time_window=secondary_time_window,
                        search_stage=secondary_stage_name,
                    )
                except ExternalReadPolicyError as exc:
                    raise _stage_policy_error(
                        exc,
                        search_stage=secondary_stage_name,
                        provider_request_count=2,
                    ) from exc
            execution = combine_external_search_executions(
                primary_execution,
                secondary_execution,
            )
            stage_metrics = ExternalReadStageMetrics(
                search_stage_count=2,
                official_stage_candidate_count=(
                    primary_execution.provider_candidate_count
                ),
                official_stage_result_count=sum(
                    result.search_stage == primary_stage_name
                    for result in execution.results
                ),
                media_stage_candidate_count=(
                    secondary_execution.provider_candidate_count
                ),
                media_stage_result_count=sum(
                    result.search_stage == secondary_stage_name
                    for result in execution.results
                ),
            )
        evidence = select_external_research_evidence(
            execution.results,
            query=temporal_query.query,
        )
        current_status_coverage = current_status_evidence_coverage(evidence)
        if (
            current_status_requires_candidate
            and evidence
            and not current_status_coverage.complete
        ):
            synthesis = ExternalResearchSynthesis(
                status="not_run_incomplete_evidence",
                request_count=0,
            )
        elif self.synthesis_call is None:
            synthesis = ExternalResearchSynthesis(
                status="not_configured" if evidence else "not_run_no_evidence",
                request_count=0,
            )
        else:
            synthesis = await synthesize_external_research_answer(
                temporal_query.query,
                evidence,
                self.synthesis_call,
                trusted_current_date=trusted_current_date,
                primary_time_window=temporal_query.time_window,
                secondary_time_window=(
                    secondary_time_window if should_run_secondary else None
                ),
                secondary_is_nearest_fallback=(
                    should_run_secondary
                    and plan.secondary_mode == "if_no_results"
                    and secondary_time_window != temporal_query.time_window
                ),
                scene=plan.scene,
            )
        detail_text = format_external_research_response(
            provider_name=execution.provider_name,
            evidence=evidence,
            synthesis=synthesis,
            query=temporal_query.query,
            time_window=temporal_query.time_window,
            search_stage_count=stage_metrics.search_stage_count,
            planning_mode=plan.planning_mode,
            primary_source_scope=plan.primary_source_scope,
            primary_time_range=plan.primary_time_range,
            primary_evidence_role=plan.primary_evidence_role,
            secondary_source_scope=(
                plan.secondary_source_scope if should_run_secondary else ""
            ),
            secondary_time_range=(
                plan.secondary_time_range if should_run_secondary else ""
            ),
            secondary_evidence_role=(
                plan.secondary_evidence_role if should_run_secondary else ""
            ),
            secondary_mode=(plan.secondary_mode if should_run_secondary else "none"),
            secondary_time_window=(
                secondary_time_window if should_run_secondary else None
            ),
            scene=plan.scene,
        )
        response_text = format_external_research_default_response(
            evidence=evidence,
            synthesis=synthesis,
            query=temporal_query.query,
            time_window=temporal_query.time_window,
            search_stage_count=stage_metrics.search_stage_count,
            secondary_time_window=(
                secondary_time_window if should_run_secondary else None
            ),
            scene=plan.scene,
            current_status_requires_candidate=current_status_requires_candidate,
        )
        return external_search_execution_to_report_payload(
            execution,
            synthesis=synthesis,
            response_text=response_text,
            detail_text=detail_text,
            stage_metrics=stage_metrics,
            search_plan=plan,
        )


def create_tavily_external_read_executor(
    *,
    api_key: str,
    timeout_seconds: int = 10,
    transport: TavilySearchTransport | None = None,
    synthesis_call: ExternalResearchLlmCall | None = None,
    today_provider: Callable[[], date] = date.today,
) -> TavilyExternalReadExecutor:
    """Build the reviewed single-provider executor without registering it."""
    budget = ExternalReadBudget(timeout_seconds=timeout_seconds)
    selected_transport = transport or PinnedTavilyHttpTransport()
    provider = TavilyBasicSearchProvider(
        api_key=api_key,
        transport=selected_transport,
        timeout_seconds=budget.timeout_seconds,
        max_response_bytes=budget.max_response_bytes,
    )
    return TavilyExternalReadExecutor(
        provider=provider,
        budget=budget,
        synthesis_call=synthesis_call,
        today_provider=today_provider,
    )


def create_configured_tavily_external_read_executor(
    *,
    feature_enabled: bool,
    api_key: str,
    timeout_seconds: int,
    transport: TavilySearchTransport | None = None,
    synthesis_call: ExternalResearchLlmCall | None = None,
    today_provider: Callable[[], date] = date.today,
) -> TavilyExternalReadExecutor | None:
    """Fail closed unless the switch, credential, and budget are all valid."""
    if feature_enabled is not True:
        return None
    try:
        return create_tavily_external_read_executor(
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            transport=transport,
            synthesis_call=synthesis_call,
            today_provider=today_provider,
        )
    except ValueError:
        return None
