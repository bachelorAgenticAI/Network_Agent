# nodes/format_network.py
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from nodes.helpers.memory_store import MemoryStore, utc_now
from state.schemas import FormatResult
from state.types import AgentState

SYSTEM = """
You reconstruct network_db by MERGING updates from recent_tool_data into previous_network_db.

Return ONLY JSON matching FormatResult.

Input:
- previous_network_db (may be empty)
- recent_tool_data (~30 latest tool_calls + tool results)

Key rule — incremental updates:
- recent_tool_data is PARTIAL.
- Never delete or overwrite entities just because they are missing from this round.
- Absence in recent_tool_data ≠ removal or change.
- Example: if Route 1 is fetched but Route 2 is not, Route 2 must remain unchanged.

Update logic:
- Modify ONLY entities explicitly referenced in tool results.
- Merge new facts into existing entities.
- Keep all other entities unchanged.

Freshness:
- Updated facts:
  - update last_seen_ts
  - stale = false
- Non-updated facts:
  - keep existing values
  - mark stale = true
  - DO NOT change last_seen_ts

Conflicts:
- Prefer newer tool results.
- Store replaced values in history[] with timestamp + source.

Null handling:
- Set values to null ONLY if a tool explicitly reports unknown/unavailable.

Meta:
- network_db.meta.ts = current reconstruction time (ISO8601 Z)
- Preserve or propagate meta.target.

Goal:
Produce a NEW network_db reflecting the best known state without losing previously known information.
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
