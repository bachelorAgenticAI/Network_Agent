"""Generate the final user-facing summary for one run."""

from __future__ import annotations

import json

from langchain_core.messages import SystemMessage

from agent.state.types import AgentState
from agent.utils.logger import log_node_enter, log_node_exit

SYSTEM = """Write a short, precise summary for the user. Include:

What was observed (brief)
Diagnosis (main cause)
If changes were made: what was done
Verification: passed/failed and what remains
Keep it brief, without internal agent meta.
"""

# This node generates a final summary message for the user.
def summary_node(state: AgentState, llm) -> dict:
    print("Generating summary for user...")
    ctx = {
        "intent": state.get("intent"),
        "intent_description": state.get("intent_description"),
        "target": state.get("target"),
        "network_db": state.get("network_db") or {},
        "diagnosis": state.get("diagnosis") or {},
        "needs_fix": state.get("needs_fix"),
        "plan": state.get("plan") or {},
        "changes": state.get("changes") or [],
        "verify": state.get("verify") or {},
        "attempts": state.get("attempts", 0),
    }
    log_node_enter("summary", ctx) # Logger

    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    ai = llm.invoke([msg])
    out = {"messages": [ai]}
    log_node_exit("summary", out) # Logger
    return out
