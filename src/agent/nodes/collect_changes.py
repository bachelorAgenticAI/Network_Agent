from __future__ import annotations

from langchain_core.messages import AIMessage, ToolMessage

from agent.state.types import AgentState
from agent.utils.logger import log_node_enter, log_node_exit


def collect_changes_node(state: AgentState) -> dict:
    print("Collecting changes from recent tool calls...")
    log_node_enter(
        "collect_changes",
        {
            "remedy_start_cursor": int(state.get("remedy_start_cursor") or 0),
            "remediation_step_idx": int(state.get("remediation_step_idx") or 0),
            "plan": state.get("plan") or {},
        },
    )

    messages = state.get("messages") or []

    start = int(state.get("remedy_start_cursor") or 0)
    window = messages[start:]
    plan_steps = (state.get("plan") or {}).get("plan_steps") or []
    total_steps = len(plan_steps)
    current_idx = int(state.get("remediation_step_idx") or 0)

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
    next_idx = current_idx + (1 if total_steps > current_idx else 0)
    remediation_done = next_idx >= total_steps
    print(changes)
    out = {
        "changes": changes,
        "remedy_start_cursor": len(messages),
        "remediation_step_idx": min(next_idx, total_steps),
        "remediation_done": remediation_done,
    }
    log_node_exit("collect_changes", out)
    return out
