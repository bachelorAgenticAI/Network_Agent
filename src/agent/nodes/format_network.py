# nodes/format_network.py
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from nodes.helpers.memory_store import MemoryStore, utc_now
from state.schemas import FormatResult
from state.types import AgentState

SYSTEM = """
Return ONLY JSON that matches FormatResult.

Input:
- previous_network_db (may be empty)
- recent_tool_data: the latest ~30 tool-related messages (AI tool_calls + Tool results)

Task:
- Compare previous_network_db with new information in recent_tool_data.
- Update/fix the topology accordingly, or keep it the same if still accurate.
- Add any facts including description of devices, links, configs, issues, timestamps, etc.
- Produce a NEW network_db that reflects the most accurate current state.
- Do not guess: unknown ⇒ empty fields/lists.
- network_db.meta must include ts (ISO8601 Z) and target.
"""


def _jsonable(x: Any, max_chars: int = 20000) -> str:
    try:
        s = json.dumps(x, ensure_ascii=False, default=str)
    except Exception:
        s = str(x)
    return s if len(s) <= max_chars else s[:max_chars] + "...(truncated)"


def _toolish_raw(m: BaseMessage, max_content: int = 4000) -> dict[str, Any]:
    content = getattr(m, "content", None)
    if isinstance(content, str) and len(content) > max_content:
        content = content[:max_content] + "...(truncated)"

    d: dict[str, Any] = {"type": m.__class__.__name__, "content": content}

    if isinstance(m, AIMessage):
        d["tool_calls"] = getattr(m, "tool_calls", None) or []
    elif isinstance(m, ToolMessage):
        d["tool_call_id"] = getattr(m, "tool_call_id", None)
        d["name"] = getattr(m, "name", None)

    return d


def _is_tool_related(m: BaseMessage) -> bool:
    if isinstance(m, ToolMessage):
        return True
    if isinstance(m, AIMessage) and (getattr(m, "tool_calls", None) or []):
        return True
    return False


def format_network_node(state: AgentState, llm_info) -> dict:
    print("Formatting network info...")
    target = state.get("target") or "network"
    messages = state.get("messages") or []

    recent = [m for m in messages if _is_tool_related(m)][-30:]
    payload = {
        "target": target,
        "intent": state.get("intent"),
        "previous_network_db": state.get("network_db") or {},
        "recent_tool_data": [_toolish_raw(m) for m in recent],
    }

    formatter = llm_info.with_structured_output(FormatResult)
    result: FormatResult = formatter.invoke(
        [SystemMessage(content=SYSTEM), HumanMessage(content=_jsonable(payload))]
    )

    network_db = result.network_db.model_dump(mode="json")

    meta = network_db.setdefault("meta", {})
    meta.setdefault("ts", utc_now())
    meta.setdefault("target", target)

    try:
        store = MemoryStore()
        db = store.load()
        db["network_db"] = network_db
        store.save(db)
        warnings = []
    except Exception as e:
        warnings = [f"persist_network_db_failed: {e!r}"]

    out = {"network_db": network_db, "phase": "have_info"}
    if warnings:
        out["warnings"] = warnings
    return out
