from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeAlias

from ..policy.risk import RiskLevel


class ToolArgumentError(ValueError):
    """Raised when a tool request is missing or has invalid arguments."""


class ToolExecutionError(RuntimeError):
    """Raised when a registered tool cannot be executed."""


@dataclass(frozen=True)
class ToolContext:
    query: str = ""
    is_owner: bool = False
    is_group: bool = False
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    text: str
    metadata: dict[str, object] = field(default_factory=dict)


ToolExecutor: TypeAlias = Callable[
    [dict[str, Any], ToolContext],
    str | ToolResult | Awaitable[str | ToolResult],
]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    risk_level: RiskLevel
    required_arguments: tuple[str, ...] = ()
    optional_arguments: tuple[str, ...] = ()
    executor: ToolExecutor | None = None
    enabled: bool = True
    llm_visible: bool = True
    requires_approval: bool = False
    approval_resume_enabled: bool = False

    def validate_arguments(self, arguments: dict[str, Any]) -> dict[str, Any]:
        allowed = set(self.required_arguments) | set(self.optional_arguments)
        unknown = sorted(set(arguments) - allowed)
        if unknown:
            raise ToolArgumentError(
                f"{self.name} tool got unsupported arguments: {', '.join(unknown)}"
            )
        for field_name in self.required_arguments:
            value = arguments.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ToolArgumentError(f"{self.name} tool requires arguments.{field_name}")
        return dict(arguments)


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec] | None = None) -> None:
        self._specs: dict[str, ToolSpec] = {}
        for spec in specs or []:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        if not spec.name.strip():
            raise ValueError("tool name must be non-empty")
        if spec.name != spec.name.strip():
            raise ValueError(f"tool name must not have surrounding whitespace: {spec.name!r}")
        if spec.name in self._specs:
            raise ValueError(f"duplicate tool registered: {spec.name}")
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name.strip())

    def require(self, name: str) -> ToolSpec:
        spec = self.get(name)
        if spec is None or not spec.enabled:
            raise ToolArgumentError(f"unsupported tool: {name}")
        return spec

    def validate_arguments(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.require(name).validate_arguments(arguments)

    def visible_specs(self) -> list[ToolSpec]:
        return [spec for spec in self._specs.values() if spec.enabled and spec.llm_visible]

    def visible_tool_names(self) -> list[str]:
        return [spec.name for spec in self.visible_specs()]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        spec = self.require(name)
        validated = spec.validate_arguments(arguments)
        if spec.executor is None:
            raise ToolExecutionError(f"tool has no executor: {name}")
        value = spec.executor(validated, context)
        if inspect.isawaitable(value):
            value = await value
        if isinstance(value, ToolResult):
            return value
        return ToolResult(text=str(value))


def create_default_main_agent_tool_registry(
    *,
    include_dry_run_tools: bool = False,
) -> ToolRegistry:
    specs = [
        ToolSpec(
            name="dev_context",
            description="Read project development context through DevContextGraph.",
            risk_level=RiskLevel.READ_LOCAL,
            required_arguments=("query",),
            executor=None,
            enabled=True,
            llm_visible=True,
            requires_approval=False,
            approval_resume_enabled=False,
        )
    ]
    if include_dry_run_tools:
        specs.append(
            ToolSpec(
                name="dry_run_write_file",
                description="Simulate a local file write approval without writing files.",
                risk_level=RiskLevel.WRITE_LOCAL,
                required_arguments=("path", "content_summary"),
                executor=dry_run_write_file_executor,
                enabled=True,
                llm_visible=False,
                requires_approval=True,
                approval_resume_enabled=True,
            )
        )
    return ToolRegistry(specs)


def dry_run_write_file_executor(arguments: dict[str, Any], _context: ToolContext) -> ToolResult:
    path = str(arguments["path"]).strip()
    content_summary = str(arguments["content_summary"]).strip()
    return ToolResult(
        text="\n".join(
            [
                "dry_run_write_file result:",
                f"path: {path}",
                f"content_summary: {content_summary}",
                "side_effect: none",
            ]
        ),
        metadata={"dry_run": True, "path": path},
    )
