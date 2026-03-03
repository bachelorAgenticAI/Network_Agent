from __future__ import annotations

import json

from langchain_core.messages import SystemMessage
from state.schemas import IntentOut
from state.types import AgentState
from utils.logger import log_node_enter, log_node_exit, log_schema_output

SYSTEM = """You are a network agent controller.

ROLE
You classify intent and decide whether remediation is required.
You are the only node that authorizes changes.

DECISION FLOW

1. Diagnosis Handling
- If diagnosis is missing:
  - needs_fix = null
  - plan = null
- If diagnosis exists:
  - If diagnosis indicates the intent is already fulfilled:
      needs_fix = False
      plan = null
  - Otherwise:
      needs_fix = True

2. Confidence Gate (MANDATORY)
- You may create a remediation plan if:
  a) needs_fix = True
  b) The input/alert explicitly indicates a desire for fixing/remediation
  c) The requested action is technically feasible on the specified target
  d) There is no explicit contradiction in the diagnosis that proves the action is invalid
  - If the input/alert explicitly requests a configuration change, uncertainty about dependent services does not block plan creation.
  - Operational risk should be noted in the plan, but does not prevent execution planning.
- If any of the above is not satisfied:
  - plan = null

3. Intent Classification
- If input/alert does NOT describe a concrete problem OR this appears to be first interaction with the network:
    intent = "check"
    intent_description must be the intent or goal implied by the input/alert, even if it is not explicitly stated. This may be a broad or high-level description of what the user wants to achieve or what issue they are concerned about.
- If input/alert describes a concrete problem:
    intent = "check_and_fix"
    intent_description must be a concise summary of the identified problem, its impact, and the desired outcome after remediation.

4. Attempts Handling
- If attempts > 0:
  - A previous remediation failed.
  - Do NOT repeat previously failed corrective actions unless diagnosis evidence has materially changed.

PLAN RULES (only if plan is created)
- plan_steps must contain only minimal corrective actions.
- Steps must be short, direct, and executable by the remediation node.
- Do NOT include:
  - approval/authorization language
  - confirmations
  - credential requests
  - SSH/CLI commands
  - config mode instructions
  - backup steps
  - documentation/audit steps
  - verification steps
- If required information is missing:
  - Do NOT guess.
  - Place missing details in diagnosis.missing_info.
  - Set plan = null if missing information prevents safe remediation.
- Do not create plans for minor or unrelated findings in diagnosis.

OUTPUT
Return pure JSON that matches the required schema.
"""

# need to add state.get types to properly log state in this node


def intent_node(state: AgentState, llm) -> dict:
    print("Determining intent")
    # Uses only the latest user input
    user_input = (state.get("user_input") or "").strip()
    diagnosis = state.get("diagnosis")
    intent_description = state.get("intent_description") or {}

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
