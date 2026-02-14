from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RootCause(BaseModel):
    cause: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class Diagnosis(BaseModel):
    root_causes: list[RootCause] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    plan_steps: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    rollback: list[str] = Field(default_factory=list)
    requires_approval: bool = True


class VerifyResult(BaseModel):
    passed: bool
    evidence: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)


class IntentOut(BaseModel):
    intent: str = Field(description='One of: "check", "check_and_fix", "fix", "unknown"')
    target: str | None = Field(default=None, description="Optional target device/site/service")
    approved: bool = Field(
        default=False, description="True only if user explicitly approved changes"
    )
    # Post-diagnosis decision
    needs_fix: bool | None = Field(default=None, description="Set after diagnosis is present")
    plan: Plan = Field(default_factory=Plan)


# Network schemas


class Device(BaseModel):
    name: str
    role: str | None = None  # "router", "switch", "host"
    mgmt_ip: str | None = None
    vendor: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)


class Link(BaseModel):
    a_device: str
    a_if: str | None = None
    b_device: str
    b_if: str | None = None
    kind: Literal["lldp", "cdp", "arp", "traceroute", "manual", "unknown"] = "unknown"
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class TopologyInfo(BaseModel):
    devices: list[Device] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    recent_changes: list[dict[str, Any]] = Field(default_factory=list)
