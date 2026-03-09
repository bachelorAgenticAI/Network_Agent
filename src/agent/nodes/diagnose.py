# diagnose_node.py
from __future__ import annotations

import json

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from agent.state.schemas import Diagnosis
from agent.state.types import AgentState
from agent.utils.logger import log_node_enter, log_node_exit

SYSTEM = """You are a network diagnostician.

Goal:
Produce a structured diagnosis that is narrowly scoped to the alert_description.
Do NOT expand into unrelated potential issues.
Do NOT include confirmation steps or verification steps in the diagnosis. Focus on identifying the root cause(s) of the problem as defined by the alert_description.

Inputs you may use:
- alert_description (primary scope/goal)
- observations from tool responses (ToolMessage) ONLY — treat these as factual, authoritative, and the most recent source of truth
- existing topology context (if present) — it may be outdated and must NOT override ToolMessage observations

Hard rules:
- Do not call tools in this node.
- Treat alert_description as the authoritative definition of "what counts as a problem i need to fix". 
- There may be multiple fixes and problems. Rank them by likelihood and relevance to the alert_description.
- Dont list potential for the diagnose/fix you would take, just the actual diagnosis of the problem based on evidence. The next node will determine the fix based on the diagnosis you provide.
- Only diagnose issues that:
  1) directly explain the alert_description, AND
  2) are supported by observations/topology evidence.
- If evidence is insufficient, say so in missing_info; do not invent diagnoses.
- Ignore anomalies that are not relevant to the alert_description (even if observed), unless they block the alert goal.
- Prioritize fresh observations from this round (latest info collection) over older observations.
- If multiple root causes are possible, include them all but rank them by likelihood and support from evidence.
- Keep root_causes concise, but include concrete evidence snippets from tool outputs.

Output format:
Return ONLY a single JSON object with this schema:
If no root cause can be supported, set root_causes to [] and populate missing_info with the minimum questions needed.
"""


def _is_tool_related(m):
    return isinstance(m, ToolMessage) or (
        isinstance(m, AIMessage) and (getattr(m, "tool_calls", None) or [])
    )


def diagnose_node(state: AgentState, llm) -> dict:
    print("Diagnosing...")
    messages = state.get("messages") or []

    info_start = int(state.get("info_start_cursor") or 0)
    recent_window = messages[info_start:]

    recent_tool_msgs = [m for m in recent_window if _is_tool_related(m)][-30:]
    if not recent_tool_msgs:
        recent_tool_msgs = [m for m in messages if _is_tool_related(m)][-30:]

    observations = []
    for m in recent_tool_msgs:
        if isinstance(m, ToolMessage):
            observations.append(
                {"type": "ToolMessage", "name": getattr(m, "name", None), "content": m.content}
            )
        elif isinstance(m, AIMessage):
            observations.append(
                {"type": "AIMessage", "tool_calls": getattr(m, "tool_calls", None) or []}
            )

    ctx = {
        "intent": state.get("intent"),
        "alert_description": state.get("intent_description"),
        "target": state.get("target"),
        "attempts": state.get("attempts", 0),
        "network_information": state.get("network_db") or {},
        "observations": observations,
        "previous_changes": state.get("changes") or [],
    }
    log_node_enter("diagnose", ctx)
    print("Diagnose node description:", state.get("intent_description"))
    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    diag: Diagnosis = llm.with_structured_output(Diagnosis).invoke([msg])

    patch = {
        "observations": observations,
        "diagnosis": diag.model_dump(),
    }
    print(patch)
    log_node_exit("diagnose", patch)
    return patch
