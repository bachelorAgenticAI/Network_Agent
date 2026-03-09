from __future__ import annotations

import json

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from agent.state.schemas import VerifyResult
from agent.state.types import AgentState
from agent.utils.logger import log_node_enter, log_node_exit

SYSTEM = """You evaluate the result of verify-tools and conclude passed=True/False.
Rules:
- Base your assessment on ToolMessage outputs.
- Use the most recent verification round as primary evidence.
- passed=True only if the verification actually shows that the designated problem is gone.
- Passed=false if verification shows the problem is still there OR if evidence is missing/inconclusive.
- If evidence is missing or inconclusive, set passed=False and populate missing_info.
Return structured output.
"""


def _extract_recent_verify_tool_msgs(state: AgentState, limit: int = 30) -> list[dict]:
    msgs = state.get("messages") or []
    start = int(state.get("verify_start_cursor") or 0)
    window = msgs[start:]

    toolish = []
    for m in reversed(window):
        if isinstance(m, ToolMessage):
            toolish.append(
                {
                    "type": "ToolMessage",
                    "name": getattr(m, "name", None),
                    "tool_call_id": getattr(m, "tool_call_id", None),
                    "content": m.content,
                }
            )
        elif isinstance(m, AIMessage) and (getattr(m, "tool_calls", None) or []):
            toolish.append(
                {
                    "type": "AIMessage",
                    "tool_calls": getattr(m, "tool_calls", None) or [],
                }
            )

        if len(toolish) >= limit:
            break

    if not toolish:
        for m in reversed(msgs):
            if isinstance(m, ToolMessage):
                toolish.append(
                    {
                        "type": "ToolMessage",
                        "name": getattr(m, "name", None),
                        "tool_call_id": getattr(m, "tool_call_id", None),
                        "content": m.content,
                    }
                )
            elif isinstance(m, AIMessage) and (getattr(m, "tool_calls", None) or []):
                toolish.append(
                    {
                        "type": "AIMessage",
                        "tool_calls": getattr(m, "tool_calls", None) or [],
                    }
                )

            if len(toolish) >= limit:
                break

    return list(reversed(toolish))


def assess_verify_node(state: AgentState, llm) -> dict:
    print("Assessing verification results...")

    db = state.get("network_db") or {}
    obs = _extract_recent_verify_tool_msgs(state, limit=30)

    ctx = {
        "diagnosis": state.get("diagnosis") or {},
        "plan": state.get("plan") or {},
        "verify_observations": obs,
        "network_db": db,
    }

    log_node_enter("assess_verify", ctx)

    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    out: VerifyResult = llm.with_structured_output(VerifyResult).invoke([msg])

    patch = {
        "verify": out.model_dump(),
    }

    log_node_exit("assess_verify", patch)
    return patch
