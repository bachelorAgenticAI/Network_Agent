from __future__ import annotations

from langchain_core.messages import HumanMessage
from state.types import AgentState


def ingestion(state: AgentState) -> dict:
    txt = (state.get("user_input") or "").strip()

    updates: dict = {
        "phase": "start",
    }

    if txt:
        updates["messages"] = [HumanMessage(content=txt)]
        # On new user input: do not blindly wipe everything; keep topology/observations/history
        # but clear controller fields that should be recomputed.
        updates.update(
            {
                "intent": None,
                "target": None,
                "approved": False,
                "needs_fix": None,
                "diagnosis": {},
                "plan": {},
                "verify": {},
                "attempts": 0,
            }
        )

    return updates
