from __future__ import annotations

import json

from langchain_core.messages import SystemMessage
from state.types import AgentState

SYSTEM = """You are a network remediation agent.
You receive a remediation PLAN consisting of ordered change-steps. Your job is to execute the PLAN fully.

IMPORTANT: every toolcall is used with arg: "router<number>" and never with hostname.
Use full interface names (e.g. "GigabitEthernet0/0/1" not "Gi0/0/1").

Execution rules:
- You MUST execute EVERY change-step in the PLAN that is applicable. Do not stop after a single toolcall if more steps remain.
- Follow the PLAN order. If multiple steps target different devices, execute them in the order listed.
- For each PLAN step that requires a device change, perform exactly one corresponding toolcall (unless the step explicitly requires multiple distinct changes).
- If the PLAN contains N distinct change-steps, you should produce N toolcalls (or explicitly skip a step with a short reason only if it is inapplicable or already satisfied per inputs such as previous_changes).
- Do not invent commands. Only use the available tools and their supported actions.
- This node must ONLY execute remediation changes from the PLAN. Do NOT run verification/check/show commands.
- Keep changes minimal and reversible; do not touch unrelated interfaces/protocols.
- Avoid repeating failed change actions with identical arguments from previous_changes unless diagnosis has changed.

Stopping condition:
- You may only stop when all PLAN steps are executed or explicitly skipped with a reason tied to the given inputs (PLAN, previous_changes)."""


def remediation_node(state: AgentState, llm) -> dict:
    print("Executing remediation plan...")
    plan = state.get("plan") or {}
    plan_steps = plan.get("plan_steps") or []
    step_idx = int(state.get("remediation_step_idx") or 0)
    remedy_start_cursor = len(
        state.get("messages") or []
    )  # for controller to know from where to read remedy messages

    if step_idx >= len(plan_steps):
        print("No remaining remediation plan steps.")
        return {
            "phase": "fixed",
            "remedy_start_cursor": remedy_start_cursor,
            "remediation_done": True,
        }

    ctx = {
        "intent": state.get("intent"),
        "intent_description": state.get("intent_description"),
        "target": state.get("target"),
        "network_db": state.get("network_db") or {},
        "diagnosis": state.get("diagnosis") or {},
        "current_step_index": step_idx,
        "current_step": plan_steps[step_idx],
        "remaining_steps_after_current": max(len(plan_steps) - step_idx - 1, 0),
        "previous_changes": state.get("changes") or [],
        "attempts": state.get("attempts", 0),
    }

    step_instruction = (
        "Execute ONLY current_step now. "
        "Emit exactly one remediation tool call for this step and do not execute later steps yet."
    )
    msg = SystemMessage(
        content=SYSTEM + "\n\n" + step_instruction + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False)
    )
    ai = llm.invoke([msg], tool_choice="required")  # include tool_calls
    tc = getattr(ai, "tool_calls", None)
    print("tool_calls for remedy:", tc)
    return {"messages": [ai], "phase": "fixed", "remedy_start_cursor": remedy_start_cursor}
