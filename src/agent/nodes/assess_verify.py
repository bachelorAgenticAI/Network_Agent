# assess_verify.py
from __future__ import annotations

import json

from langchain_core.messages import SystemMessage
from nodes.helpers.observations import (
    extract_recent_tool_messages,
    extract_tool_call_map,
    tool_messages_to_observations,
)
from nodes.helpers.persist import persist_observations
from state.schemas import VerifyResult
from state.types import AgentState
from utils.logger import log_node_enter, log_node_exit, log_schema_output

SYSTEM = """You evaluate the result of verify-tools and conclude passed=True/False.
Rules:
- Base your assessment on ToolMessage outputs.
- passed=True only if the verification actually shows that the problem is gone.
Return structured output.
"""


def assess_verify_node(state: AgentState, llm) -> dict:
    print("Assessing verification results...")
    tool_msgs = extract_recent_tool_messages(state.get("messages", []))
    tool_call_map = extract_tool_call_map(state.get("messages", []))
    obs = tool_messages_to_observations(tool_msgs, tool_call_map)

    # Persist tool results to long-term DB + update in-memory state cache
    db = persist_observations(
        obs,
        target=state.get("target"),
        db=state.get("network_db"),
        keep_history=True,
        flush_to_disk=True,
    )

    ctx = {
        "diagnosis": state.get("diagnosis") or {},
        "plan": state.get("plan") or {},
        "verify_observations": obs,
        "network_db": db,
    }

    log_node_enter("assess_verify", ctx)

    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    out: VerifyResult = llm.with_structured_output(VerifyResult).invoke([msg])

    log_schema_output("assess_verify", schema=VerifyResult, output=out, state=state)

    patch = {
        "network_db": db,  # <-- expose current state to the rest of the graph
        "verify": out.model_dump(),
    }
    log_node_exit("assess_verify", patch)

    return patch
