# diagnose_node.py
from __future__ import annotations
import json
from langchain_core.messages import SystemMessage
from state.types import AgentState
from state.schemas import Diagnosis

from nodes.helpers.observations import (
    extract_recent_tool_messages, 
    extract_tool_call_map, 
    tool_messages_to_observations
)
from nodes.helpers.persist import persist_observations
from utils.logger import log_node_enter, log_node_exit, log_schema_output

SYSTEM = """You are a network diagnostician.
Use observations from tool responses (ToolMessage) and the existing topology to create a structured diagnosis.

Rules:
- Do not call tools in this node.
- Return only Diagnosis (root_causes/risks/missing_info) structured.
"""


def diagnose_node(state: AgentState, llm) -> dict:
    print("Diagnosing...")

    tool_msgs = extract_recent_tool_messages(state.get("messages", []))
    tool_call_map = extract_tool_call_map(state.get("messages", []))
    new_obs = tool_messages_to_observations(tool_msgs, tool_call_map)

    observations = (state.get("observations") or []) + new_obs 

    db = persist_observations(
        new_obs,
        target=state.get("target"),
        db=state.get("network_db"),
        keep_history=True,
        flush_to_disk=True,
    )

    ctx = {
        "intent": state.get("intent"),
        "target": state.get("target"),
        "network_db": db,
        "observations_tail": observations[-25:],
    }
    log_node_enter("diagnose", ctx)

    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))    
    diag: Diagnosis = llm.with_structured_output(Diagnosis).invoke([msg])
    log_schema_output("diagnose", schema=Diagnosis, output=diag, state=state)

    patch = {
        "observations": observations,
        "network_db": db,
        "diagnosis": diag.model_dump(),
    }

    log_node_exit("diagnose", patch)
    return patch

