from __future__ import annotations

<<<<<<< HEAD
from langchain_core.messages import AIMessage, HumanMessage
from state.types import AgentState
=======
from langchain_core.messages import HumanMessage

from agent.state.types import AgentState
>>>>>>> feature/monitoring

MAX_MESSAGES = 30


def ingestion(state: AgentState) -> dict:
    txt = (state.get("user_input") or "").strip()
    if not txt:
        return {"phase": "start"}

    prev = state.get("messages", [])
    # behold kun dialog (ikke tool trace)
    prev = [m for m in prev if isinstance(m, (HumanMessage, AIMessage))]

    messages = (prev + [HumanMessage(content=txt)])[-MAX_MESSAGES:]

    # Reset state on new user input to avoid confusion from leftover state. This ensures the agent focuses on the current prompt.
    # Keep message history to maintain conversation context, but clear out any prior diagnosis, plan, etc. that could mislead the agent.
    return {
        "phase": "start",
        "user_input": txt,
        "messages": messages,
        "intent": None,
        "intent_description": None,
        "target": None,
        "attempts": 0,
        "network_db": {},
        "observations": [],
        "diagnosis": None,
        "needs_fix": None,
        "plan": {},
        "changes": [],
        "remediation_step_idx": 0,
        "remediation_done": False,
        "verify": {},
        "remedy_start_cursor": 0,
    }
