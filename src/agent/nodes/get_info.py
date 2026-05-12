"""Run read-only tool calls to gather evidence for diagnosis and topology updates."""

from __future__ import annotations

import json

from langchain_core.messages import SystemMessage

from agent.state.types import AgentState
from agent.utils.logger import log_node_enter, log_node_exit
from mcp_app.utils.routers import ROUTERS

SYSTEM = """You are a network agent tasked with gathering facts via tools.
Instructions:
- For all routers, run the allowed tools with argument router<number> to gather full state.
- Do not use ping or traceroute.
- Do not use any remediation/configuration-changing tools.
- Use full interface names only.
- Use tools to retrieve facts; do not guess.
- If attempts > 0, avoid repeating the exact same tool+args combinations unless required to confirm state drift.
- Use previous_changes to avoid repeating tool calls already made, unless required to confirm state drift.
- Do not provide a final diagnosis.
- After tool calls, keep the response brief.
"""


# This node focuses on gathering information through tool calls to inform the diagnosis.
def get_info_node(state: AgentState, llm) -> dict:
    print("Gathering information with tools...")
    mapping = {router_id: router.name for router_id, router in ROUTERS.items()}
    ctx = {
        "alert_description": state.get("intent_description"),
        "target": state.get("target"),
        "router_mapping": mapping,
        "attempts": state.get("attempts", 0),
        "previous_changes": state.get("changes") or [],
    }
    log_node_enter("get_info", ctx)  # Logger

    # Save cursor so later nodes can isolate just this round of tool messages.
    msg = SystemMessage(content=SYSTEM + "\n\nSTATE:\n" + json.dumps(ctx, ensure_ascii=False))
    info_start_cursor = len(state.get("messages") or [])
    ai = llm.invoke([msg], tool_choice="required")  # include tool_calls
    out = {"messages": [ai], "info_start_cursor": info_start_cursor}
    log_node_exit("get_info", out)  # Logger
    return out
