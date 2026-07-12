from __future__ import annotations

from dataclasses import dataclass

from .external_read_security import ExternalReadBudget
from .external_search import ExternalSearchExecution, execute_external_search
from .owner_agent_work_runtime import ExternalReadReportPayload
from .tavily_http_transport import PinnedTavilyHttpTransport
from .tavily_search import TavilyBasicSearchProvider, TavilySearchTransport


def external_search_execution_to_report_payload(
    execution: ExternalSearchExecution,
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
        status_category="completed" if execution.results else "no_results",
        error_category="none",
        report_text=execution.response_text,
    )


@dataclass(frozen=True)
class TavilyExternalReadExecutor:
    """Fixed Tavily Basic executor; it performs exactly one provider search."""

    provider: TavilyBasicSearchProvider
    budget: ExternalReadBudget

    async def __call__(self, query: str) -> ExternalReadReportPayload:
        execution = await execute_external_search(
            self.provider,
            query,
            budget=self.budget,
        )
        return external_search_execution_to_report_payload(execution)


def create_tavily_external_read_executor(
    *,
    api_key: str,
    timeout_seconds: int = 10,
    transport: TavilySearchTransport | None = None,
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
    return TavilyExternalReadExecutor(provider=provider, budget=budget)


def create_configured_tavily_external_read_executor(
    *,
    feature_enabled: bool,
    api_key: str,
    timeout_seconds: int,
    transport: TavilySearchTransport | None = None,
) -> TavilyExternalReadExecutor | None:
    """Fail closed unless the switch, credential, and budget are all valid."""
    if feature_enabled is not True:
        return None
    try:
        return create_tavily_external_read_executor(
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            transport=transport,
        )
    except ValueError:
        return None
