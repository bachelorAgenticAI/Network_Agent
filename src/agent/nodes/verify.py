from __future__ import annotations

import json

from langchain_core.messages import SystemMessage
from state.types import AgentState

SYSTEM = """You are a verification agent.
Run relevant verify-tools based on the diagnosis, plan, and executed changes.

IMPORTANT: every toolcall is used with arg: "router1" and never with hostname

Rules:
- Use tools for verification (do not guess).
- Do not conclude passed/failed here; that is done in assess_verify.
"""


def verify_node(state: AgentState, llm) -> dict:
    print("Running verification tools...")
    ctx = {
        "target": state.get("target"),
        "network_db": state.get("network_db") or {},
        "diagnosis": state.get("diagnosis") or {},
        "plan": state.get("plan") or {},
        "changes_tail": (state.get("changes") or [])[-25:],
    }
    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    ai = llm.invoke([msg])  # may include tool_calls
    return {"messages": [ai], "phase": "verified"}
