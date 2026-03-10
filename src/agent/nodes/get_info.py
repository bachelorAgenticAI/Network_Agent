"""Run read-only tool calls to gather evidence for diagnosis and topology updates."""

from __future__ import annotations

import json

from langchain_core.messages import SystemMessage

from agent.state.types import AgentState
from agent.utils.logger import log_node_enter, log_node_exit
from mcp_app.tools.router_names import list_routers

SYSTEM = """You are a network agent tasked with gathering facts via tools.
Use available tools to collect information relevant to the alert_description and target and to build/update network topology.

IMPORTANT: every toolcall is used with arg: "router<number>" and never with hostname. Use full interface names (e.g. "GigabitEthernet0/0/1" not "Gi0/0/1").
Router inventory is already preloaded in available_router_map and available_router_args. Use those values directly when calling tools.
If no router number is provided, use available_router_map and previous_network_information to find the relevant router<number> for the target device/devices.
Requirements:
- Use all available read-only information tools that are relevant to the current request, except list_routers.
- Do not call list_routers unless the preloaded router inventory is missing or clearly stale.
- For baseline collection, gather configuration, interface, ARP, OSPF, and DHCP information across the available routers.
- Secondary to that, use tools that directly validate the alert_description
- You can not use tools that makes changes (e.g set_interface)
- You must use tools (tool calls) to retrieve data (do not guess).
- If attempts > 0, avoid repeating the exact same tool+args combinations unless they are required to confirm state drift.
- Use previous_changes to avoid repeating the same tool calls that have already been made, unless they are required to confirm state drift.
- Do not provide a final diagnosis here.
- After tool calls: do not write a long report. Keep it brief.
"""


# This node focuses on gathering information through tool calls to inform the diagnosis.
def get_info_node(state: AgentState, llm) -> dict:
    print("Gathering information with tools...")
    routers = list_routers()
    router_map = routers if isinstance(routers, dict) else {}
    available_router_args = sorted(router_map.keys())
    ctx = {
        "alert_description": state.get("intent_description"),
        "target": state.get("target"),
        "attempts": state.get("attempts", 0),
        "previous_changes": state.get("changes") or [],
        "available_router_map": router_map,
        "available_router_args": available_router_args,
    }
    log_node_enter("get_info", ctx)  # Logger

    # Save cursor so later nodes can isolate just this round of tool messages.
    msg = SystemMessage(content=SYSTEM + "\n\nSTATE:\n" + json.dumps(ctx, ensure_ascii=False))
    info_start_cursor = len(state.get("messages") or [])
    ai = llm.invoke([msg], tool_choice="required")  # include tool_calls
    out = {
        "messages": [ai],
        "info_start_cursor": info_start_cursor,
        "router_map": router_map,
        "available_router_args": available_router_args,
    }
    log_node_exit("get_info", out)  # Logger
    return out
