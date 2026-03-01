# diagnose_node.py
from __future__ import annotations

import json

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from state.schemas import Diagnosis
from state.types import AgentState

SYSTEM = """You are a network diagnostician.

Goal:
Produce a structured diagnosis that is narrowly scoped to the user's intent_description. 
Do NOT expand into unrelated potential issues.

Inputs you may use:
- intent_description (primary scope/goal)
- user_input (secondary)
- observations from tool responses (ToolMessage) ONLY — treat these as factual, authoritative, and the most recent source of truth
- existing topology context (if present) — it may be outdated and must NOT override ToolMessage observations


Hard rules:
- Do not call tools in this node.
- Treat intent_description as the authoritative definition of "what counts as a problem i need to fix".
- Only diagnose issues that:
  1) directly explain the intent_description, AND
  2) are supported by observations/topology evidence.
- If evidence is insufficient, say so in missing_info; do not invent diagnoses.
- Ignore anomalies that are not relevant to the intent_description (even if observed), unless they block the intent goal.

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

    # Ta siste ~30 tool-relaterte meldinger som "observations"
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
        "intent_description": state.get("intent_description"),
        "target": state.get("target"),
        "network_information": state.get("network_db") or {},
        "observations": observations,
    }

    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    diag: Diagnosis = llm.with_structured_output(Diagnosis).invoke([msg])

    patch = {
        "observations": observations,
        "diagnosis": diag.model_dump(),
    }
    print(patch)
    return patch
