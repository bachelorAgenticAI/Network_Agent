from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


# Convert content to JSON
def try_json(x: Any) -> Any:
    # Already decoded
    if isinstance(x, dict):
        return x
    if isinstance(x, list):
        # LangChain content blocks: [{"type":"text","text":"{...}","id":"..."}]
        if len(x) == 1 and isinstance(x[0], dict) and isinstance(x[0].get("text"), str):
            s = x[0]["text"].strip()
            try:
                return json.loads(s)
            except Exception:
                return {"text": s}
        return x

    if isinstance(x, str):
        s = x.strip()
        if not s:
            return {"text": ""}
        try:
            return json.loads(s)
        except Exception:
            return {"text": x}

    return {"value": repr(x)}


# Extract tool call information from recent messages limit set to x
def extract_tool_call_map(messages: list[BaseMessage], limit: int = 10) -> dict[str, dict]:
    m: dict[str, dict] = {}
    for msg in reversed(messages[-limit:]):
        if isinstance(msg, AIMessage):
            for tc in getattr(msg, "tool_calls", None) or []:
                tc_id = tc.get("id")
                if tc_id:
                    m[tc_id] = {"name": tc.get("name"), "args": tc.get("args") or {}}
    return m


# Extract recent tool messages from the message history, limit set to x
def extract_recent_tool_messages(messages: list[BaseMessage], limit: int = 10) -> list[ToolMessage]:
    tool_msgs: list[ToolMessage] = []
    for m in reversed(messages[-limit:]):
        if isinstance(m, ToolMessage):
            tool_msgs.append(m)
    return list(reversed(tool_msgs))


# Convert tool messages to observations, using the tool call map for additional context about the tool calls.
def tool_messages_to_observations(
    tool_msgs: list[ToolMessage], tool_call_map: dict[str, dict] | None = None
) -> list[dict]:
    tool_call_map = tool_call_map or {}
    out: list[dict] = []
    for tm in tool_msgs:
        tc = tool_call_map.get(getattr(tm, "tool_call_id", None), {})
        out.append(
            {
                "tool_name": tc.get("name") or getattr(tm, "name", None) or "unknown_tool",
                "tool_call_id": getattr(tm, "tool_call_id", None),
                "tool_args": tc.get("args") or {},
                "content": try_json(tm.content),
            }
        )
    return out
