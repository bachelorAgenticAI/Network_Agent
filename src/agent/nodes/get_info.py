# should write topoloy to memory and inject it to state.
from __future__ import annotations

import json
from langchain_core.messages import SystemMessage
from state.types import AgentState


SYSTEM = """You are a network agent tasked with gathering facts via tools.
Use available tools to collect information relevant to the intent/target and to build/update network topology.

IMPORTANT: every toolcall is used with arg: "router1" and never with hostname
Requirements:
- You must use tools (tool calls) to retrieve data (do not guess).
- Do not provide a final diagnosis here.
- After tool calls: do not write a long report. Keep it brief.
"""


def get_info_node(state: AgentState, llm) -> dict:
    print("Gathering information with tools...")
    ctx = {
        "intent": state.get("intent"),
        "target": state.get("target"),
        "network_db": state.get("network_db") or {},
        "attempts": state.get("attempts", 0),
    }

    msg = SystemMessage(content=SYSTEM + "\n\nSTATE:\n" + json.dumps(ctx, ensure_ascii=False))
    ai = llm.invoke([msg], tool_choice="required")  # include tool_calls
    tc = getattr(ai, "tool_calls", None)
    print("tool_calls:", tc)
    return {"messages": [ai], "phase": "have_info"}
