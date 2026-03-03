from __future__ import annotations

import json

from langchain_core.messages import SystemMessage
from state.schemas import IntentOut
from state.types import AgentState
from utils.logger import log_node_enter, log_node_exit, log_schema_output

SYSTEM = """You are a network agent controller.

Tasks:
Main task is to classify intent and target and make decisions. You are the boss and authorize changes.

When a diagnosis exists in state:
- determine needs_fix (True/False)
- Set needs_fix=False if the diagnosis indicates the intent has been fulfilled
- create a plan if needs_fix=True.

Rules:
- If diagnosis is missing: needs_fix and plan must be null/empty.
- If verify shows the problem is still present, verify must be set to an empty dict.

Intent:
- Base intent on input/alert (check, check_and_fix) and create a suitable intent_description for other nodes.
- If the input/alert does NOT describe a concrete problem, OR the agent appears to be operating in a network for the first time, you MUST:
  - set intent = "check"
  - create an intent_description stating that the goal is to learn as much as possible about the network, discover its structure and state, identify all potential problems or risks.
- If the input/alert does describe a concrete problem:
 - set intent = "check_and_fix"
 - If attempts > 0, you have already tried to fix the problem, but it is still not resolved.
- When attempts > 0, adjust plan to avoid repeating already failed changes unless diagnosis evidence has changed.
- Do NOT include: authorization/approval requests, “confirm”, “get credentials”, “SSH/CLI commands”, “enter config mode”, “backup config”, “document/audit”, or long verification procedures.
- If required info is missing, do NOT put it in plan_steps; it must be placed in diagnosis.missing_info instead.
- Base the plan heavily on (user input)/alert, and use diagnosis only to fill necessary details on how to fix the issue related to the input/alert.
- Do not create plans for minor or unrelated problems from diagnosis.
- Do not create a plan unless the input/alert indicates a desire for fixing/remediation.
- plan_steps MUST be short and executable instructions for the remediation node and not include steps for "After changes: verify" etc.
- plan_steps should focus only on the minimal corrective actions; do not include verification/sanity-check steps (verification happens in verify node).


Return pure JSON that matches the schema.
"""

# need to add state.get types to properly log state in this node


def intent_node(state: AgentState, llm) -> dict:
    print("Determining intent")
    # Uses only the latest user input
    user_input = (state.get("user_input") or "").strip()
    diagnosis = state.get("diagnosis")
    intent_description = state.get("intent_description") or {}
    messages = state.get("messages") or []
    print("Previous messages in state:")
    for m in messages:
        print(f"- {type(m).__name__}: {getattr(m, 'content', '')[:100]}")  # print type and content preview

    ctx = {
        "user_input": user_input if user_input else None,
        "intent_description": intent_description if intent_description else None,
        "current_intent": state.get("intent") or [],
        "current_target": state.get("target"),
        "diagnosis": diagnosis if diagnosis else None,
        "failed_changes": state.get("changes") or [],
        "number_of_attempts": state.get("attempts", 0),
    }
    print("Intent node context:", ctx)
    log_node_enter("intent", ctx)

    msg = SystemMessage(content=SYSTEM + "\n\nSTATE:\n" + json.dumps(ctx, ensure_ascii=False))

    out: IntentOut = llm.with_structured_output(IntentOut).invoke([msg])

    log_schema_output("intent", schema=IntentOut, output=out, state=state)

    updates: dict = {
        "intent": out.intent,
        "target": out.target,
        "intent_description": out.intent_description,
    }

    # Only set needs_fix/plan after diagnosis exists
    if diagnosis is not None:
        # Tom diagnose => ingen funn => ikke noe å fikse
        if not (diagnosis.get("root_causes") or diagnosis.get("risks") or diagnosis.get("missing_info")):
            updates["needs_fix"] = False
            updates["plan"] = {}
            updates["phase"] = "have_diagnosis"
            log_node_exit("intent", updates)
            print("attempts in assess_verify:", state.get("attempts"))
            return updates

        if out.needs_fix is not None:
            updates["needs_fix"] = bool(out.needs_fix)
        plan_dict = out.plan.model_dump()
        if plan_dict:
            print("Added plan to state")
            updates["plan"] = plan_dict
            print(plan_dict)
        updates["phase"] = "have_diagnosis"

    # Log node exit with the updates and a preview of the new state
    log_node_exit("intent", updates)
    print("attempts in assess_verify:", state.get("attempts"))
    return updates
