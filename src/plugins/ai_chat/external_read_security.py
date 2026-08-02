from __future__ import annotations

import ipaddress
import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date, timedelta
from enum import Enum
from urllib.parse import urlsplit


EXTERNAL_READ_MAX_QUERY_CHARS = 300
EXTERNAL_READ_MAX_SEARCH_QUERY_CHARS = 50
EXTERNAL_READ_MAX_RESULTS = 10
EXTERNAL_READ_MAX_RESPONSE_BYTES = 262_144
EXTERNAL_READ_MAX_TIMEOUT_SECONDS = 15

EXTERNAL_READ_SCENES = frozenset(
    {
        "general_lookup",
        "official_update",
        "current_status",
        "technical_docs",
        "news_summary",
        "recommendation",
        "comparison",
    }
)


class ExternalReadPolicyCategory(str, Enum):
    INVALID_QUERY = "invalid_query"
    SENSITIVE_QUERY = "sensitive_query"
    UNSAFE_PROVIDER_ENDPOINT = "unsafe_provider_endpoint"
    UNSAFE_RESOLVED_ADDRESS = "unsafe_resolved_address"
    INVALID_BUDGET = "invalid_budget"
    REQUEST_TIMEOUT = "request_timeout"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    RESPONSE_TOO_LARGE = "response_too_large"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    SANITIZATION_FAILED = "sanitization_failed"


class ExternalReadPolicyError(ValueError):
    def __init__(self, category: ExternalReadPolicyCategory, detail: str) -> None:
        super().__init__(detail)
        self.category = category
        self.detail = detail


class ExternalReadStagePolicyError(ExternalReadPolicyError):
    """Policy failure with bounded, non-content external-read stage metadata."""

    def __init__(
        self,
        category: ExternalReadPolicyCategory,
        detail: str,
        *,
        search_stage: str,
        provider_request_count: int,
    ) -> None:
        super().__init__(category, detail)
        if search_stage not in {
            "official",
            "media_fallback",
            "primary",
            "secondary",
        }:
            raise ValueError("external read failure search stage is invalid")
        expected_request_counts = (
            {1, 2} if search_stage == "primary" else {1}
            if search_stage == "official"
            else {2}
        )
        if (
            isinstance(provider_request_count, bool)
            or not isinstance(provider_request_count, int)
            or provider_request_count not in expected_request_counts
        ):
            raise ValueError("external read failure provider request count is invalid")
        self.search_stage = search_stage
        self.provider_request_count = provider_request_count
        self.synthesis_request_count = 0


@dataclass(frozen=True)
class ExternalReadEndpoint:
    base_url: str
    source_host: str


@dataclass(frozen=True)
class ExternalReadTimeWindow:
    start_date: date
    end_date: date
    kind: str

    def __post_init__(self) -> None:
        if not isinstance(self.start_date, date) or not isinstance(
            self.end_date,
            date,
        ):
            raise TypeError("external read time window dates are invalid")
        if self.start_date > self.end_date:
            raise ValueError("external read time window is reversed")
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,31}", self.kind):
            raise ValueError("external read time window kind is invalid")

    @property
    def start_iso(self) -> str:
        return self.start_date.isoformat()

    @property
    def end_iso(self) -> str:
        return self.end_date.isoformat()


@dataclass(frozen=True)
class ExternalReadTemporalQuery:
    query: str
    time_window: ExternalReadTimeWindow | None = None
    search_question: str = ""


@dataclass(frozen=True)
class ExternalReadSearchPlan:
    """MainAgent-authored bounded provider plan; query text is never persisted."""

    primary_query: str
    primary_source_scope: str
    primary_time_range: str = ""
    primary_evidence_role: str = "direct_answer"
    secondary_query: str = ""
    secondary_source_scope: str = ""
    secondary_time_range: str = ""
    secondary_evidence_role: str = ""
    secondary_mode: str = "none"
    planning_mode: str = "main_agent"
    scene: str = "general_lookup"

    def __post_init__(self) -> None:
        primary_query = normalize_external_read_search_query(self.primary_query)
        if self.primary_source_scope not in {"official", "general", "news"}:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.INVALID_QUERY,
                "primary source scope is invalid",
            )
        primary_time_range = self.primary_time_range.strip()
        if primary_time_range not in {
            "",
            "day",
            "week",
            "month",
            "six_months",
            "year",
        }:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.INVALID_QUERY,
                "primary time range is invalid",
            )
        evidence_roles = {
            "context",
            "direct_answer",
            "official_confirmation",
            "reported_candidate",
            "recommendation",
        }
        primary_evidence_role = self.primary_evidence_role.strip()
        if primary_evidence_role not in evidence_roles:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.INVALID_QUERY,
                "primary evidence role is invalid",
            )
        if self.secondary_mode not in {"none", "if_no_results", "always"}:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.INVALID_QUERY,
                "secondary search mode is invalid",
            )
        if self.planning_mode not in {"main_agent", "legacy_fixed"}:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.INVALID_QUERY,
                "external read planning mode is invalid",
            )
        scene = self.scene.strip().lower()
        if scene not in EXTERNAL_READ_SCENES:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.INVALID_QUERY,
                "external read scene is invalid",
            )
        secondary_query = self.secondary_query.strip()
        secondary_scope = self.secondary_source_scope.strip()
        secondary_time_range = self.secondary_time_range.strip()
        secondary_evidence_role = self.secondary_evidence_role.strip()
        if self.secondary_mode == "none":
            if (
                secondary_query
                or secondary_scope
                or secondary_time_range
                or secondary_evidence_role
            ):
                raise ExternalReadPolicyError(
                    ExternalReadPolicyCategory.INVALID_QUERY,
                    "disabled secondary search must not include a query or source scope",
                )
        else:
            secondary_query = normalize_external_read_search_query(secondary_query)
            if secondary_scope not in {"official", "general", "news"}:
                raise ExternalReadPolicyError(
                    ExternalReadPolicyCategory.INVALID_QUERY,
                    "secondary source scope is invalid",
                )
            if secondary_time_range not in {
                "",
                "day",
                "week",
                "month",
                "six_months",
                "year",
            }:
                raise ExternalReadPolicyError(
                    ExternalReadPolicyCategory.INVALID_QUERY,
                    "secondary time range is invalid",
                )
            if not secondary_evidence_role:
                secondary_evidence_role = "direct_answer"
            if secondary_evidence_role not in evidence_roles:
                raise ExternalReadPolicyError(
                    ExternalReadPolicyCategory.INVALID_QUERY,
                    "secondary evidence role is invalid",
                )
        object.__setattr__(self, "primary_query", primary_query)
        object.__setattr__(self, "primary_time_range", primary_time_range)
        object.__setattr__(self, "primary_evidence_role", primary_evidence_role)
        object.__setattr__(self, "secondary_query", secondary_query)
        object.__setattr__(self, "secondary_source_scope", secondary_scope)
        object.__setattr__(self, "secondary_time_range", secondary_time_range)
        object.__setattr__(
            self,
            "secondary_evidence_role",
            secondary_evidence_role,
        )
        object.__setattr__(self, "scene", scene)


@dataclass(frozen=True)
class ExternalReadBudget:
    max_results: int = EXTERNAL_READ_MAX_RESULTS
    max_response_bytes: int = EXTERNAL_READ_MAX_RESPONSE_BYTES
    timeout_seconds: int = 10
    external_request_count: int = 1
    redirect_count: int = 0
    retry_count: int = 0

    def __post_init__(self) -> None:
        limits = (
            ("max_results", self.max_results, 1, EXTERNAL_READ_MAX_RESULTS),
            (
                "max_response_bytes",
                self.max_response_bytes,
                1,
                EXTERNAL_READ_MAX_RESPONSE_BYTES,
            ),
            (
                "timeout_seconds",
                self.timeout_seconds,
                1,
                EXTERNAL_READ_MAX_TIMEOUT_SECONDS,
            ),
        )
        for name, value, minimum, maximum in limits:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ExternalReadPolicyError(
                    ExternalReadPolicyCategory.INVALID_BUDGET,
                    f"{name} must be an integer",
                )
            if not minimum <= value <= maximum:
                raise ExternalReadPolicyError(
                    ExternalReadPolicyCategory.INVALID_BUDGET,
                    f"{name} must be between {minimum} and {maximum}",
                )

        fixed_counts = (
            ("external_request_count", self.external_request_count, 1),
            ("redirect_count", self.redirect_count, 0),
            ("retry_count", self.retry_count, 0),
        )
        for name, value, expected in fixed_counts:
            if isinstance(value, bool) or not isinstance(value, int) or value != expected:
                raise ExternalReadPolicyError(
                    ExternalReadPolicyCategory.INVALID_BUDGET,
                    f"{name} must equal {expected}",
                )


_SENSITIVE_QUERY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:api[\s_-]?key|access[\s_-]?token|refresh[\s_-]?token|token|password|passwd|secret)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\bauthorization\s*[:=]\s*(?:bearer|basic)\s+\S+", re.IGNORECASE),
    re.compile(r"\bcookie\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(
        r"(?:手机号|手机|联系电话|电话)\s*[:：=]?\s*(?:\+?86[-\s]?)?1[3-9]\d{9}"
    ),
    re.compile(r"(?:qq(?:号|号码)?|企鹅号)\s*[:：=]?\s*[1-9]\d{4,11}", re.IGNORECASE),
    re.compile(
        r"(?:身份证(?:号|号码)?|公民身份号码)\s*[:：=]?\s*\d{17}[\dXx]"
    ),
)

_LOCAL_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|\s)[A-Za-z]:[\\/]+\S*"),
    re.compile(r"(?:^|\s)\\\\[^\s\\/]+[\\/]+\S*"),
    re.compile(
        r"(?:^|\s)/(?:Users|home|etc|var|tmp|root|mnt|opt|srv|proc|sys|dev)(?:/|\s|$)\S*",
        re.IGNORECASE,
    ),
)

_URL_PATTERN = re.compile(r"\b(?:https?|ftp|file)://\S+", re.IGNORECASE)

_RELATIVE_SIX_MONTH_PATTERNS = (
    re.compile(r"(?:最近|近|过去|前)(?:半年|六\s*个?月|6\s*个?月)"),
    re.compile(
        r"\b(?:last|past|recent)\s+(?:six\s+months?|half[- ]year)\b",
        re.IGNORECASE,
    ),
)
_RELATIVE_MONTH_PATTERNS = (
    re.compile(r"(?:当前日期|今天|今日)?(?:往前|向前|前推)(?:一个|1\s*个?)月"),
    re.compile(r"(?:最近|近|过去|前)(?:一个|1\s*个?)月"),
    re.compile(r"\b(?:last|past|recent)\s+(?:one\s+)?month\b", re.IGNORECASE),
)
_RELATIVE_WEEK_PATTERNS = (
    re.compile(r"(?:最近|近|过去|前)(?:一|1)周"),
    re.compile(r"\b(?:last|past|recent)\s+(?:one\s+)?week\b", re.IGNORECASE),
)
_CURRENT_MONTH_PATTERN = re.compile(r"本月|这个月|\bthis\s+month\b", re.IGNORECASE)
_CURRENT_WEEK_PATTERN = re.compile(r"本周|这周|\bthis\s+week\b", re.IGNORECASE)
_TODAY_PATTERN = re.compile(r"今天|今日|\btoday\b", re.IGNORECASE)
_ABSOLUTE_DATE_RANGE_PATTERN = re.compile(
    r"(?<!\d)(\d{4}-\d{2}-\d{2})\s*(?:至|到|~|～|—|–)\s*"
    r"(\d{4}-\d{2}-\d{2})(?!\d)"
)
_VAGUE_RECENT_PATTERN = re.compile(
    r"最近|近期|近来|\brecent(?:ly)?\b",
    re.IGNORECASE,
)
_OFFICIAL_ONLY_PATTERNS = (
    re.compile(
        r"(?:只|仅)(?:看|查|用|要|参考|采用)?\s*"
        r"(?:官方|第一方)(?:来源|资料|公告|消息|页面|网站)?"
    ),
    re.compile(r"(?:仅限|只限于?)\s*(?:官方|第一方)"),
    re.compile(
        r"\b(?:official|first[- ]party)(?:\s+(?:sources?|pages?|announcements?))?"
        r"\s+only\b|\bonly\s+(?:official|first[- ]party)\b",
        re.IGNORECASE,
    ),
)

_NEXT_STATUS_MARKERS = (
    "下一个",
    "下个",
    "下一版",
    "下一期",
    "即将",
    "未发布",
    "next",
    "upcoming",
    "unreleased",
)
_CURRENT_STATUS_MARKERS = (
    "当前",
    "现在",
    "目前",
    "最新",
    "已经上线",
    "已上线",
    "current",
    "latest",
    "available now",
)
_LIFECYCLE_ENTITY_MARKERS = (
    "版本",
    "模型",
    "卡池",
    "角色",
    "活动",
    "发布",
    "上线",
    "release",
    "version",
    "model",
    "roster",
)
_COMPARISON_SCENE_MARKERS = (
    "对比",
    "比较",
    "区别",
    "差异",
    "哪个好",
    "怎么选",
    " vs ",
    " versus ",
    "compare",
)
_RECOMMENDATION_SCENE_MARKERS = (
    "推荐",
    "值得去",
    "值得买",
    "美食",
    "餐厅",
    "旅游",
    "攻略",
    "recommend",
)
_TECHNICAL_DOCS_SCENE_MARKERS = (
    "官方文档",
    "api",
    "sdk",
    "报错",
    "错误码",
    "兼容",
    "release notes",
    "changelog",
    "documentation",
)
_NEWS_SCENE_MARKERS = (
    "新闻",
    "动态",
    "进展",
    "发生了什么",
    "行业消息",
    "news",
    "developments",
)
_OFFICIAL_UPDATE_SCENE_MARKERS = (
    "更新",
    "发布",
    "上线",
    "公告",
    "新版本",
    "update",
    "release",
    "announcement",
)

_RELATIVE_WINDOW_TIME_RANGES = {
    "today": "day",
    "current_week": "week",
    "previous_week": "week",
    "current_month": "month",
    "previous_month": "month",
    "auto_recent_month": "month",
    "previous_six_months": "six_months",
}
_NEXT_BROADER_TIME_RANGE = {
    "day": "six_months",
    "week": "six_months",
    "month": "six_months",
}


def _normalize_untrusted_text(value: str) -> str:
    without_controls = "".join(
        " " if unicodedata.category(character).startswith("C") else character
        for character in value
    )
    return " ".join(without_controls.split())


def normalize_external_read_query(query: str) -> str:
    if not isinstance(query, str):
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.INVALID_QUERY,
            "query must be text",
        )
    normalized = _normalize_untrusted_text(query).strip()
    if not normalized:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.INVALID_QUERY,
            "query is empty",
        )
    if len(normalized) > EXTERNAL_READ_MAX_QUERY_CHARS:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.INVALID_QUERY,
            f"query exceeds {EXTERNAL_READ_MAX_QUERY_CHARS} characters",
        )
    if _URL_PATTERN.search(normalized):
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.INVALID_QUERY,
            "query must not contain a URL",
        )
    if any(pattern.search(normalized) for pattern in _LOCAL_PATH_PATTERNS):
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.SENSITIVE_QUERY,
            "query must not contain a local path",
        )
    if any(pattern.search(normalized) for pattern in _SENSITIVE_QUERY_PATTERNS):
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.SENSITIVE_QUERY,
            "query appears to contain a secret or explicitly identified personal data",
        )
    return normalized


def normalize_external_read_search_query(query: str) -> str:
    """Validate the exact short query that may be sent to the fixed provider."""

    normalized = normalize_external_read_query(query)
    if len(normalized) > EXTERNAL_READ_MAX_SEARCH_QUERY_CHARS:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.INVALID_QUERY,
            "search query exceeds "
            f"{EXTERNAL_READ_MAX_SEARCH_QUERY_CHARS} characters",
        )
    return normalized


def _previous_calendar_month_day(value: date) -> date:
    return _previous_calendar_months_day(value, months=1)


def _previous_calendar_months_day(value: date, *, months: int) -> date:
    if isinstance(months, bool) or not isinstance(months, int) or months < 1:
        raise ValueError("external read calendar month count is invalid")
    month_index = value.year * 12 + value.month - 1 - months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def external_read_time_window_for_range(
    time_range: str,
    *,
    reference_date: date,
    kind: str | None = None,
) -> ExternalReadTimeWindow:
    if time_range == "day":
        start_date = reference_date
    elif time_range == "week":
        start_date = reference_date - timedelta(days=7)
    elif time_range == "month":
        start_date = _previous_calendar_month_day(reference_date)
    elif time_range == "six_months":
        start_date = _previous_calendar_months_day(reference_date, months=6)
    elif time_range == "year":
        try:
            start_date = reference_date.replace(year=reference_date.year - 1)
        except ValueError:
            start_date = reference_date.replace(
                year=reference_date.year - 1,
                day=28,
            )
    else:
        raise ValueError("external read time range is invalid")
    return ExternalReadTimeWindow(
        start_date=start_date,
        end_date=reference_date,
        kind=kind or f"rolling_{time_range}",
    )


def resolve_external_read_time_window(
    query: str,
    *,
    reference_date: date,
) -> tuple[ExternalReadTimeWindow | None, re.Match[str] | None]:
    if not isinstance(reference_date, date):
        raise TypeError("external read reference date is invalid")
    for pattern in _RELATIVE_SIX_MONTH_PATTERNS:
        matched = pattern.search(query)
        if matched is not None:
            return (
                ExternalReadTimeWindow(
                    start_date=_previous_calendar_months_day(
                        reference_date,
                        months=6,
                    ),
                    end_date=reference_date,
                    kind="previous_six_months",
                ),
                matched,
            )
    for pattern in _RELATIVE_MONTH_PATTERNS:
        matched = pattern.search(query)
        if matched is not None:
            return (
                ExternalReadTimeWindow(
                    start_date=_previous_calendar_month_day(reference_date),
                    end_date=reference_date,
                    kind="previous_month",
                ),
                matched,
            )
    for pattern in _RELATIVE_WEEK_PATTERNS:
        matched = pattern.search(query)
        if matched is not None:
            return (
                ExternalReadTimeWindow(
                    start_date=reference_date - timedelta(days=7),
                    end_date=reference_date,
                    kind="previous_week",
                ),
                matched,
            )
    matched = _CURRENT_MONTH_PATTERN.search(query)
    if matched is not None:
        return (
            ExternalReadTimeWindow(
                start_date=reference_date.replace(day=1),
                end_date=reference_date,
                kind="current_month",
            ),
            matched,
        )
    matched = _CURRENT_WEEK_PATTERN.search(query)
    if matched is not None:
        return (
            ExternalReadTimeWindow(
                start_date=reference_date - timedelta(days=reference_date.weekday()),
                end_date=reference_date,
                kind="current_week",
            ),
            matched,
        )
    matched = _TODAY_PATTERN.search(query)
    if matched is not None:
        return (
            ExternalReadTimeWindow(
                start_date=reference_date,
                end_date=reference_date,
                kind="today",
            ),
            matched,
        )
    matched = _ABSOLUTE_DATE_RANGE_PATTERN.search(query)
    if matched is not None:
        try:
            start_date = date.fromisoformat(matched.group(1))
            end_date = date.fromisoformat(matched.group(2))
        except ValueError as exc:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.INVALID_QUERY,
                "external read absolute date range is invalid",
            ) from exc
        if start_date > end_date:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.INVALID_QUERY,
                "external read absolute date range is reversed",
            )
        return (
            ExternalReadTimeWindow(
                start_date=start_date,
                end_date=end_date,
                kind="absolute_range",
            ),
            matched,
        )
    matched = _VAGUE_RECENT_PATTERN.search(query)
    if matched is not None:
        return (
            external_read_time_window_for_range(
                "month",
                reference_date=reference_date,
                kind="auto_recent_month",
            ),
            matched,
        )
    return None, None


def external_read_time_window_requires_clarification(
    query: str,
    *,
    reference_date: date,
) -> bool:
    """Return whether recency is still unresolved after deterministic defaults."""

    normalized = normalize_external_read_query(query)
    time_window, _ = resolve_external_read_time_window(
        normalized,
        reference_date=reference_date,
    )
    return time_window is None and _VAGUE_RECENT_PATTERN.search(normalized) is not None


def _fallback_search_query(query: str) -> str:
    candidate = query
    for pattern in (
        *_RELATIVE_SIX_MONTH_PATTERNS,
        *_RELATIVE_MONTH_PATTERNS,
        *_RELATIVE_WEEK_PATTERNS,
        _CURRENT_MONTH_PATTERN,
        _CURRENT_WEEK_PATTERN,
        _TODAY_PATTERN,
        _ABSOLUTE_DATE_RANGE_PATTERN,
        _VAGUE_RECENT_PATTERN,
    ):
        candidate = pattern.sub(" ", candidate)
    candidate = " ".join(candidate.split()).strip(" ，,;；:-")
    if not candidate:
        candidate = query
    return normalize_external_read_search_query(candidate)


def _contains_any_marker(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(marker in lowered for marker in markers)


def external_read_query_requires_official_sources(query: str) -> bool:
    """Return whether the owner explicitly restricted evidence to first-party sources."""

    if not isinstance(query, str):
        return False
    return any(pattern.search(query) is not None for pattern in _OFFICIAL_ONLY_PATTERNS)


def external_read_query_requires_next_status(query: str) -> bool:
    """Return whether the owner asked for a lifecycle state after the current one."""

    return isinstance(query, str) and _contains_any_marker(query, _NEXT_STATUS_MARKERS)


def infer_external_read_scene(query: str) -> str:
    """Infer a bounded business scene without retaining the source query."""

    normalized = normalize_external_read_query(query)
    has_lifecycle_entity = _contains_any_marker(
        normalized,
        _LIFECYCLE_ENTITY_MARKERS,
    )
    if has_lifecycle_entity and (
        _contains_any_marker(normalized, _NEXT_STATUS_MARKERS)
        or _contains_any_marker(normalized, _CURRENT_STATUS_MARKERS)
    ):
        return "current_status"
    if _contains_any_marker(normalized, _COMPARISON_SCENE_MARKERS):
        return "comparison"
    if _contains_any_marker(normalized, _RECOMMENDATION_SCENE_MARKERS):
        return "recommendation"
    if _contains_any_marker(normalized, _TECHNICAL_DOCS_SCENE_MARKERS):
        return "technical_docs"
    if _contains_any_marker(normalized, _NEWS_SCENE_MARKERS):
        return "news_summary"
    if _contains_any_marker(normalized, _OFFICIAL_UPDATE_SCENE_MARKERS):
        return "official_update"
    return "general_lookup"


def _current_status_baseline_query(candidate_query: str) -> str:
    baseline = candidate_query
    replacements = (
        ("下一个版本", "当前已上线版本"),
        ("下个版本", "当前已上线版本"),
        ("下一版本", "当前已上线版本"),
        ("下一版", "当前版本"),
        ("下一个", "当前"),
        ("下个", "当前"),
        ("即将上线", "当前已上线"),
        ("即将发布", "当前已发布"),
        ("最新版本预告", "当前已上线版本"),
        ("最新版本", "当前已上线版本"),
        ("upcoming version", "current released version"),
        ("next version", "current released version"),
        ("upcoming", "current released"),
        ("next", "current"),
    )
    for old, new in replacements:
        baseline = re.sub(re.escape(old), new, baseline, flags=re.IGNORECASE)
    baseline = re.sub(r"(?:官方)?(?:预告|前瞻)", " ", baseline)
    if baseline == candidate_query:
        baseline = f"当前已上线 {candidate_query}"
    return normalize_external_read_search_query(
        baseline[:EXTERNAL_READ_MAX_SEARCH_QUERY_CHARS]
    )


def _is_explicit_current_status_baseline_query(query: str) -> bool:
    return _contains_any_marker(
        query,
        (
            "当前",
            "现在",
            "目前",
            "已经上线",
            "已上线",
            "已经发布",
            "已发布",
            "current",
            "available now",
            "released version",
        ),
    )


def adapt_external_read_scene_plan(
    plan: ExternalReadSearchPlan,
    *,
    source_query: str,
) -> ExternalReadSearchPlan:
    """Apply deterministic scene defaults inside the fixed two-read budget."""

    inferred_scene = infer_external_read_scene(source_query)
    scene = inferred_scene if plan.scene == "general_lookup" else plan.scene
    adapted = replace(plan, scene=scene)
    official_only = external_read_query_requires_official_sources(source_query)
    if official_only:
        adapted = replace(
            adapted,
            primary_source_scope="official",
            secondary_source_scope=(
                "official" if adapted.secondary_mode != "none" else ""
            ),
        )
    if scene != "current_status" or not external_read_query_requires_next_status(
        source_query
    ):
        return adapted
    candidate_query = (
        adapted.secondary_query
        if adapted.secondary_mode != "none"
        else adapted.primary_query
    )
    baseline_query = adapted.primary_query
    if not _is_explicit_current_status_baseline_query(baseline_query):
        baseline_query = _current_status_baseline_query(baseline_query)
    return ExternalReadSearchPlan(
        primary_query=baseline_query,
        primary_source_scope="official" if official_only else "general",
        primary_time_range="",
        primary_evidence_role="context",
        secondary_query=candidate_query,
        secondary_source_scope="official" if official_only else "news",
        secondary_time_range=(
            adapted.secondary_time_range
            or adapted.primary_time_range
            or "month"
        ),
        secondary_evidence_role=(
            "official_confirmation" if official_only else "reported_candidate"
        ),
        secondary_mode="always",
        planning_mode=adapted.planning_mode,
        scene=scene,
    )


def adapt_recent_external_read_search_plan(
    plan: ExternalReadSearchPlan,
    *,
    source_query: str,
    time_window: ExternalReadTimeWindow | None,
) -> ExternalReadSearchPlan:
    """Reserve the second provider read for a broader nearest-result fallback."""
    if time_window is None or time_window.kind not in _RELATIVE_WINDOW_TIME_RANGES:
        return plan
    if _VAGUE_RECENT_PATTERN.search(source_query) is None and not any(
        pattern.search(source_query)
        for pattern in (
            *_RELATIVE_SIX_MONTH_PATTERNS,
            *_RELATIVE_MONTH_PATTERNS,
            *_RELATIVE_WEEK_PATTERNS,
            _CURRENT_MONTH_PATTERN,
            _CURRENT_WEEK_PATTERN,
            _TODAY_PATTERN,
        )
    ):
        return plan

    primary_time_range = _RELATIVE_WINDOW_TIME_RANGES[time_window.kind]
    fallback_time_range = _NEXT_BROADER_TIME_RANGE.get(primary_time_range)
    if fallback_time_range is None:
        return ExternalReadSearchPlan(
            primary_query=plan.primary_query,
            primary_source_scope=plan.primary_source_scope,
            primary_time_range=primary_time_range,
            primary_evidence_role=plan.primary_evidence_role,
            secondary_query=plan.secondary_query,
            secondary_source_scope=plan.secondary_source_scope,
            secondary_time_range=plan.secondary_time_range,
            secondary_evidence_role=plan.secondary_evidence_role,
            secondary_mode=plan.secondary_mode,
            planning_mode=plan.planning_mode,
            scene=plan.scene,
        )
    if plan.secondary_mode == "always":
        return ExternalReadSearchPlan(
            primary_query=plan.primary_query,
            primary_source_scope=plan.primary_source_scope,
            primary_time_range=primary_time_range,
            primary_evidence_role=plan.primary_evidence_role,
            secondary_query=plan.secondary_query,
            secondary_source_scope=plan.secondary_source_scope,
            secondary_time_range=plan.secondary_time_range,
            secondary_evidence_role=plan.secondary_evidence_role,
            secondary_mode=plan.secondary_mode,
            planning_mode=plan.planning_mode,
            scene=plan.scene,
        )

    secondary_query = _fallback_search_query(
        plan.secondary_query or plan.primary_query
    )
    secondary_scope = plan.secondary_source_scope or plan.primary_source_scope
    secondary_role = plan.secondary_evidence_role or plan.primary_evidence_role
    official_only = external_read_query_requires_official_sources(source_query)
    if (
        plan.primary_source_scope == "official"
        and secondary_scope == "official"
        and not official_only
    ):
        secondary_scope = "general"
        secondary_role = "reported_candidate"
    return ExternalReadSearchPlan(
        primary_query=plan.primary_query,
        primary_source_scope=plan.primary_source_scope,
        primary_time_range=primary_time_range,
        primary_evidence_role=plan.primary_evidence_role,
        secondary_query=secondary_query,
        secondary_source_scope=secondary_scope,
        secondary_time_range=fallback_time_range,
        secondary_evidence_role=secondary_role,
        secondary_mode="if_no_results",
        planning_mode=plan.planning_mode,
        scene=plan.scene,
    )


def resolve_external_read_secondary_time_window(
    *,
    primary_time_window: ExternalReadTimeWindow | None,
    search_plan: ExternalReadSearchPlan,
    reference_date: date,
) -> ExternalReadTimeWindow | None:
    if (
        primary_time_window is None
        or search_plan.secondary_mode != "if_no_results"
        or not search_plan.secondary_time_range
    ):
        return primary_time_window
    primary_range = _RELATIVE_WINDOW_TIME_RANGES.get(primary_time_window.kind)
    if (
        primary_range is None
        or _NEXT_BROADER_TIME_RANGE.get(primary_range)
        != search_plan.secondary_time_range
    ):
        return primary_time_window
    return external_read_time_window_for_range(
        search_plan.secondary_time_range,
        reference_date=reference_date,
        kind="nearest_available_fallback",
    )


def rewrite_external_read_temporal_query(
    query: str,
    *,
    reference_date: date,
) -> ExternalReadTemporalQuery:
    normalized = normalize_external_read_query(query)
    time_window, matched = resolve_external_read_time_window(
        normalized,
        reference_date=reference_date,
    )
    if time_window is None or matched is None:
        return ExternalReadTemporalQuery(
            query=normalized,
            search_question=normalized,
        )
    absolute_range = f"{time_window.start_iso} 至 {time_window.end_iso}"
    search_question = (
        normalized[: matched.start()]
        + absolute_range
        + normalized[matched.end() :]
    ).strip()
    rewritten = f"{search_question}；可信日期范围：{absolute_range}"
    rewritten = normalize_external_read_query(rewritten)
    return ExternalReadTemporalQuery(
        query=rewritten,
        time_window=time_window,
        search_question=normalize_external_read_query(search_question),
    )


def canonicalize_external_host(value: str) -> str:
    host = value.strip().rstrip(".").lower()
    if not host:
        return ""
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider hostname is invalid",
        ) from exc


def validate_external_read_endpoint(
    base_url: str,
    *,
    allowed_hosts: tuple[str, ...],
) -> ExternalReadEndpoint:
    if not isinstance(base_url, str) or not base_url.strip():
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint is empty",
        )
    if "\\" in base_url or any(
        unicodedata.category(character).startswith("C") for character in base_url
    ):
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint contains unsafe characters",
        )
    try:
        parsed = urlsplit(base_url.strip())
        port = parsed.port
        username = parsed.username
        password = parsed.password
    except ValueError as exc:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint is invalid",
        ) from exc

    if parsed.scheme.lower() != "https":
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint must use https",
        )
    if username is not None or password is not None:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint must not contain userinfo",
        )
    if parsed.fragment:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint must not contain a fragment",
        )
    if parsed.query:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint must not contain a query string",
        )
    if port not in {None, 443}:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider endpoint must use port 443",
        )

    host = canonicalize_external_host(parsed.hostname or "")
    allowed = {
        canonicalize_external_host(item) for item in allowed_hosts if item.strip()
    }
    if not allowed or host not in allowed:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_PROVIDER_ENDPOINT,
            "provider hostname is not allowlisted",
        )

    try:
        literal_address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        literal_address = None
    if literal_address is not None:
        validate_external_read_addresses((str(literal_address),))

    return ExternalReadEndpoint(base_url=base_url.strip(), source_host=host)


def validate_external_read_addresses(addresses: tuple[str, ...]) -> tuple[str, ...]:
    if not addresses:
        raise ExternalReadPolicyError(
            ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS,
            "provider hostname resolved to no addresses",
        )

    normalized: list[str] = []
    for value in addresses:
        try:
            address = ipaddress.ip_address(str(value).strip())
        except ValueError as exc:
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS,
                "provider hostname resolved to an invalid address",
            ) from exc
        if (
            not address.is_global
            or address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
            or address.is_unspecified
        ):
            raise ExternalReadPolicyError(
                ExternalReadPolicyCategory.UNSAFE_RESOLVED_ADDRESS,
                "provider hostname resolved to a non-public address",
            )
        canonical = str(address)
        if canonical not in normalized:
            normalized.append(canonical)
    return tuple(normalized)
