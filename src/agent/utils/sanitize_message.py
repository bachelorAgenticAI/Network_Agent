import json

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage


def sanitize_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    Sørger for at alle tool_calls i historikken har en ToolMessage
    med matchende tool_call_id.

    Hvis agenten krasjer etter at LLM har laget tool_calls men før tools
    har returnert svar, vil checkpointer lagre en inkonsistent state.
    Denne funksjonen reparerer den før neste turn.

    Idempotent: legger ikke inn duplikater.
    """

    if not messages:
        return messages

    # --- Finn alle forventede tool_call_id ---
    expected_ids: list[str] = []

    for msg in messages:
        if isinstance(msg, AIMessage):
            tool_calls = getattr(msg, "tool_calls", None) or []
            for tc in tool_calls:
                tc_id = tc.get("id")
                if tc_id:
                    expected_ids.append(tc_id)

    if not expected_ids:
        return messages

    # --- Finn hvilke som allerede er besvart ---
    responded_ids: set[str] = set()

    for msg in messages:
        if isinstance(msg, ToolMessage):
            tc_id = getattr(msg, "tool_call_id", None)
            if tc_id:
                responded_ids.add(tc_id)

    # --- Manglende responses ---
    missing_ids = [
        tc_id for tc_id in expected_ids
        if tc_id not in responded_ids
    ]

    if not missing_ids:
        return messages

    repaired = list(messages)

    for tc_id in missing_ids:
        repaired.append(
            ToolMessage(
                tool_call_id=tc_id,
                content=json.dumps({
                    "error": "auto_resolved_pending_tool_call",
                    "message": (
                        "Previous tool call had no response. "
                        "Agent likely crashed before tool execution completed."
                    ),
                }),
            )
        )

    return repaired
