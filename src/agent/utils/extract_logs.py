"""Convert raw node_io logs into a compact run summary for analytics and reporting."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).resolve().parent.parent / "logger"
NODE_IO_LOG_PATH = LOG_DIR / "node_io_log.jsonl"
EXTRACTED_LOGS_PATH = LOG_DIR / "extracted_logs.json"

# Log timestamps may use Z; normalize to ISO format understood by datetime.
def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

# Read line-delimited node logs into memory.
def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing log file: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows

# Find first/last event for a given node+direction pair.
def _find(
    entries: list[dict[str, Any]], node: str, direction: str, *, first: bool
) -> dict[str, Any] | None:
    matches = [e for e in entries if e.get("node") == node and e.get("direction") == direction]
    if not matches:
        return None
    return matches[0] if first else matches[-1]

# Normalize a string into snake_case. Non-alphanumeric characters are replaced with underscores.
def _snake_case(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")

# Normalize issue type based on cause text, with some custom rules for common network issues.
def _normalize_issue_type(cause_text: str) -> str:
    c = cause_text.lower()
    if "admin" in c and ("shutdown" in c or "shut down" in c):
        return "admin_shutdown"
    return _snake_case(cause_text or "unknown")

# Tool output may be raw string or embedded JSON chunks; normalize to status text.
def _extract_change_result(raw_result: Any) -> str:
    if isinstance(raw_result, list):
        for item in raw_result:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str):
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                continue
            status = obj.get("status")
            if isinstance(status, str) and status:
                return status
    if isinstance(raw_result, str) and raw_result:
        return raw_result
    return "unknown"

# Pull a few normalized metrics from free-text verification evidence.
def _extract_verify_evidence_obj(verify: dict[str, Any]) -> dict[str, Any]:
    evidence = verify.get("evidence", [])
    if not isinstance(evidence, list):
        evidence = []

    out: dict[str, Any] = {}

    for item in evidence:
        if not isinstance(item, str):
            continue

        m_admin = re.search(r'"admin_state"\s*:\s*"([^"]+)"', item)
        if m_admin:
            out["interface_admin_state"] = m_admin.group(1)

        m_oper = re.search(r'"oper_state"\s*:\s*"([^"]+)"', item)
        if m_oper:
            out["interface_oper_state"] = m_oper.group(1)

        if "success rate is 100 percent" in item.lower() or "(5/5)" in item:
            out["ping_10_0_0_2_success"] = True

        if 'no "shutdown" line' in item.lower() or "shutdown line removed" in item.lower():
            out["shutdown_removed"] = True

    remaining = verify.get("remaining_issues", [])
    if isinstance(remaining, list):
        for issue in remaining:
            if not isinstance(issue, str):
                continue
            m_nbr = re.search(r'neighbor_state="?([a-zA-Z0-9\-_]+)"?', issue)
            if m_nbr:
                out["ospf_neighbor_state"] = m_nbr.group(1)

    return out

# Aggregate token usage across all logged model messages.
def _sum_tokens(entries: list[dict[str, Any]]) -> dict[str, int]:
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    for entry in entries:
        messages = entry.get("data", {}).get("messages", [])
        if not isinstance(messages, list):
            continue
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            usage = (msg.get("response_metadata") or {}).get("token_usage") or {}
            prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
            completion_tokens += int(usage.get("completion_tokens", 0) or 0)
            total_tokens += int(usage.get("total_tokens", 0) or 0)

    return {
        "total_prompt_tokens": prompt_tokens,
        "total_completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }

# Count tool calls inside one node output payload.
def _tool_calls_count(entry: dict[str, Any] | None) -> int:
    if not entry:
        return 0
    messages = entry.get("data", {}).get("messages", [])
    if not isinstance(messages, list):
        return 0

    total = 0
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        tool_calls = msg.get("tool_calls", [])
        if isinstance(tool_calls, list):
            total += len(tool_calls)
    return total

# Number of times each node ran in this incident (based on "in" events).
def _node_cycles(entries: list[dict[str, Any]]) -> dict[str, int]:
    cycles: dict[str, int] = {}
    for entry in entries:
        if entry.get("direction") != "in":
            continue
        node = entry.get("node")
        if not isinstance(node, str) or not node:
            continue
        cycles[node] = cycles.get(node, 0) + 1
    return cycles

# Build one structured run document from raw node enter/exit events.
def build_extracted(entries: list[dict[str, Any]]) -> dict[str, Any]:
    if not entries:
        raise ValueError("No entries in node_io_log.jsonl")

    monitor_in = _find(entries, "monitor_loop", "in", first=True) or {}
    monitor_out = _find(entries, "monitor_loop", "out", first=False) or {}

    diagnose_out = _find(entries, "diagnose", "out", first=False) or {}
    intent_out_last = _find(entries, "intent", "out", first=False) or {}
    collect_changes_out = _find(entries, "collect_changes", "out", first=False) or {}
    assess_verify_out = _find(entries, "assess_verify", "out", first=False) or {}

    monitor_in_data = monitor_in.get("data", {})
    alerts = monitor_in_data.get("alerts", [])
    input_alert = alerts[0] if isinstance(alerts, list) and alerts else {}

    diagnosis = diagnose_out.get("data", {}).get("diagnosis", {})
    if not isinstance(diagnosis, dict):
        diagnosis = {}
    root_causes = diagnosis.get("root_causes", [])
    if not isinstance(root_causes, list):
        root_causes = []

    primary_cause = root_causes[0] if root_causes else {}
    primary_type = str(primary_cause.get("type", "")).strip()
    issue_type = _normalize_issue_type(primary_type or str(primary_cause.get("cause", "unknown")))

    intent_out_data = intent_out_last.get("data", {})
    plan = intent_out_data.get("plan", {}) if isinstance(intent_out_data, dict) else {}
    plan_steps = plan.get("plan_steps", []) if isinstance(plan, dict) else []

    changes_raw = collect_changes_out.get("data", {}).get("changes", [])
    changes_out: list[dict[str, Any]] = []
    if isinstance(changes_raw, list):
        for change in changes_raw:
            if not isinstance(change, dict):
                continue
            changes_out.append(
                {
                    "tool": change.get("tool"),
                    "args": change.get("args", {}),
                    "result": _extract_change_result(change.get("result")),
                }
            )

    verify = assess_verify_out.get("data", {}).get("verify", {})
    if not isinstance(verify, dict):
        verify = {}

    all_start = min(_parse_ts(e["ts"]) for e in entries)
    all_end = max(_parse_ts(e["ts"]) for e in entries)

    intent_in_events = [
        e for e in entries if e.get("node") == "intent" and e.get("direction") == "in"
    ]
    intent_out_events = [
        e for e in entries if e.get("node") == "intent" and e.get("direction") == "out"
    ]
    diagnose_in = _find(entries, "diagnose", "in", first=True)
    diagnose_out_event = _find(entries, "diagnose", "out", first=False)
    remediation_in = _find(entries, "remediation", "in", first=True)
    remediation_out = _find(entries, "remediation", "out", first=False)
    verify_in = _find(entries, "verify", "in", first=True)
    assess_verify_out_event = _find(entries, "assess_verify", "out", first=False)

    detect_s = 0.0
    if intent_in_events and intent_out_events:
        detect_s = round(
            (
                _parse_ts(intent_out_events[0]["ts"]) - _parse_ts(intent_in_events[0]["ts"])
            ).total_seconds(),
            1,
        )

    diagnose_s = 0.0
    if diagnose_in and diagnose_out_event:
        diagnose_s = round(
            (_parse_ts(diagnose_out_event["ts"]) - _parse_ts(diagnose_in["ts"])).total_seconds(), 1
        )

    remediate_s = 0.0
    if remediation_in and remediation_out:
        remediate_s = round(
            (_parse_ts(remediation_out["ts"]) - _parse_ts(remediation_in["ts"])).total_seconds(), 1
        )

    verify_s = 0.0
    if verify_in and assess_verify_out_event:
        verify_s = round(
            (_parse_ts(assess_verify_out_event["ts"]) - _parse_ts(verify_in["ts"])).total_seconds(),
            1,
        )

    get_info_out = _find(entries, "get_info", "out", first=False)
    verify_out = _find(entries, "verify", "out", first=False)

    tool_calls_pre_diagnosis = _tool_calls_count(get_info_out)
    tool_calls_verify = _tool_calls_count(verify_out)
    tool_calls_total = (
        tool_calls_pre_diagnosis + _tool_calls_count(remediation_out) + tool_calls_verify
    )

    run_id = (
        monitor_in_data.get("thread_id")
        or monitor_out.get("data", {}).get("thread_id")
        or "unknown"
    )
    test_case_id = f"tc_{_snake_case(str(input_alert.get('type', 'unknown')))}_{issue_type}_01"

    return {
        "metadata": {
            "run_id": run_id,
            "test_case_id": test_case_id,
            "started_at": monitor_in.get("ts", all_start.isoformat()),
            "ended_at": monitor_out.get("ts", all_end.isoformat()),
        },
        "input_alert": input_alert,
        "prediction": {
            "detected": bool(root_causes),
            "issue_type": issue_type,
            "device": input_alert.get("device"),
            "interface": input_alert.get("interface"),
            "root_causes_ranked": [
                {
                    "type": _normalize_issue_type(str(rc.get("type", "")))
                    if rc.get("type")
                    else None,
                    "cause": _normalize_issue_type(str(rc.get("cause", "unknown"))),
                    "confidence": rc.get("confidence"),
                    "evidence": rc.get("evidence", []),
                }
                for rc in root_causes
                if isinstance(rc, dict)
            ],
            "needs_fix": bool(intent_out_data.get("needs_fix")),
        },
        "plan": {
            "intent": intent_out_data.get("intent"),
            "steps": plan_steps if isinstance(plan_steps, list) else [],
        },
        "execution": {
            "changes": changes_out,
            "verify": {
                "passed": bool(verify.get("passed")),
                "evidence": _extract_verify_evidence_obj(verify),
                "remaining_issues": verify.get("remaining_issues", []),
            },
        },
        "metrics_input": {
            "timings": {
                "detect_s": detect_s,
                "diagnose_s": diagnose_s,
                "remediate_s": remediate_s,
                "verify_s": verify_s,
                "total_s": round((all_end - all_start).total_seconds(), 1),
            },
            "node_cycles": _node_cycles(entries),
            "counts": {
                "tool_calls_total": tool_calls_total,
                "tool_calls_pre_diagnosis": tool_calls_pre_diagnosis,
                "tool_calls_verify": tool_calls_verify,
                "remediation_attempts": 1 if remediation_in else 0,
                "plan_steps": len(plan_steps) if isinstance(plan_steps, list) else 0,
            },
            "tokens": _sum_tokens(entries),
        },
    }

# Write the extracted logs to a JSON file. This is the main entrypoint used by the monitor loop after each run.
def write_extracted_logs(
    input_path: Path = NODE_IO_LOG_PATH, output_path: Path = EXTRACTED_LOGS_PATH
) -> Path:
    entries = _load_jsonl(input_path)
    extracted = build_extracted(entries)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(extracted, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return output_path


if __name__ == "__main__":
    out = write_extracted_logs()
    print(f"Wrote: {out}")
