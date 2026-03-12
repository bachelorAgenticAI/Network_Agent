"""Main controller agent. Classify intent and decide whether remediation planning is required."""

from __future__ import annotations

import json

from langchain_core.messages import SystemMessage

from agent.state.schemas import IntentOut
from agent.state.types import AgentState
from agent.utils.logger import log_node_enter, log_node_exit

SYSTEM = """You are a network agent controller.

ROLE
You classify intent and decide whether remediation is required.
You are the only node that authorizes changes.
You may make reasonable assumptions about incomplete input and translate a high-level request into the necessary configuration steps.
For optional fields such as names, descriptions, or labels:
- use the values from the alerts when provided; otherwise generate reasonable defaults.

CONTEXT HANDLING
- The alert field may be present, empty, null, or a placeholder string.
- Treat these values as NO ALERT CONTEXT: null, "", "None", "none", "null", "[]", "{}", "no alert", "no context", "n/a".
- A missing/placeholder alert does NOT imply a network fault.
- Do NOT invent a fault when there is no supporting evidence.

DECISION FLOW

1. Diagnosis Handling
- If diagnosis is missing:
  - needs_fix = null
  - plan = null
- If diagnosis exists:
  - If diagnosis.root_causes is empty:
      needs_fix = False
      plan = null
  - Otherwise:
      needs_fix = True

2. Confidence Gate (MANDATORY)
- Create a remediation plan if:
  a) needs_fix = True
  b) At least one diagnosis.root_cause is supported by concrete evidence.
  c) The requested action is technically feasible on the specified target.
  d) There is no explicit contradiction in diagnosis that proves the action is invalid.
- If alert explicitly requests a configuration change, uncertainty about dependent services does not block planning.
- Operational risk should not be noted in the plan, but does not prevent execution planning.
- If any condition is not satisfied:
  - plan = null
  - needs_fix = False

3. Intent Classification
- If alert is NO ALERT CONTEXT (see Context Handling) OR alert does not describe a concrete problem OR this appears to be first interaction:
    intent = "check"
    intent_description must describe what should be inspected first based on available context. 
    - If no context exists: intent_description must be an instruct to gather baseline network information by running the available information tools. The description should request collection of:
      - router names
      - device configuration summaries
      - interface states
      - ARP tables
      - OSPF status
      - DHCP state
- If alert describes or indicate a problem:
    intent = "check_and_fix"
    intent_description must be a concise summary of the identified problem, its impact, and the desired outcome after remediation.

4. Attempts Handling
- If attempts > 0:
  - A previous remediation failed.
  - Do NOT repeat previously failed corrective actions unless diagnosis evidence has materially changed.
  - Read previous_changes, may be success or failure.

PLAN RULES (only if plan is created)
- plan_steps must be atomic: one step = one device change = one remediation tool call.
- Do not include multiple actions in one step. If you need 3 changes, create 3 steps.
- Each step must include device: "router<number>" and full interface names where applicable (e.g. "GigabitEthernet0/0/1" not "Gi0/0/1").
- Each step must specify exactly one action from the remediation tools supported actions.
- `action` must exactly match an available remediation tool name.
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
  - Make reasonable assumptions and still produce a remediation plan only when diagnosis.root_causes has supported evidence.
  - Place missing details in diagnosis.missing_info.
  - If new diagnosis remains consistent with previous diagnosis, you may reuse previously failed plan steps that are still relevant.
- If needs_fix = True, plan_steps must not be empty.
- Do not create plans for minor or unrelated findings in diagnosis.

OUTPUT
Return pure JSON that matches the required schema.
"""

# This node determines the intent from the alert and after diagnosis is available, decides whether remediation is needed and generates a plan.
def intent_node(state: AgentState, llm) -> dict:
    print("Determining intent")
    Alert_input = (state.get("user_input") or "").strip()
    diagnosis = state.get("diagnosis")
    intent_description = state.get("intent_description") or {}

    ctx = {
        "Alert_info": Alert_input if Alert_input else None,
        "intent_description": intent_description if intent_description else None,
        "current_intent": state.get("intent") or [],
        "current_target": state.get("target"),
        "diagnosis": diagnosis if diagnosis else None,
        "Previous_changes": state.get("changes") or [],
        "number_of_attempts": state.get("attempts", 0),
    }
    log_node_enter("intent", ctx) # Logger

    # IntentOut gives typed control fields used for graph routing.
    msg = SystemMessage(content=SYSTEM + "\n\nSTATE:\n" + json.dumps(ctx, ensure_ascii=False))
    out: IntentOut = llm.with_structured_output(IntentOut).invoke([msg])

    updates: dict = {
        "intent": out.intent,
        "target": out.target,
        "intent_description": out.intent_description,
    }

    if diagnosis is not None:
        # Only explicit root causes should unlock remediation.
        has_root_causes = bool(diagnosis.get("root_causes") or [])

        if not has_root_causes:
            updates["needs_fix"] = False
            updates["plan"] = {}
            updates["phase"] = "have_diagnosis"
            log_node_exit("intent", updates) # Logger
            return updates

        updates["needs_fix"] = bool(out.needs_fix) if out.needs_fix is not None else True

        if updates["needs_fix"] and out.plan.plan_steps:
            # Persist generated plan only when remediation is required.
            updates["plan"] = out.plan.model_dump()
        else:
            updates["needs_fix"] = False
            updates["plan"] = {}

        updates["phase"] = "have_diagnosis"

    log_node_exit("intent", updates) # Logger
    return updates
