from __future__ import annotations

from langchain_core.messages import HumanMessage
from state.types import AgentState


def ingestion(state: AgentState) -> dict:
    txt = (state.get("user_input") or "").strip()
    if not txt:
        return {"phase": "start"}

    prev = state.get("messages") or []
    return {
        "phase": "start",
        "messages": prev + [HumanMessage(content=txt)],
        "intent": None,
        "target": None,
    }
