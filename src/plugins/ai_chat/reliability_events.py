from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from typing import Iterable
from uuid import UUID, uuid4

from .database import connect, connect_read_only, ensure_database
from .failure_diagnostics import CATEGORY_LABELS, FailureCategory, classify_failure


RELIABILITY_EVENT_SCHEMA_VERSION = 1
RELIABILITY_BUCKET_MINUTES = 5
RELIABILITY_MAX_TREND_HOURS = 24 * 90
CHINA_STANDARD_TIME = timezone(timedelta(hours=8))


class ReliabilityEventContractError(ValueError):
    """Raised when a reliability event is outside the reviewed safe contract."""


class ReliabilityOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEGRADED = "degraded"
    SKIPPED = "skipped"


class ReliabilityRecoveryState(str, Enum):
    UNRESOLVED = "unresolved"
    RECOVERED = "recovered"
    RECURRING = "recurring"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class ReliabilityCodeContract:
    category: FailureCategory | None
    outcomes: frozenset[ReliabilityOutcome]


COMPONENT_OPERATIONS: dict[str, frozenset[str]] = {
    "bot_runtime": frozenset({"lifecycle"}),
    "chat_llm": frozenset({"generate_reply"}),
    "main_llm": frozenset({"plan_action"}),
    "sticker_classifier": frozenset({"classify_intent"}),
    "document_artifact": frozenset({"render_document"}),
    "document_delivery": frozenset({"send_document"}),
    "project_doc_rag": frozenset({"rebuild_index", "retrieve"}),
    "memory_rag": frozenset({"retrieve"}),
    "vision": frozenset({"infer"}),
    "tts": frozenset({"synthesize"}),
    "qq_adapter": frozenset({"send_message"}),
    "database": frozenset({"read", "write"}),
}


def _failure_contract(category: FailureCategory) -> ReliabilityCodeContract:
    return ReliabilityCodeContract(
        category,
        frozenset({ReliabilityOutcome.FAILED, ReliabilityOutcome.DEGRADED}),
    )


CODE_CONTRACTS: dict[str, ReliabilityCodeContract] = {
    "request_timeout": _failure_contract(FailureCategory.NETWORK),
    "connection_failed": _failure_contract(FailureCategory.NETWORK),
    "model_rate_limited": _failure_contract(FailureCategory.MODEL),
    "model_not_found": _failure_contract(FailureCategory.MODEL),
    "invalid_model_response": _failure_contract(FailureCategory.MODEL),
    "authorization_failed": _failure_contract(FailureCategory.PERMISSION),
    "invalid_configuration": _failure_contract(FailureCategory.CONFIGURATION),
    "data_validation_failed": _failure_contract(FailureCategory.DATA),
    "presentation_slide_limit_exceeded": _failure_contract(FailureCategory.DATA),
    "artifact_integrity_failed": _failure_contract(FailureCategory.DATA),
    "document_delivery_failed": _failure_contract(FailureCategory.NETWORK),
    "approval_context_invalid": _failure_contract(FailureCategory.PERMISSION),
    "required_arguments_unavailable": _failure_contract(FailureCategory.CONFIGURATION),
    "unexpected_runtime_state": _failure_contract(FailureCategory.DATA),
    "suspected_abnormal_exit": ReliabilityCodeContract(
        FailureCategory.DATA,
        frozenset({ReliabilityOutcome.DEGRADED}),
    ),
    "operation_succeeded": ReliabilityCodeContract(
        None,
        frozenset({ReliabilityOutcome.SUCCEEDED}),
    ),
    "operation_skipped": ReliabilityCodeContract(
        None,
        frozenset({ReliabilityOutcome.SKIPPED}),
    ),
    "runtime_started": ReliabilityCodeContract(
        None,
        frozenset({ReliabilityOutcome.SUCCEEDED}),
    ),
    "runtime_stopped": ReliabilityCodeContract(
        None,
        frozenset({ReliabilityOutcome.SUCCEEDED}),
    ),
}


RECOVERY_CAPABLE_OPERATIONS = frozenset(
    (component, operation)
    for component, operations in COMPONENT_OPERATIONS.items()
    for operation in operations
    if (component, operation) != ("bot_runtime", "lifecycle")
)


_PROCESS_RUNTIME_ID = str(uuid4())


def process_runtime_id() -> str:
    return _PROCESS_RUNTIME_ID


def new_runtime_id() -> str:
    return str(uuid4())


def _normalized_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ReliabilityEventContractError("occurred_at must be timezone-aware")
    return value.astimezone(UTC).replace(microsecond=0)


def _validate_runtime_id(value: str) -> str:
    if not isinstance(value, str):
        raise ReliabilityEventContractError("runtime_id must be a UUID string")
    try:
        normalized = str(UUID(value))
    except (ValueError, AttributeError) as exc:
        raise ReliabilityEventContractError("runtime_id must be a UUID string") from exc
    if value != normalized:
        raise ReliabilityEventContractError("runtime_id must use canonical UUID form")
    return value


@dataclass(frozen=True)
class ReliabilityEvent:
    schema_version: int
    occurred_at: datetime
    runtime_id: str
    component: str
    operation: str
    category: FailureCategory | None
    code: str
    outcome: ReliabilityOutcome

    def __post_init__(self) -> None:
        if self.schema_version != RELIABILITY_EVENT_SCHEMA_VERSION:
            raise ReliabilityEventContractError("unsupported reliability event schema")
        object.__setattr__(self, "occurred_at", _normalized_datetime(self.occurred_at))
        _validate_runtime_id(self.runtime_id)
        operations = COMPONENT_OPERATIONS.get(self.component)
        if operations is None or self.operation not in operations:
            raise ReliabilityEventContractError("component and operation are not registered")
        contract = CODE_CONTRACTS.get(self.code)
        if contract is None:
            raise ReliabilityEventContractError("reliability code is not registered")
        if self.category != contract.category:
            raise ReliabilityEventContractError("category does not match the code contract")
        if self.outcome not in contract.outcomes:
            raise ReliabilityEventContractError("outcome does not match the code contract")
        lifecycle_codes = {"runtime_started", "runtime_stopped", "suspected_abnormal_exit"}
        is_lifecycle = (self.component, self.operation) == ("bot_runtime", "lifecycle")
        if (self.code in lifecycle_codes) != is_lifecycle:
            raise ReliabilityEventContractError("lifecycle code and operation do not match")


@dataclass(frozen=True)
class ReliabilityEventBucket:
    id: int
    bucket_start: datetime
    runtime_id: str
    component: str
    operation: str
    category: FailureCategory | None
    code: str
    outcome: ReliabilityOutcome
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True)
class ReliabilityTrendItem:
    component: str
    operation: str
    category: FailureCategory
    code: str
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    last_success_at: datetime | None
    recovery_state: ReliabilityRecoveryState


@dataclass(frozen=True)
class ReliabilityTrendSummary:
    generated_at: datetime
    window_hours: int
    failure_occurrence_count: int
    items: tuple[ReliabilityTrendItem, ...]


@dataclass(frozen=True)
class RuntimeLifecycleStart:
    runtime_id: str
    suspected_previous_runtime_id: str | None


RECOVERY_STATE_LABELS = {
    ReliabilityRecoveryState.UNRESOLVED: "未恢复",
    ReliabilityRecoveryState.RECOVERED: "已恢复",
    ReliabilityRecoveryState.RECURRING: "反复发生",
    ReliabilityRecoveryState.INSUFFICIENT_EVIDENCE: "证据不足",
}


def create_reliability_event(
    *,
    component: str,
    operation: str,
    code: str,
    outcome: ReliabilityOutcome | str,
    category: FailureCategory | str | None = None,
    occurred_at: datetime | None = None,
    runtime_id: str | None = None,
) -> ReliabilityEvent:
    try:
        normalized_outcome = ReliabilityOutcome(outcome)
    except ValueError as exc:
        raise ReliabilityEventContractError("outcome is not registered") from exc
    if category is None:
        normalized_category = None
    else:
        try:
            normalized_category = FailureCategory(category)
        except ValueError as exc:
            raise ReliabilityEventContractError("category is not registered") from exc
    return ReliabilityEvent(
        schema_version=RELIABILITY_EVENT_SCHEMA_VERSION,
        occurred_at=occurred_at or datetime.now(UTC),
        runtime_id=runtime_id or process_runtime_id(),
        component=component,
        operation=operation,
        category=normalized_category,
        code=code,
        outcome=normalized_outcome,
    )


def _bucket_start(value: datetime) -> datetime:
    normalized = _normalized_datetime(value)
    minute = normalized.minute - normalized.minute % RELIABILITY_BUCKET_MINUTES
    return normalized.replace(minute=minute, second=0)


def _datetime_text(value: datetime) -> str:
    return _normalized_datetime(value).isoformat(timespec="seconds")


def _datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    return _normalized_datetime(parsed)


def _bucket_from_row(row) -> ReliabilityEventBucket:
    category_value = str(row["category"])
    return ReliabilityEventBucket(
        id=int(row["id"]),
        bucket_start=_datetime_from_text(row["bucket_start"]),
        runtime_id=str(row["runtime_id"]),
        component=str(row["component"]),
        operation=str(row["operation"]),
        category=FailureCategory(category_value) if category_value else None,
        code=str(row["code"]),
        outcome=ReliabilityOutcome(str(row["outcome"])),
        occurrence_count=int(row["occurrence_count"]),
        first_seen_at=_datetime_from_text(row["first_seen_at"]),
        last_seen_at=_datetime_from_text(row["last_seen_at"]),
    )


def record_reliability_event(event: ReliabilityEvent) -> ReliabilityEventBucket:
    if not isinstance(event, ReliabilityEvent):
        raise ReliabilityEventContractError("event must be a ReliabilityEvent")
    ensure_database()
    bucket_start = _datetime_text(_bucket_start(event.occurred_at))
    occurred_at = _datetime_text(event.occurred_at)
    category = event.category.value if event.category is not None else ""
    values = (
        event.schema_version,
        bucket_start,
        event.runtime_id,
        event.component,
        event.operation,
        category,
        event.code,
        event.outcome.value,
        occurred_at,
        occurred_at,
    )
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO reliability_event_buckets (
                schema_version,
                bucket_start,
                runtime_id,
                component,
                operation,
                category,
                code,
                outcome,
                occurrence_count,
                first_seen_at,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT (
                bucket_start,
                runtime_id,
                component,
                operation,
                category,
                code,
                outcome
            ) DO UPDATE SET
                occurrence_count = reliability_event_buckets.occurrence_count + 1,
                first_seen_at = MIN(reliability_event_buckets.first_seen_at, excluded.first_seen_at),
                last_seen_at = MAX(reliability_event_buckets.last_seen_at, excluded.last_seen_at)
            """,
            values,
        )
        row = connection.execute(
            """
            SELECT *
            FROM reliability_event_buckets
            WHERE bucket_start = ?
              AND runtime_id = ?
              AND component = ?
              AND operation = ?
              AND category = ?
              AND code = ?
              AND outcome = ?
            """,
            (
                bucket_start,
                event.runtime_id,
                event.component,
                event.operation,
                category,
                event.code,
                event.outcome.value,
            ),
        ).fetchone()
    if row is None:
        raise RuntimeError("reliability event bucket disappeared after upsert")
    return _bucket_from_row(row)


def record_result_safely(
    *,
    component: str,
    operation: str,
    code: str,
    outcome: ReliabilityOutcome | str,
    occurred_at: datetime | None = None,
    runtime_id: str | None = None,
) -> bool:
    contract = CODE_CONTRACTS.get(code)
    if contract is None:
        return False
    try:
        event = create_reliability_event(
            component=component,
            operation=operation,
            category=contract.category,
            code=code,
            outcome=outcome,
            occurred_at=occurred_at,
            runtime_id=runtime_id,
        )
        record_reliability_event(event)
    except Exception:
        return False
    return True


def record_success_safely(
    component: str,
    operation: str,
    *,
    occurred_at: datetime | None = None,
    runtime_id: str | None = None,
) -> bool:
    return record_result_safely(
        component=component,
        operation=operation,
        code="operation_succeeded",
        outcome=ReliabilityOutcome.SUCCEEDED,
        occurred_at=occurred_at,
        runtime_id=runtime_id,
    )


def record_failure_safely(
    component: str,
    operation: str,
    error: object,
    *,
    outcome: ReliabilityOutcome = ReliabilityOutcome.FAILED,
    occurred_at: datetime | None = None,
    runtime_id: str | None = None,
) -> bool:
    diagnosis = classify_failure(error)
    return record_result_safely(
        component=component,
        operation=operation,
        code=diagnosis.code,
        outcome=outcome,
        occurred_at=occurred_at,
        runtime_id=runtime_id,
    )


def _load_buckets_since(cutoff: datetime) -> list[ReliabilityEventBucket]:
    with connect_read_only() as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM reliability_event_buckets
            WHERE last_seen_at >= ?
            ORDER BY first_seen_at, id
            """,
            (_datetime_text(cutoff),),
        ).fetchall()
    return [_bucket_from_row(row) for row in rows]


def _latest_successes(
    buckets: Iterable[ReliabilityEventBucket],
) -> dict[tuple[str, str], list[datetime]]:
    successes: dict[tuple[str, str], list[datetime]] = {}
    for bucket in buckets:
        if bucket.outcome != ReliabilityOutcome.SUCCEEDED:
            continue
        successes.setdefault((bucket.component, bucket.operation), []).append(
            bucket.last_seen_at
        )
    return successes


def read_reliability_trend(
    *,
    window_hours: int = 24,
    now: datetime | None = None,
) -> ReliabilityTrendSummary:
    if isinstance(window_hours, bool) or not isinstance(window_hours, int):
        raise ValueError("window_hours must be an integer")
    if window_hours < 1 or window_hours > RELIABILITY_MAX_TREND_HOURS:
        raise ValueError("window_hours is outside the reviewed range")
    generated_at = _normalized_datetime(now or datetime.now(UTC))
    buckets = _load_buckets_since(generated_at - timedelta(hours=window_hours))
    successes = _latest_successes(buckets)
    grouped: dict[
        tuple[str, str, FailureCategory, str],
        list[ReliabilityEventBucket],
    ] = {}
    for bucket in buckets:
        if bucket.outcome not in {
            ReliabilityOutcome.FAILED,
            ReliabilityOutcome.DEGRADED,
        }:
            continue
        if bucket.category is None:
            continue
        key = (bucket.component, bucket.operation, bucket.category, bucket.code)
        grouped.setdefault(key, []).append(bucket)

    items: list[ReliabilityTrendItem] = []
    for (component, operation, category, code), failures in grouped.items():
        first_seen_at = min(item.first_seen_at for item in failures)
        last_seen_at = max(item.last_seen_at for item in failures)
        occurrence_count = sum(item.occurrence_count for item in failures)
        operation_successes = successes.get((component, operation), [])
        last_success_at = max(operation_successes) if operation_successes else None
        if (component, operation) not in RECOVERY_CAPABLE_OPERATIONS:
            recovery_state = ReliabilityRecoveryState.INSUFFICIENT_EVIDENCE
        elif last_success_at is not None and last_success_at > last_seen_at:
            recovery_state = ReliabilityRecoveryState.RECOVERED
        elif any(timestamp > first_seen_at for timestamp in operation_successes):
            recovery_state = ReliabilityRecoveryState.RECURRING
        else:
            recovery_state = ReliabilityRecoveryState.UNRESOLVED
        items.append(
            ReliabilityTrendItem(
                component=component,
                operation=operation,
                category=category,
                code=code,
                occurrence_count=occurrence_count,
                first_seen_at=first_seen_at,
                last_seen_at=last_seen_at,
                last_success_at=last_success_at,
                recovery_state=recovery_state,
            )
        )
    items.sort(
        key=lambda item: (
            -item.occurrence_count,
            -item.last_seen_at.timestamp(),
            item.component,
            item.operation,
            item.category.value,
            item.code,
        )
    )
    return ReliabilityTrendSummary(
        generated_at=generated_at,
        window_hours=window_hours,
        failure_occurrence_count=sum(item.occurrence_count for item in items),
        items=tuple(items),
    )


def _trend_time(value: datetime) -> str:
    return _normalized_datetime(value).astimezone(CHINA_STANDARD_TIME).strftime(
        "%m-%d %H:%M:%S"
    )


def _trend_state_counts(
    summary: ReliabilityTrendSummary,
) -> dict[ReliabilityRecoveryState, int]:
    return {
        state: sum(1 for item in summary.items if item.recovery_state == state)
        for state in ReliabilityRecoveryState
    }


def format_reliability_trend_report(
    recent: ReliabilityTrendSummary,
    weekly: ReliabilityTrendSummary,
    *,
    item_limit: int = 8,
) -> str:
    if isinstance(item_limit, bool) or not isinstance(item_limit, int):
        raise ValueError("item_limit must be an integer")
    if item_limit < 1 or item_limit > 20:
        raise ValueError("item_limit is outside the reviewed range")
    recent_counts = _trend_state_counts(recent)
    weekly_counts = _trend_state_counts(weekly)
    lines = [
        "结构化故障趋势（只读）",
        "范围：只统计已接入 P2.47 的固定结构化失败/降级事件；不读取聊天正文或原始异常。",
        "",
        "最近 24 小时：",
        (
            f"- 失败/降级 {recent.failure_occurrence_count} 次，"
            f"涉及 {len(recent.items)} 个故障组。"
        ),
        (
            "- 状态："
            f"未恢复 {recent_counts[ReliabilityRecoveryState.UNRESOLVED]}｜"
            f"已恢复 {recent_counts[ReliabilityRecoveryState.RECOVERED]}｜"
            f"反复发生 {recent_counts[ReliabilityRecoveryState.RECURRING]}｜"
            "证据不足 "
            f"{recent_counts[ReliabilityRecoveryState.INSUFFICIENT_EVIDENCE]}。"
        ),
    ]
    if recent.items:
        lines.extend(["", "重点故障："])
        for index, item in enumerate(recent.items[:item_limit], start=1):
            state_label = RECOVERY_STATE_LABELS[item.recovery_state]
            lines.extend(
                [
                    f"{index}. {item.component} / {item.operation}",
                    (
                        f"   {CATEGORY_LABELS[item.category]} / {item.code}｜"
                        f"{item.occurrence_count} 次｜{state_label}"
                    ),
                    (
                        f"   首次 {_trend_time(item.first_seen_at)}｜"
                        f"最后失败 {_trend_time(item.last_seen_at)}"
                    ),
                ]
            )
            if (
                item.last_success_at is not None
                and item.recovery_state
                != ReliabilityRecoveryState.INSUFFICIENT_EVIDENCE
            ):
                lines.append(f"   最近成功 {_trend_time(item.last_success_at)}")
        omitted = len(recent.items) - item_limit
        if omitted > 0:
            lines.append(f"- 另有 {omitted} 个故障组未展开。")
    else:
        lines.append("- 当前窗口内未发现结构化失败或降级事件。")

    lines.extend(
        [
            "",
            "最近 7 天摘要：",
            (
                f"- 失败/降级 {weekly.failure_occurrence_count} 次，"
                f"涉及 {len(weekly.items)} 个故障组。"
            ),
            (
                "- 状态："
                f"未恢复 {weekly_counts[ReliabilityRecoveryState.UNRESOLVED]}｜"
                f"已恢复 {weekly_counts[ReliabilityRecoveryState.RECOVERED]}｜"
                f"反复发生 {weekly_counts[ReliabilityRecoveryState.RECURRING]}｜"
                "证据不足 "
                f"{weekly_counts[ReliabilityRecoveryState.INSUFFICIENT_EVIDENCE]}。"
            ),
            "",
            "说明：没有结构化故障不等于已证明系统持续在线；未接入组件仍需结合可靠性巡检和最近错误查看。",
            "本命令未调用 Main LLM、Tavily、RAG 或外部模型，未告警、修复、重试、重启或清理数据。",
        ]
    )
    return "\n".join(lines)


def _latest_runtime_start():
    ensure_database()
    with connect() as connection:
        return connection.execute(
            """
            SELECT *
            FROM reliability_event_buckets
            WHERE component = 'bot_runtime'
              AND operation = 'lifecycle'
              AND code = 'runtime_started'
              AND outcome = 'succeeded'
            ORDER BY last_seen_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()


def _runtime_has_clean_stop(runtime_id: str, started_at: datetime) -> bool:
    ensure_database()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT 1
            FROM reliability_event_buckets
            WHERE runtime_id = ?
              AND component = 'bot_runtime'
              AND operation = 'lifecycle'
              AND code = 'runtime_stopped'
              AND outcome = 'succeeded'
              AND last_seen_at >= ?
            LIMIT 1
            """,
            (runtime_id, _datetime_text(started_at)),
        ).fetchone()
    return row is not None


def begin_runtime_lifecycle(
    *,
    runtime_id: str | None = None,
    occurred_at: datetime | None = None,
) -> RuntimeLifecycleStart:
    current_runtime_id = _validate_runtime_id(runtime_id or process_runtime_id())
    current_time = _normalized_datetime(occurred_at or datetime.now(UTC))
    previous = _latest_runtime_start()
    suspected_previous_runtime_id: str | None = None
    if previous is not None:
        previous_runtime_id = str(previous["runtime_id"])
        previous_started_at = _datetime_from_text(previous["last_seen_at"])
        if (
            previous_runtime_id != current_runtime_id
            and not _runtime_has_clean_stop(previous_runtime_id, previous_started_at)
        ):
            suspected_previous_runtime_id = previous_runtime_id
            record_result_safely(
                component="bot_runtime",
                operation="lifecycle",
                code="suspected_abnormal_exit",
                outcome=ReliabilityOutcome.DEGRADED,
                occurred_at=current_time,
                runtime_id=previous_runtime_id,
            )
    event = create_reliability_event(
        component="bot_runtime",
        operation="lifecycle",
        code="runtime_started",
        outcome=ReliabilityOutcome.SUCCEEDED,
        occurred_at=current_time,
        runtime_id=current_runtime_id,
    )
    record_reliability_event(event)
    return RuntimeLifecycleStart(current_runtime_id, suspected_previous_runtime_id)


def finish_runtime_lifecycle(
    *,
    runtime_id: str | None = None,
    occurred_at: datetime | None = None,
) -> ReliabilityEventBucket:
    event = create_reliability_event(
        component="bot_runtime",
        operation="lifecycle",
        code="runtime_stopped",
        outcome=ReliabilityOutcome.SUCCEEDED,
        occurred_at=occurred_at,
        runtime_id=runtime_id,
    )
    return record_reliability_event(event)


def begin_runtime_lifecycle_safely(
    *,
    runtime_id: str | None = None,
    occurred_at: datetime | None = None,
) -> RuntimeLifecycleStart | None:
    try:
        return begin_runtime_lifecycle(runtime_id=runtime_id, occurred_at=occurred_at)
    except Exception:
        return None


def finish_runtime_lifecycle_safely(
    *,
    runtime_id: str | None = None,
    occurred_at: datetime | None = None,
) -> bool:
    try:
        finish_runtime_lifecycle(runtime_id=runtime_id, occurred_at=occurred_at)
    except Exception:
        return False
    return True
