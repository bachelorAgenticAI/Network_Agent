from typing import Annotated, TypedDict, Optional
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    user_input: str

    intent: str
    target: Optional[str]

    observations: list[dict]
    diagnosis: dict
    needs_fix: bool
    plan: dict
    changes: list[dict]
    verify: dict

    phase: str  # "start" | "have_info" | "have_diagnosis" | "fixed" | "verified"
    approved: bool
    attempts: int
