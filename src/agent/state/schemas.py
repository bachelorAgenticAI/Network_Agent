from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RootCause(BaseModel):
    cause: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class Diagnosis(BaseModel):
    root_causes: list[RootCause] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)

class PlanStep(BaseModel):
    id: int
    device: str  # "router<number>"
    action: str
    target: str | None = None
    parameters: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    problem: str = ""
    fix_summary: str = ""
    plan_steps: list[PlanStep] = Field(default_factory=list)

class VerifyResult(BaseModel):
    passed: bool
    evidence: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)


class IntentOut(BaseModel):
    intent: Literal["check", "check_and_fix"] = Field(description="Base intent of input")
    intent_description: str = Field(description="Explain the intent for other nodes")
    target: str | None = Field(default=None, description="Optional target device/site/service")
    # Post-diagnosis decision
    needs_fix: bool | None = Field(default=None, description="Set after diagnosis is present")
    plan: Plan = Field(default_factory=Plan)


# Network schemas
class KV(BaseModel):
    model_config = ConfigDict(extra="forbid")
    k: str
    v: str  # enklest; evt Union[str,int,float,bool,None]


class Device(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    role: Literal["router", "switch"] | None = None
    mgmt_ip: str | None = None
    vendor: str | None = None
    meta: list[KV] = Field(default_factory=list)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str | None = None
    detail: str | None = None
    meta: list[KV] = Field(default_factory=list)


class Link(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a_device: str
    a_if: str | None = None
    b_device: str
    b_if: str | None = None
    kind: Literal["lldp", "cdp", "arp", "traceroute", "manual", "unknown"] = "unknown"
    evidence: list[Evidence] = Field(default_factory=list)


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    meta: list[KV] = Field(default_factory=list)


class TopologyInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    devices: list[Device] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    recent_changes: list[Change] = Field(default_factory=list)


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim: str
    meta: list[KV] = Field(default_factory=list)


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    content: str | None = None
    meta: list[KV] = Field(default_factory=list)


class NetworkMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ts: str
    target: str


class NetworkDB(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topology: TopologyInfo = Field(default_factory=TopologyInfo)
    facts: list[Fact] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    meta: NetworkMeta | None = None


class FormatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    network_db: NetworkDB
