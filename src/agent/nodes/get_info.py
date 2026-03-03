# should write topoloy to memory and inject it to state.
from __future__ import annotations

import json

from langchain_core.messages import SystemMessage
from state.types import AgentState

SYSTEM = """You are a network agent tasked with gathering facts via tools.
Use available tools to collect information relevant to the intent_description and target and to build/update network topology.

IMPORTANT: every toolcall is used with arg: "router<number>" and never with hostname
If no router number is provided, use previous_network_information to find the relevant router<number> for the target device/devices.
Requirements:
- You can not use tools that makes changes (e.g set_interface)
- You must use tools (tool calls) to retrieve data (do not guess).
- Prefer tools that directly validate the symptom first, then gather context needed to isolate likely root cause.
- Prioritize fresh observations over previous_network_information if they conflict.
- If attempts > 0, avoid repeating the exact same tool+args combinations unless they are required to confirm state drift.
- Do not provide a final diagnosis here.
- After tool calls: do not write a long report. Keep it brief.
"""


def get_info_node(state: AgentState, llm) -> dict:
    print("Gathering information with tools...")
    ctx = {
        "intent_description": state.get("intent_description"),
        "target": state.get("target"),
        "previous_network_information": state.get("network_db") or {},
        "attempts": state.get("attempts", 0),
        "previous_changes": state.get("changes") or [],
    }

    msg = SystemMessage(content=SYSTEM + "\n\nSTATE:\n" + json.dumps(ctx, ensure_ascii=False))
    info_start_cursor = len(state.get("messages") or [])
    ai = llm.invoke([msg], tool_choice="required")  # include tool_calls
    tc = getattr(ai, "tool_calls", None)
    print("tool_calls:", tc)
    return {"messages": [ai], "info_start_cursor": info_start_cursor}
