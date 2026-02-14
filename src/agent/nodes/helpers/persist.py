# nodes/helpers/persist.py
from __future__ import annotations
from typing import Any
from nodes.helpers.memory_store import MemoryStore

# Find device name from tool call arguments
def infer_device(args: dict[str, Any], fallback: str | None = None) -> str | None:
    return args.get("router_name") or args.get("device") or fallback

# 
def persist_observations(
    observations: list[dict],
    target: str | None = None,
    db: dict | None = None,
    keep_history: bool = True,
    flush_to_disk: bool = True,
) -> dict:
    store = MemoryStore()
    db = db or store.load()

    # Keep track of already persisted tool call IDs to avoid duplicates in the DB
    registry: list[str] = db.get("persisted_tool_call_ids") or []
    seen: set[str] = set(registry)

    for o in observations:
        tcid = o.get("tool_call_id")

        # Skip if already persisted
        if tcid and tcid in seen:
            continue

        tool = o.get("tool_name") or "unknown_tool"
        args = o.get("tool_args") or {}
        data = o.get("content")
        dev = infer_device(args, fallback=target)
        if not dev:
            continue

        db = store.upsert_tool_result_in_db(
            db=db,
            device=dev,
            tool=tool,
            data=data,
            args=args,
            keep_history=keep_history,
        )

        # Mark as persisted
        if tcid:
            seen.add(tcid)
            registry.append(tcid)

    # Save updated registry
    MAX_IDS = 30 # Keep only most recent 30 tool call IDs to prevent unbounded growth
    if len(registry) > MAX_IDS:
        registry = registry[-MAX_IDS:]
        seen = set(registry)

    db["persisted_tool_call_ids"] = registry

    if flush_to_disk:
        store.save(db)

    return db

