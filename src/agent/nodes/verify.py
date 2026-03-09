from __future__ import annotations

import json

from langchain_core.messages import SystemMessage

from agent.state.types import AgentState
from agent.utils.logger import log_node_enter, log_node_exit

SYSTEM = """You are a verification agent.
Run relevant verify-tools based on the diagnosis, plan, and executed changes.

IMPORTANT: every toolcall is used with arg: "router<number>" and never with hostname. Use full interface names (e.g. "GigabitEthernet0/0/1" not "Gi0/0/1").

Rules:
- Use tools for verification (do not guess).
- Do not include any form of comfirmation or authorization steps.
- Do not conclude passed/failed. Just run tools and report results.
- Verify only the original problem scope first, then include one safety check for obvious side effects if relevant.
- Prefer direct symptom checks over broad status dumps.
"""


def verify_node(state: AgentState, llm) -> dict:
    print("Running verification tools...")
    verify_start_cursor = len(state.get("messages") or [])
    ctx = {
        "target": state.get("target"),
        "network_db": state.get("network_db") or {},
        "diagnosis": state.get("diagnosis") or {},
        "plan": state.get("plan") or {},
        "changes_tail": (state.get("changes") or [])[-25:],
    }
    log_node_enter("verify", ctx)
    msg = SystemMessage(content=SYSTEM + "\n\nCTX:\n" + json.dumps(ctx, ensure_ascii=False))
    ai = llm.invoke([msg])  # may include tool_calls
    out = {"messages": [ai], "phase": "verified", "verify_start_cursor": verify_start_cursor}
    log_node_exit("verify", out)
    return out
