from __future__ import annotations

import json

from langchain_core.messages import SystemMessage
from state.types import AgentState

SYSTEM = """You are a network remediation agent.
You receive a plan that you can base the tools you use and execute the necessary actions with these tools.

IMPORTANT: every toolcall is used with arg: "router<number>" and never with hostname. Use full interface names (e.g. "GigabitEthernet0/0/1" not "Gi0/0/1").

Rules:
- Use tools, can me multiple tools that are meant for changes (do not invent commands).
- Make changes to fix the current problem based on the plan.
- You can use multiple steps and multiple tool calls, but keep the number of steps reasonable and accurate to the plan.
- Do not run verification/check actions in this node; this node must only execute remediation changes from the plan.
- Avoid repeating failed change actions with identical arguments from previous_changes unless diagnosis has changed.
- Keep changes minimal and reversible; do not touch unrelated interfaces/protocols.
"""


def remediation_node(state: AgentState, llm) -> dict:
    print("Executing remediation plan...")
    plan = state.get("plan") or {}
    remedy_start_cursor = len(
        state.get("messages") or []
    )  # for controller to know from where to read remedy messages

    ctx = {
        "intent": state.get("intent"),
        "intent_description": state.get("intent_description"),
        "target": state.get("target"),
        "network_db": state.get("network_db") or {},
        "diagnosis": state.get("diagnosis") or {},
        "plan": plan,
        "previous_changes": state.get("changes") or [],
        "attempts": state.get("attempts", 0),
    }

    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    ai = llm.invoke([msg])  # may include tool_calls
    tc = getattr(ai, "tool_calls", None)
    print("tool_calls for remedy:", tc)
    return {"messages": [ai], "phase": "fixed", "remedy_start_cursor": remedy_start_cursor}
