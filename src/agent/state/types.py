from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # Conversation
    messages: Annotated[list[BaseMessage], add_messages]
    user_input: str

    # Control
    intent: str  # "check" | "check_and_fix" | "fix" | "unknown"
    target: str | None
    approved: bool
    attempts: int
    phase: str  # "start" | "have_info" | "have_diagnosis" | "fixed" | "verified"

    # Network data
    network_db: dict
    observations: list[dict]
    diagnosis: dict
    needs_fix: bool
    plan: dict

    # Remediation / verify
    changes: list[dict]
    verify: dict
