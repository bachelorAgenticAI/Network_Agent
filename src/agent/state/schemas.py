# Use Pydantic models to explcitly set the structure in state, easier for nodes/llm
from pydantic import BaseModel, Field
from typing import List, Optional

class RootCause(BaseModel):
    cause: str
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0

class Diagnosis(BaseModel):
    root_causes: List[RootCause] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)

class Plan(BaseModel):
    plan_steps: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)
    rollback: list[str] = Field(default_factory=list)
    requires_approval: bool = True
