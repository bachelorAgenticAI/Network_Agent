from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from agent.state.types import AgentState
from agent.utils.logger import log_node_enter, log_node_exit

MAX_MESSAGES = 30


def ingestion(state: AgentState) -> dict:
    log_node_enter("ingestion", {"user_input": state.get("user_input"), "messages": state.get("messages", [])})
    txt = (state.get("user_input") or "").strip()
    if not txt:
        out = {"phase": "start"}
        return out

    prev = state.get("messages", [])
    # behold kun dialog (ikke tool trace)
    prev = [m for m in prev if isinstance(m, (HumanMessage, AIMessage))]

    messages = (prev + [HumanMessage(content=txt)])[-MAX_MESSAGES:]

    # Reset state on new user input to avoid confusion from leftover state. This ensures the agent focuses on the current prompt.
    # Keep message history to maintain conversation context, but clear out any prior diagnosis, plan, etc. that could mislead the agent.
    out = {
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
    log_node_exit("ingestion", out)   
    return out
