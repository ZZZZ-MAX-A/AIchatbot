from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .risk import RiskLevel


class PolicyDecisionType(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True)
class PolicyDecision:
    type: PolicyDecisionType
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.type == PolicyDecisionType.ALLOW


@dataclass(frozen=True)
class ToolPolicyInput:
    risk_level: RiskLevel
    is_owner: bool
    is_group: bool
    enable_external_read: bool = False
    enable_local_write: bool = False
    enable_external_write: bool = False


def decide_tool_policy(value: ToolPolicyInput) -> PolicyDecision:
    if value.risk_level == RiskLevel.DANGEROUS:
        return PolicyDecision(PolicyDecisionType.DENY, "dangerous tools are disabled")
    if not value.is_owner:
        return PolicyDecision(PolicyDecisionType.DENY, "main agent tools require owner access")
    if value.is_group:
        return PolicyDecision(PolicyDecisionType.DENY, "main agent tools are private-only by default")
    if value.risk_level in {RiskLevel.INTERNAL, RiskLevel.READ_LOCAL}:
        return PolicyDecision(PolicyDecisionType.ALLOW)
    if value.risk_level == RiskLevel.READ_EXTERNAL:
        if value.enable_external_read:
            return PolicyDecision(PolicyDecisionType.ALLOW)
        return PolicyDecision(PolicyDecisionType.DENY, "external reads are disabled")
    if value.risk_level == RiskLevel.WRITE_LOCAL:
        if value.enable_local_write:
            return PolicyDecision(PolicyDecisionType.REQUIRE_APPROVAL, "local writes require approval")
        return PolicyDecision(PolicyDecisionType.DENY, "local writes are disabled")
    if value.risk_level == RiskLevel.WRITE_EXTERNAL:
        if value.enable_external_write:
            return PolicyDecision(PolicyDecisionType.REQUIRE_APPROVAL, "external writes require approval")
        return PolicyDecision(PolicyDecisionType.DENY, "external writes are disabled")
    return PolicyDecision(PolicyDecisionType.DENY, "unsupported risk level")
