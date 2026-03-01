from __future__ import annotations

from langchain_core.messages import HumanMessage
from state.types import AgentState


def ingestion(state: AgentState) -> dict:
    txt = (state.get("user_input") or "").strip()
    if not txt:
        return {"phase": "start"}

    # Reset state on new user input to avoid confusion from leftover state. This ensures the agent focuses on the current prompt.
    # Keep message history to maintain conversation context, but clear out any prior diagnosis, plan, etc. that could mislead the agent.
    return {
        "phase": "start",
        "user_input": txt,
        "messages": [HumanMessage(content=txt)],
        "intent": None,
        "target": None,
        "attempts": 0,
        "network_db": {},
        "observations": [],
        "diagnosis": None,
        "needs_fix": None,
        "plan": {},
        "changes": [],
        "verify": {},
        "remedy_start_cursor": 0,
    }
