from __future__ import annotations

import json

from langchain_core.messages import SystemMessage

from agent.state.types import AgentState
from agent.utils.logger import log_node_enter, log_node_exit

SYSTEM = """You are a network remediation agent.
You receive a remediation PLAN consisting of ordered change-steps. Your job is to execute the PLAN fully.

IMPORTANT: every toolcall is used with arg: "router<number>" and never with hostname.
Use full interface names (e.g. "GigabitEthernet0/0/1" not "Gi0/0/1").

Execution rules:
- You MUST execute EVERY change-step in the PLAN that is applicable. Do not stop after a single toolcall if more steps remain.
- Follow the PLAN order. If multiple steps target different devices, execute them in the order listed.
- For each PLAN step that requires a device change, perform exactly one corresponding toolcall.
- Do not invent commands. Only use the available tools and their supported actions.
- This node must ONLY execute remediation changes from the PLAN. Do NOT run verification/check/show commands.
- Keep changes minimal and reversible; do not touch unrelated interfaces/protocols.
- Avoid repeating failed change actions with identical arguments from previous_changes unless diagnosis has changed.

Stopping condition:
- Stop when all PLAN steps are executed.
"""


def remediation_node(state: AgentState, llm) -> dict:
    print("Executing remediation plan...")
    plan = state.get("plan") or {}
    plan_steps = plan.get("plan_steps") or []
    step_idx = int(state.get("remediation_step_idx") or 0)
    remedy_start_cursor = len(state.get("messages") or [])

    if step_idx >= len(plan_steps):
        print("No remaining remediation plan steps.")
        out = {
            "phase": "fixed",
            "remedy_start_cursor": remedy_start_cursor,
            "remediation_done": True,
        }
        return out

    current_step = plan_steps[step_idx] or {}
    action_name = (current_step.get("action") or "").strip()

    ctx = {
        "intent": state.get("intent"),
        "alert_description": state.get("intent_description"),
        "target": state.get("target"),
        "network_db": state.get("network_db") or {},
        "diagnosis": state.get("diagnosis") or {},
        "current_step_index": step_idx,
        "current_step": current_step,
        "current_step_action": action_name,
        "remaining_steps_after_current": max(len(plan_steps) - step_idx - 1, 0),
        "previous_changes": state.get("changes") or [],
        "attempts": state.get("attempts", 0),
    }
    log_node_enter("remediation", ctx)

    step_instruction = (
        "Execute ONLY current_step now. "
        "Emit exactly one remediation tool call for this step and do not execute later steps yet. "
        "The tool name MUST exactly match current_step.action. Do not substitute a different tool."
    )
    msg = SystemMessage(
        content=SYSTEM + "\n\n" + step_instruction + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False)
    )

    ai = llm.invoke([msg], tool_choice="required")
    tc = getattr(ai, "tool_calls", None)
    print("tool_calls for remedy:", tc)
    out = {"messages": [ai], "phase": "fixed", "remedy_start_cursor": remedy_start_cursor}
    log_node_exit("remediation", out)
    return out
