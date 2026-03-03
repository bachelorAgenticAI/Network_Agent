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
- recent_tool_data (~latest tool calls/results in this info round)

Key rule — incremental updates:
- recent_tool_data is PARTIAL.
- Never delete or overwrite entities just because they are missing from this round.
- Absence in recent_tool_data ≠ removal or change.

Update logic:
- Modify ONLY entities explicitly referenced in tool results.
- Merge new facts into existing entities.
- Keep all other entities unchanged.

Extraction quality:
- Prefer concrete fields from parsed tool outputs over generic "fetched successfully" claims.
- Use tool args and tool names to identify device/interface/protocol scope.
- Avoid duplicate facts and duplicate recent_changes entries.
- Extraxted facts should be as specific and structured as possible, but if needed, can include a raw/truncated version of the tool output for completeness.

Freshness:
- Updated facts: update last_seen_ts and stale=false.
- Non-updated facts: keep value, mark stale=true, keep last_seen_ts unchanged.

Meta:
- network_db.meta.ts = current reconstruction time (ISO8601 Z)
- Preserve or propagate meta.target.
"""


def _jsonable(x: Any, max_chars: int = 14000) -> str:
    try:
        s = json.dumps(x, ensure_ascii=False, default=str)
    except Exception:
        s = str(x)
    return s if len(s) <= max_chars else s[:max_chars] + "...(truncated)"


def _is_tool_related(m: BaseMessage) -> bool:
    if isinstance(m, ToolMessage):
        return True
    if isinstance(m, AIMessage) and (getattr(m, "tool_calls", None) or []):
        return True
    return False


def _safe_parse_json(content: Any) -> Any:
    if not isinstance(content, str):
        return content
    try:
        return json.loads(content)
    except Exception:
        return content


def _shrink_value(value: Any, max_chars: int = 1800) -> Any:
    if isinstance(value, (dict, list)):
        raw = json.dumps(value, ensure_ascii=False, default=str)
        if len(raw) <= max_chars:
            return value
        return raw[:max_chars] + "...(truncated)"
    if isinstance(value, str) and len(value) > max_chars:
        return value[:max_chars] + "...(truncated)"
    return value


def _build_recent_tool_data(window: list[BaseMessage], max_items: int = 20) -> list[dict[str, Any]]:
    calls_by_id: dict[str, dict[str, Any]] = {}
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

    data: list[dict[str, Any]] = []
    for m in window:
        if not isinstance(m, ToolMessage):
            continue

        tc_id = getattr(m, "tool_call_id", None)
        call_meta = calls_by_id.get(tc_id, {})
        parsed = _safe_parse_json(getattr(m, "content", None))

        entry = {
            "type": "ToolMessage",
            "tool_call_id": tc_id,
            "name": getattr(m, "name", None) or call_meta.get("tool"),
            "args": call_meta.get("args") or {},
            "parsed": _shrink_value(parsed, max_chars=1800),
        }
        data.append(entry)

    return data[-max_items:]


def _persist_network_db(network_db: dict[str, Any]) -> list[str]:
    try:
        store = MemoryStore()
        db = store.load()
        db["network_db"] = network_db
        store.save(db)
        return []
    except Exception as e:
        return [f"persist_network_db_failed: {e!r}"]


def _fast_path_no_new_tool_data(state: AgentState, target: str) -> dict:
    existing = (state.get("network_db") or {}).copy()
    meta = existing.setdefault("meta", {})
    meta["ts"] = utc_now()
    meta.setdefault("target", target)

    warnings = _persist_network_db(existing)
    out = {"network_db": existing, "phase": "have_info"}
    if warnings:
        out["warnings"] = warnings
    return out


def format_network_node(state: AgentState, llm_format) -> dict:
    print("Formatting network info...")
    target = state.get("target") or "network"
    messages = state.get("messages") or []

    info_start = int(state.get("info_start_cursor") or 0)
    recent_window = [m for m in messages[info_start:] if _is_tool_related(m)]

    recent_tool_data = _build_recent_tool_data(recent_window, max_items=20)
    if not recent_tool_data:
        return _fast_path_no_new_tool_data(state, target)

    payload = {
        "target": target,
        "intent": state.get("intent"),
        "previous_network_db": state.get("network_db") or {},
        "recent_tool_data": recent_tool_data,
    }

    formatter = llm_format.with_structured_output(FormatResult)
    result: FormatResult = formatter.invoke(
        [SystemMessage(content=SYSTEM), HumanMessage(content=_jsonable(payload))]
    )

    network_db = result.network_db.model_dump(mode="json")
    meta = network_db.setdefault("meta", {})
    meta["ts"] = utc_now()
    meta.setdefault("target", target)

    warnings = _persist_network_db(network_db)

    out = {"network_db": network_db, "phase": "have_info"}
    if warnings:
        out["warnings"] = warnings
    return out