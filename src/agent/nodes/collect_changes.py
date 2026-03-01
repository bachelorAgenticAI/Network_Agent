from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage
from state.types import AgentState


def collect_changes_node(state: AgentState) -> dict:
    print("Collecting changes from recent tool calls...")

    messages = state.get("messages") or []

    start = int(state.get("remedy_start_cursor") or 0)
    window = messages[start:]

    calls_by_id = {}
    for m in window:
        if isinstance(m, AIMessage):
            for c in getattr(m, "tool_calls", None) or []:
                tc_id = c.get("id") or c.get("tool_call_id")
                if not tc_id:
                    continue
                calls_by_id[tc_id] = {
                    "tool": c.get("name") or c.get("tool"),
                    "args": c.get("args") or {},
                }

    new_changes = []
    for m in window:
        if isinstance(m, ToolMessage):
            tc_id = getattr(m, "tool_call_id", None)
            meta = calls_by_id.get(tc_id, {})

            new_changes.append(
                {
                    "tool_call_id": tc_id,
                    "tool": meta.get("tool") or getattr(m, "name", None),
                    "args": meta.get("args") or {},
                    "result": m.content,
                }
            )

    changes = (state.get("changes") or []) + new_changes
    return {
        "changes": changes,
        "remedy_start_cursor": len(messages),
    }
