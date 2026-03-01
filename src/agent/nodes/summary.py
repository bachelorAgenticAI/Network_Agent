from __future__ import annotations

import json

from langchain_core.messages import SystemMessage
from state.types import AgentState

SYSTEM = """Write a short, precise summary for the user. Include:

What was observed (brief)
Diagnosis (main cause)
If changes were made: what was done
Verification: passed/failed and what remains
Keep it brief, without internal agent meta.
"""


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

    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    ai = llm.invoke([msg])
    return {"messages": [ai]}
