"""TypedDict state contract shared by all graph nodes."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# This module defines the AgentState TypedDict, which specifies the structure of the state object passed between nodes in the agent's execution graph.
class AgentState(TypedDict, total=False):
    # Conversation
    messages: Annotated[list[BaseMessage], add_messages]
    user_input: str  # Used for alert

    # Control
    intent: str  # "check" | "check_and_fix"
    intent_description: str  # natural language explanation of intent for other nodes

    target: str | None
    attempts: int
    phase: str  # "start" | "have_info" | "have_diagnosis" | "fixed" | "verified"

    # Network data
    network_db: dict
    router_map: dict[str, str]
    available_router_args: list[str]
    observations: list[dict]
    diagnosis: dict
    needs_fix: bool
    plan: dict
    info_start_cursor: int

    # Remediation / verify
    changes: list[dict]
    remediation_step_idx: int
    remediation_done: bool
    verify: dict
    remedy_start_cursor: int
    verify_start_cursor: int
