# diagnose_node.py
from __future__ import annotations

import json

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from agent.state.schemas import Diagnosis
from agent.state.types import AgentState

SYSTEM = """You are a network diagnostician.
Use observations from tool responses (ToolMessage) and the existing topology to create a structured diagnosis.

Rules:
- Do not call tools in this node.
- Return only Diagnosis (root_causes/risks/missing_info) structured.
"""


def _is_tool_related(m):
    return isinstance(m, ToolMessage) or (
        isinstance(m, AIMessage) and (getattr(m, "tool_calls", None) or [])
    )


def diagnose_node(state: AgentState, llm) -> dict:
    print("Diagnosing...")

    db = state.get("network_db") or {}
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
        "target": state.get("target"),
        "network_db": db,
        "observations": observations,
    }

    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    diag: Diagnosis = llm.with_structured_output(Diagnosis).invoke([msg])

    patch = {
        "observations": observations,
        "diagnosis": diag.model_dump(),
    }
    return patch
