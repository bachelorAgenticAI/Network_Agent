"""Thread-safe JSONL logger for node inputs/outputs used in debugging and metrics extraction."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

_WRITE_LOCK = Lock()
_LOG_DIR = Path(__file__).resolve().parent.parent / "logger"
_NODE_IO_LOG_PATH = _LOG_DIR / "node_io_log.jsonl"


# Log timestamp format for node events.
def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# Best-effort conversion so arbitrary model objects can be written as JSON.
def _to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_to_jsonable(v) for v in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _to_jsonable(model_dump())
        except Exception:
            return str(value)

    to_dict = getattr(value, "dict", None)
    if callable(to_dict):
        try:
            return _to_jsonable(to_dict())
        except Exception:
            return str(value)

    return str(value)


# One JSON line per node event (enter/exit).
def _write_node_entry(node: str, direction: str, data: Any) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": _now_iso(),
        "node": node,
        "direction": direction,
        "data": _to_jsonable(data),
    }

    line = json.dumps(entry, ensure_ascii=False)
    with _WRITE_LOCK:
        with _NODE_IO_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


# Persist node input context.
def log_node_enter(node: str, ctx: Any) -> None:
    _write_node_entry(node=node, direction="in", data=ctx)


# Persist node output patch/result.
def log_node_exit(node: str, out: Any) -> None:
    _write_node_entry(node=node, direction="out", data=out)
