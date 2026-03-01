# utils/logger.py
from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    # optional, only for nicer schema introspection
    from pydantic import BaseModel
except Exception:  # pragma: no cover
    BaseModel = object  # type: ignore


# -------------------------
# Config
# -------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_ROOT / "logger"
LOG_FILE = LOG_DIR / "agent_trace.jsonl"  # JSON Lines (append-only)

# Keep logs short by default
MAX_STR = 300
MAX_LIST = 25
MAX_DICT_ITEMS = 50

# -------------------------
# Trace context
# -------------------------


@dataclass
class TraceContext:
    trace_id: str
    span_id: str | None = None
    parent_span_id: str | None = None


def _new_id(prefix: str = "") -> str:
    return prefix + uuid.uuid4().hex[:16]


def ensure_trace(state: dict) -> TraceContext:
    """
    Keeps a stable trace_id across the run (stored in state["trace_id"]).
    Optionally store a current span in state["span_id"] if you want.
    """
    if not state.get("trace_id"):
        state["trace_id"] = _new_id("tr_")
    # node span is created per log_node_enter
    return TraceContext(trace_id=state["trace_id"], span_id=state.get("span_id"))


# -------------------------
# Time + IO
# -------------------------


def _ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f UTC")


def _append_jsonl(obj: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# -------------------------
# clipping
# -------------------------


def _clip_str(s: str, n: int = MAX_STR) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _safe(x: Any, *, _depth: int = 0) -> Any:
    """
    Short, JSON-safe representation of common data types, with clipping for long strings and large collections.
    Intentionally lossy: focuses on signal, avoids log blowups.
    """
    if x is None or isinstance(x, (bool, int, float)):
        return x

    if isinstance(x, str):
        return _clip_str(x)

    if isinstance(x, dict):
        out: dict[str, Any] = {}
        # deterministic order for stability
        for i, (k, v) in enumerate(sorted(x.items(), key=lambda kv: str(kv[0]))):
            if i >= MAX_DICT_ITEMS:
                out["…"] = f"+{max(0, len(x) - MAX_DICT_ITEMS)} more keys"
                break
            ks = str(k)
            out[ks] = _safe(v, _depth=_depth + 1)
        return out

    if isinstance(x, (list, tuple)):
        items = list(x)
        trimmed = items[:MAX_LIST]
        out = [_safe(v, _depth=_depth + 1) for v in trimmed]
        if len(items) > MAX_LIST:
            out.append(f"… +{len(items) - MAX_LIST} more")
        return out

    # pydantic models
    for attr in ("model_dump", "dict"):
        fn = getattr(x, attr, None)
        if callable(fn):
            try:
                return _safe(fn(), _depth=_depth + 1)
            except Exception:
                pass

    return _clip_str(repr(x))


def _digest(payload: Any) -> str:
    """
    Hash on safe-serialized JSON for consistent digests across objects.
    """
    try:
        b = json.dumps(_safe(payload), ensure_ascii=False, sort_keys=True).encode("utf-8")
    except Exception:
        b = str(payload).encode("utf-8", errors="ignore")
    return hashlib.sha256(b).hexdigest()[:16]


# -------------------------
# Schema extraction (short but meaningful)
# -------------------------


def _schema_name(schema: Any) -> str | None:
    if schema is None:
        return None
    cls = schema if isinstance(schema, type) else schema.__class__
    return getattr(cls, "__name__", str(cls))


def _extract_diagnosis(d: Any) -> dict:
    # Accept dict or pydantic model
    dd = _safe(d)
    root = dd.get("root_causes") or []
    root_compact = []
    for rc in root[:10]:
        # rc is already safe dict-like
        if isinstance(rc, dict):
            root_compact.append(
                {
                    "cause": rc.get("cause"),
                    "confidence": rc.get("confidence"),
                    "evidence": (rc.get("evidence") or [])[:5],
                }
            )
    return {
        "root_causes": root_compact,
        "risks": (dd.get("risks") or [])[:10],
        "missing_info": (dd.get("missing_info") or [])[:10],
    }


def _extract_plan(p: Any) -> dict:
    pp = _safe(p)
    return {
        "plan_steps": (pp.get("plan_steps") or [])[:12],
        "verification": (pp.get("verification") or [])[:12],
        "rollback": (pp.get("rollback") or [])[:12],
    }


def _extract_verify(v: Any) -> dict:
    vv = _safe(v)
    return {
        "passed": vv.get("passed"),
        "evidence": (vv.get("evidence") or [])[:10],
        "remaining_issues": (vv.get("remaining_issues") or [])[:10],
        "missing_info": (vv.get("missing_info") or [])[:10],
    }


def _extract_intent(i: Any) -> dict:
    ii = _safe(i)
    out = {
        "intent": ii.get("intent"),
        "intent_description": ii.get("intent_description"),
        "target": ii.get("target"),
        "needs_fix": ii.get("needs_fix"),
    }
    plan = ii.get("plan")
    if plan:
        out["plan"] = _extract_plan(plan)
    return out


def _extract_topology(t: Any) -> dict:
    tt = _safe(t)
    devices = tt.get("devices") or []
    links = tt.get("links") or []
    return {
        "devices_n": len(devices) if isinstance(devices, list) else None,
        "links_n": len(links) if isinstance(links, list) else None,
        "recent_changes": (tt.get("recent_changes") or [])[:10],
    }


# Registry of schema extractors by schema name
_EXTRACTORS: dict[str, Callable[[Any], dict]] = {
    "Diagnosis": _extract_diagnosis,
    "Plan": _extract_plan,
    "VerifyResult": _extract_verify,
    "IntentOut": _extract_intent,
    "TopologyInfo": _extract_topology,
}


def _schema_compact(schema: Any, obj: Any) -> dict:
    name = _schema_name(schema)
    if not name:
        return {"name": None, "summary": None}

    extractor = _EXTRACTORS.get(name)
    if extractor and obj is not None:
        try:
            return {"name": name, "summary": extractor(obj)}
        except Exception:
            return {"name": name, "summary": None}
    return {"name": name, "summary": None}


def _schema_fields(schema: Any) -> list[str] | None:
    if schema is None:
        return None
    try:
        cls = schema if isinstance(schema, type) else schema.__class__
        if isinstance(cls, type) and issubclass(cls, BaseModel):  # type: ignore[arg-type]
            # pydantic v1: __fields__, v2: model_fields
            f = getattr(cls, "__fields__", None) or getattr(cls, "model_fields", None)
            if isinstance(f, dict):
                return list(f.keys())
    except Exception:
        pass
    return None


# -------------------------
# State summary (short and stable)
# -------------------------


def _state_summary(state: dict) -> dict:
    s = state or {}
    msgs = s.get("messages") or []
    obs = s.get("observations") or []
    chg = s.get("changes") or []
    d = s.get("diagnosis") or {}

    has_diagnosis = bool(
        (d.get("root_causes") or [])
        or (d.get("risks") or [])
        or (d.get("missing_info") or [])
    )   

    def _msg_tail():
        tail = []
        for m in msgs[-5:]:
            content = getattr(m, "content", None)
            tail.append(
                {
                    "type": m.__class__.__name__,
                    "content_head": _safe(content) if content is not None else None,
                    "tool_call_id": getattr(m, "tool_call_id", None),
                }
            )
        return tail

    db = s.get("network_db") or {}
    devices = (db.get("devices") or {}) if isinstance(db, dict) else {}
    return {
        "intent": s.get("intent"),
        "intent_description": s.get("intent_description"),
        "target": s.get("target"),
        "phase": s.get("phase"),
        "attempts": s.get("attempts"),
        "needs_fix": s.get("needs_fix"),
        "counts": {
            "messages": len(msgs),
            "observations": len(obs),
            "changes": len(chg),
        },
        "messages_tail": _msg_tail(),
        "devices_n": len(devices) if isinstance(devices, dict) else None,
        "has": {
            "diagnosis": has_diagnosis,
            "plan": bool(s.get("plan")),
            "verify": bool(s.get("verify")),
        },
    }


# -------------------------
# Core event writers
# -------------------------


def _base_event(*, node: str, event: str, state: dict | None = None) -> dict:
    st = state or {}
    tr = TraceContext(trace_id=st.get("trace_id") or _new_id("tr_"))
    return {
        "ts": _ts(),
        "pid": os.getpid(),
        "trace_id": tr.trace_id,
        "node": node,
        "event": event,
    }


def log_event(node: str, event: str, payload: dict, *, state: dict | None = None) -> None:
    evt = _base_event(node=node, event=event, state=state)
    evt["payload"] = _safe(payload)
    _append_jsonl(evt)


def log_node_enter(node: str, state: dict) -> None:
    # create a span per node entry
    ensure_trace(state)
    span_id = _new_id("sp_")
    state["span_id"] = span_id
    log_event(
        node,
        "enter",
        {
            "span_id": span_id,
            "state": _state_summary(state),
        },
        state=state,
    )


def log_node_exit(node: str, patch: dict, *, state: dict | None = None) -> None:
    # If state is provided, it links exit to the same trace/span
    payload: dict[str, Any] = {
        "span_id": (state or {}).get("span_id"),
        "patch_keys": sorted(list((patch or {}).keys())),
        "patch_digest": _digest(patch),
    }

    # add compact summaries for well-known artifacts (if present in patch)
    if patch:
        if "diagnosis" in patch:
            payload["diagnosis"] = _extract_diagnosis(patch.get("diagnosis"))
        if "plan" in patch:
            payload["plan"] = _extract_plan(patch.get("plan"))
        if "verify" in patch:
            payload["verify"] = _extract_verify(patch.get("verify"))
        if any(k in patch for k in ("intent", "target", "needs_fix")):
            payload["intent_update"] = {
                k: patch.get(k) for k in ("intent", "target", "needs_fix") if k in patch
            }

    log_event(node, "exit", payload, state=state)


def log_llm_invoke(
    node: str,
    *,
    messages: list[Any],
    schema: Any | None = None,
    extra: dict | None = None,
    state: dict | None = None,
) -> None:
    msg_meta = []
    for m in messages:
        content = getattr(m, "content", "") or ""
        msg_meta.append(
            {
                "type": m.__class__.__name__,
                "content_len": len(content),
                "content_head": _safe(content) if content else None,
            }
        )

    log_event(
        node,
        "llm_invoke",
        {
            "span_id": (state or {}).get("span_id"),
            "schema": {
                "name": _schema_name(schema),
                "fields": _schema_fields(schema),
            },
            "messages": msg_meta,
            "extra": _safe(extra or {}),
        },
        state=state,
    )


def log_schema_output(
    node: str,
    *,
    schema: Any | None,
    output: Any,
    state: dict | None = None,
    label: str = "llm_output",
) -> None:
    """
    Optional: call this right after LLM structured output for short, meaningful summaries.
    """
    log_event(
        node,
        label,
        {
            "span_id": (state or {}).get("span_id"),
            "schema": _schema_compact(schema, output),
            "output_digest": _digest(output),
        },
        state=state,
    )


def log_edge_transfer(
    *,
    from_node: str,
    to_node: str,
    schema: Any | None,
    payload: Any,
    state: dict | None = None,
    label: str = "edge",
) -> None:
    """
    Optional: use when you explicitly want to log "what was sent to next node" in compact form.
    """
    log_event(
        from_node,
        label,
        {
            "span_id": (state or {}).get("span_id"),
            "to": to_node,
            "schema": _schema_compact(schema, payload),
            "payload_digest": _digest(payload),
            "payload_keys": sorted(list(payload.keys())) if isinstance(payload, dict) else None,
        },
        state=state,
    )
