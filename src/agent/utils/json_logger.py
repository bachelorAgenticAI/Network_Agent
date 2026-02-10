# json_logger.py

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from langchain_core.messages import BaseMessage

LOG_FILE = Path("agent_trace.jsonl")


def _serialize(obj: Any):
    """Fallback serializer for ikke-JSON objekter."""
    try:
        return str(obj)
    except Exception:
        return "<non-serializable>"


def dump_messages(messages: list[BaseMessage]) -> list[dict]:
    """Gjør LangChain messages JSON-serialiserbare."""
    out = []

    for m in messages:
        out.append({
            "type": m.__class__.__name__,
            "content": getattr(m, "content", None),
            "tool_calls": getattr(m, "tool_calls", None),
            "additional_kwargs": getattr(m, "additional_kwargs", None),
        })

    return out


def log_event(node: str, event: str, payload: dict):
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "node": node,
        "event": event,
        "payload": payload,
    }

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=_serialize, indent=2) + "\n")
