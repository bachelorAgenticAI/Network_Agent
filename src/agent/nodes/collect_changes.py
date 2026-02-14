# collect_changes.py
from __future__ import annotations

from nodes.helpers.observations import (
    extract_recent_tool_messages,
    extract_tool_call_map,
    tool_messages_to_observations,
)
from nodes.helpers.persist import persist_observations
from state.types import AgentState


def collect_changes_node(state: AgentState) -> dict:
    print("Collecting changes from recent tool calls...")
    tool_msgs = extract_recent_tool_messages(state.get("messages", []))
    tool_call_map = extract_tool_call_map(state.get("messages", []))
    obs = tool_messages_to_observations(tool_msgs, tool_call_map)

    # Persist tool results to long-term DB + update in-memory state cache
    db = persist_observations(
        obs,
        target=state.get("target"),
        db=state.get("network_db"),
        keep_history=True,
        flush_to_disk=True,
    )

    new_changes = [
        {
            "tool_name": o.get("tool_name"),
            "tool_call_id": o.get("tool_call_id"),
            "tool_args": o.get("tool_args"),
            "result": o.get("content"),
        }
        for o in obs
    ]

    changes = (state.get("changes") or []) + new_changes
    return {
        "changes": changes,
        "network_db": db,  # <-- expose current state to the rest of the graph
    }
