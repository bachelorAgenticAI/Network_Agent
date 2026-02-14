from __future__ import annotations

import json

from langchain_core.messages import SystemMessage
from state.types import AgentState

SYSTEM = """You are a network remediation agent.
You receive a plan (steps, rollback, verification). Execute the necessary actions via tools.

IMPORTANT: every toolcall is used with arg: "router1" and never with hostname

Rules:
- Use tools for changes (do not invent commands).
- Make the minimal possible change.
- If the plan requires approval and approved=False: DO NOT run tools. Respond briefly and stop.
"""


def remediation_node(state: AgentState, llm) -> dict:
    print("Executing remediation plan...")
    plan = state.get("plan") or {}
    requires_approval = bool(plan.get("requires_approval", True))
    approved = bool(state.get("approved", False))

    if requires_approval and not approved:
        # No tool calls; let controller route to summary
        return {}

    ctx = {
        "intent": state.get("intent"),
        "target": state.get("target"),
        "network_db": state.get("network_db") or {},
        "diagnosis": state.get("diagnosis") or {},
        "plan": plan,
        "previous_changes": state.get("changes") or [],
    }

    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    ai = llm.invoke([msg])  # may include tool_calls
    return {"messages": [ai], "phase": "fixed"}
