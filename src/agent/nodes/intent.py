from __future__ import annotations

import json
from langchain_core.messages import SystemMessage
from state.types import AgentState
from state.schemas import IntentOut

from utils.logger import log_node_enter, log_node_exit, log_schema_output


SYSTEM = """You are a network agent controller.
Tasks:

In the first round (when user_input exists): classify intent and target, and whether the user approves changes.
When a diagnosis exists in state: determine needs_fix (True/False) and create a plan if needs_fix=True.

Rules:
- approved=True only with explicit approval (e.g., "yes, make the changes", "go ahead", "fix it").
- If diagnosis is missing: needs_fix and plan must be null/empty.

Intent:
- "check": only check/diagnose
- "check_and_fix": check and fix automatically if errors are found
- "fix": fix (but requires info/diagnosis first)
- "unknown": unclear
Return pure JSON that matches the schema.
"""


def intent_node(state: AgentState, llm) -> dict:
    print("Determining intent and plan...")
    # Build compact context
    user_input = (state.get("user_input") or "").strip()
    diagnosis = state.get("diagnosis") or {}

    ctx = {
        "user_input": user_input if user_input else None,
        "current_intent": state.get("intent"),
        "current_target": state.get("target"),
        "approved": state.get("approved", False),
        "diagnosis": diagnosis if diagnosis else None,
    }

    log_node_enter("intent", ctx)

    msg = SystemMessage(content=SYSTEM + "\n\nSTATE:\n" + json.dumps(ctx, ensure_ascii=False))

    out: IntentOut = llm.with_structured_output(IntentOut).invoke([msg])
    
    log_schema_output("intent", schema=IntentOut, output=out, state=state)

    updates: dict = {
        "intent": out.intent,
        "target": out.target,
        "approved": bool(out.approved),
    }

    # Only set needs_fix/plan after diagnosis exists
    if diagnosis:
        if out.needs_fix is not None:
            updates["needs_fix"] = bool(out.needs_fix)
        plan_dict = out.plan.model_dump()
        if plan_dict:
            updates["plan"] = plan_dict
        updates["phase"] = "have_diagnosis"
    
    # Log node exit with the updates and a preview of the new state
    log_node_exit("intent", updates)
    return updates
