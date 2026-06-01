"""
Single-node baseline for comparison against the multi-node workflow.

The graph invokes one LangGraph node, but that node may run multiple LLM/tool rounds internally.
Each round appends the AI response and tool results to the same message history, so later LLM calls
reason over more accumulated evidence than earlier calls.
"""
 

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

SRC_ROOT = Path(__file__).resolve().parents[1]
try:
    sys.path.remove(str(SRC_ROOT))
except ValueError:
    pass
sys.path.insert(0, str(SRC_ROOT))

from agent.state.schemas import Diagnosis, Plan, VerifyResult  # noqa: E402
from agent.state.types import AgentState  # noqa: E402
from agent.utils.logger import log_node_enter, log_node_exit  # noqa: E402
from mcp_app.utils.routers import ROUTERS  # noqa: E402

load_dotenv()

DEFAULT_OUTPUT = Path(__file__).resolve().parent / "logger" / "simple_baseline_result.json"
DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"
DEFAULT_ALERTS = Path(__file__).resolve().parent / "memory" / "custom_alerts.json"


class BaselineToolRecord(BaseModel):
    phase: Literal["information", "remediation", "verification", "unknown"] = "unknown"
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: Any = None


class BaselineResult(BaseModel):
    intent: Literal["check", "check_and_fix"]
    intent_description: str
    target: str | None = None
    diagnosis: Diagnosis = Field(default_factory=Diagnosis)
    needs_fix: bool
    plan: Plan = Field(default_factory=Plan)
    changes: list[BaselineToolRecord] = Field(default_factory=list)
    verify: VerifyResult
    final_summary: str
    tool_records: list[BaselineToolRecord] = Field(default_factory=list)
    reasoning_trace: list[str] = Field(default_factory=list)
    residual_risk: list[str] = Field(default_factory=list)


SYSTEM = """You are a single-node network troubleshooting baseline agent.

You must follow this chain strictly inside this single node:
1. Understand the injected alert and classify intent.
2. Gather evidence with MCP tools before diagnosing. Use tool evidence, not guesses.
3. Form an initial diagnosis from only the pre-remediation evidence. Diagnose only issues directly relevant to the alert.
4. Create a remediation plan from that initial diagnosis. Do not remediate before you have a diagnosis and plan.
5. Execute the planned remediation with the available remediation tools when the alert requires repair.
6. Verify the result with MCP tools after remediation, or verify current state for check-only alerts.
7. Produce the final structured JSON output only after the understand -> gather -> diagnose -> plan -> remedy -> verify chain is complete.

Tool rules:
- Use router identifiers like "router1", "router2", etc. Never use hostnames as router arguments.
- If the alert says R1, R2, etc., translate that to router1, router2, etc. in tool calls.
- Use full interface names such as "GigabitEthernet0/0/1"; do not abbreviate.
- If the alert describes a concrete network problem or failed service, treat that
  as authorization to gather evidence, diagnose, apply the minimal relevant fix,
  and verify the result without asking for confirmation.
- Read-only tools should be used before remediation unless the alert contains an explicit configuration target with enough detail.
- Remediation tools change device state. Use them when the alert indicates a concrete network problem that needs repair.
- Keep changes scoped to the alert. Do not touch unrelated protocols, interfaces, or devices.
- After remediation, use verification tools to check whether the original alert condition is resolved.

Output rules:
- During tool-use rounds, call tools or briefly state what you have learned.
- Do not ask for confirmation inside this baseline. If details are incomplete, make reasonable assumptions from router_mapping, alert fields, and tool evidence; record uncertainty in missing_info or residual_risk.
- When all needed tool calls are complete, return ONLY one valid JSON object. Do not wrap it in markdown.
- The final JSON must contain these top-level keys: intent, intent_description, target, diagnosis, needs_fix, plan, changes, verify, final_summary, tool_records, reasoning_trace, residual_risk.
- target must be a string or null, for example "router1 GigabitEthernet0/0/1"; never an object.
- diagnosis.root_causes items must contain type, cause, evidence as a list of strings, and confidence.
- diagnosis must describe the initial alert condition or requested state based on evidence gathered before remediation.
- Do not put failed remediation attempts, API errors from change tools, or post-remediation verification failures in diagnosis.root_causes.
- Put remediation execution failures in changes, verify.remaining_issues, residual_risk, and final_summary instead.
- For explicit configuration alerts, the diagnosis may be "target identified and current state differs from requested state" or "requested change target identified"; it should not become "remediation failed" after the change attempt.
- plan.plan_steps items must contain id, device, action, target, and parameters.
- residual_risk must be a list of strings, never a single string.
- tool_records and changes must use keys phase, tool, args, and result.
- intent is "check" when the alert only calls for investigation/status.
- intent is "check_and_fix" when the alert describes a concrete problem needing repair or configuration/remediation.
- diagnosis.root_causes must be supported by tool evidence.
- needs_fix is false when no supported problem remains or the alert only calls for a check.
- plan.plan_steps must describe only real remediation actions that were executed or should have been executed.
- changes must include only configuration-changing tool calls.
- verify.passed is true only when evidence shows the original alert condition is gone or the check is healthy.
- If verification is inconclusive, set verify.passed=false and explain missing evidence.
- final_summary should be short and alert-focused.
- reasoning_trace should be concise phase-level notes, not hidden chain-of-thought.
"""


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _jsonable(model_dump())
        except Exception:
            return str(value)

    return str(value)


def _extract_json_object(text: Any) -> dict[str, Any]:
    if not isinstance(text, str):
        raise ValueError("final assistant message is not text")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError("final assistant message JSON is not an object")
    return parsed


def _fallback_result(alert_input: str, tool_records: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    changes = [record for record in tool_records if record.get("phase") == "remediation"]
    result = BaselineResult(
        intent="check_and_fix" if changes else "check",
        intent_description=alert_input,
        target=None,
        needs_fix=False,
        changes=[BaselineToolRecord.model_validate(record) for record in changes],
        verify=VerifyResult(
            passed=False,
            evidence=[],
            remaining_issues=[reason],
            missing_info=["The single-node run did not produce a valid final JSON result."],
        ),
        final_summary=reason,
        tool_records=[BaselineToolRecord.model_validate(record) for record in tool_records],
        reasoning_trace=["Single-node run ended before a valid final JSON object was produced."],
        residual_risk=[reason],
    )
    return result.model_dump(mode="json")


def _message_to_record(message: Any) -> dict[str, Any]:
    if isinstance(message, HumanMessage):
        return {"type": "human", "content": message.content}
    if isinstance(message, SystemMessage):
        return {"type": "system", "content": message.content}
    if isinstance(message, ToolMessage):
        return {
            "type": "tool",
            "name": getattr(message, "name", None),
            "tool_call_id": getattr(message, "tool_call_id", None),
            "content": message.content,
        }
    if isinstance(message, AIMessage):
        return {
            "type": "ai",
            "content": message.content,
            "tool_calls": _jsonable(getattr(message, "tool_calls", None) or []),
        }
    return {"type": type(message).__name__, "content": str(message)}


def _message_window(messages: list[Any], limit: int = 6) -> list[dict[str, Any]]:
    return [_message_to_record(message) for message in messages[-limit:]]


def _is_remediation_tool(tool_name: str) -> bool:
    return tool_name.startswith("rem_") or tool_name in {
        "set_interface_state",
        "configure_interface",
        "remove_interface",
        "set_interface_description",
    }


def _extract_tool_records(messages: list[Any]) -> list[dict[str, Any]]:
    calls_by_id: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    saw_remediation = False

    for message in messages:
        if isinstance(message, AIMessage):
            for call in getattr(message, "tool_calls", None) or []:
                call_id = call.get("id") or call.get("tool_call_id")
                if not call_id:
                    continue
                calls_by_id[call_id] = {
                    "tool": call.get("name") or call.get("tool") or "",
                    "args": call.get("args") or {},
                }

        if isinstance(message, ToolMessage):
            call_id = getattr(message, "tool_call_id", None)
            meta = calls_by_id.get(call_id, {})
            tool = meta.get("tool") or getattr(message, "name", None) or "unknown"
            if _is_remediation_tool(tool):
                phase: Literal["information", "remediation", "verification", "unknown"] = "remediation"
                saw_remediation = True
            elif saw_remediation:
                phase = "verification"
            else:
                phase = "information"
            records.append(
                {
                    "phase": phase,
                    "tool": tool,
                    "args": meta.get("args") or {},
                    "result": message.content,
                }
            )

    return records


async def _execute_tool_call(tool_by_name: dict[str, Any], call: dict[str, Any]) -> ToolMessage:
    tool_name = call.get("name") or call.get("tool") or ""
    tool_call_id = call.get("id") or call.get("tool_call_id") or tool_name
    args = call.get("args") or {}
    tool = tool_by_name.get(tool_name)

    if tool is None:
        result: Any = {"status": "error", "message": f"Unknown tool: {tool_name}"}
    else:
        try:
            result = await tool.ainvoke(args)
        except Exception as exc:
            result = {"status": "error", "message": repr(exc)}

    return ToolMessage(
        content=json.dumps(_jsonable(result), ensure_ascii=False),
        name=tool_name,
        tool_call_id=tool_call_id,
    )


# This is the core single-node agent logic. It runs a loop of LLM reasoning and tool calls until the LLM stops calling tools or the max round limit is reached.
# Each later LLM invocation has more evidence than the previous one
async def single_shot_node(
    state: AgentState,
    llm_with_tools: Any,
    tools: list[Any],
    max_tool_rounds: int,
) -> dict:
    alert_input = (state.get("user_input") or "").strip()
    router_mapping = {router_id: router.name for router_id, router in ROUTERS.items()}
    tool_names = [getattr(tool, "name", "") for tool in tools]
    tool_by_name = {getattr(tool, "name", ""): tool for tool in tools}

    ctx = {
        "alert_input": alert_input,
        "router_mapping": router_mapping,
        "available_tools": tool_names,
        "max_tool_rounds": max_tool_rounds,
    }
    log_node_enter("simple_baseline", ctx)

    messages: list[Any] = [
        SystemMessage(content=SYSTEM),
        HumanMessage(
            content=json.dumps(
                {
                    "alert_input": alert_input,
                    "router_mapping": router_mapping,
                    "available_tools": tool_names,
                },
                ensure_ascii=False,
            )
        ),
    ]

    for round_idx in range(max_tool_rounds):
        log_node_enter(
            "simple_baseline_llm_round",
            {
                "round": round_idx + 1,
                "max_tool_rounds": max_tool_rounds,
                "message_count_before": len(messages),
                "tool_records_so_far": _extract_tool_records(messages),
                "recent_messages": _message_window(messages),
            },
        )

        ai = await llm_with_tools.ainvoke(messages)
        messages.append(ai)  # Add the AI message before processing tool calls.
        tool_calls = getattr(ai, "tool_calls", None) or []

        log_node_exit(
            "simple_baseline_llm_round",
            {
                "round": round_idx + 1,
                "message_count_after": len(messages),
                "ai_message": _message_to_record(ai),
                "tool_call_count": len(tool_calls),
            },
        )

        if not tool_calls:
            break

        for call in tool_calls:
            log_node_enter(
                "simple_baseline_tool_call",
                {
                    "round": round_idx + 1,
                    "call": _jsonable(call),
                    "message_count_before": len(messages),
                },
            )
            tool_message = await _execute_tool_call(tool_by_name, call)
            messages.append(tool_message)
            log_node_exit(
                "simple_baseline_tool_call",
                {
                    "round": round_idx + 1,
                    "tool_message": _message_to_record(tool_message),
                    "message_count_after": len(messages),
                },
            )

    tool_records = _extract_tool_records(messages)
    changes = [record for record in tool_records if record.get("phase") == "remediation"]

    final_ai = messages[-1] if messages and isinstance(messages[-1], AIMessage) else None
    if final_ai is None or (getattr(final_ai, "tool_calls", None) or []):
        result = _fallback_result(
            alert_input,
            tool_records,
            "The model used the full tool budget before returning final JSON.",
        )
    else:
        try:
            result = _extract_json_object(final_ai.content)
        except Exception as exc:
            result = _fallback_result(
                alert_input,
                tool_records,
                f"The model returned invalid final JSON: {exc}",
            )

    result["tool_records"] = tool_records
    result["changes"] = changes
    result["raw_transcript"] = [_message_to_record(message) for message in messages]

    patch = {
        "messages": [AIMessage(content=json.dumps(result, ensure_ascii=False, indent=2))],
        "intent": result.get("intent"),
        "intent_description": result.get("intent_description"),
        "target": result.get("target"),
        "observations": tool_records,
        "diagnosis": result.get("diagnosis"),
        "needs_fix": result.get("needs_fix"),
        "plan": result.get("plan"),
        "changes": changes,
        "verify": result.get("verify"),
        "phase": "verified",
        "remediation_done": True,
    }
    log_node_exit("simple_baseline", {**patch, "structured_result": result})
    return patch


def build_app(llm_with_tools: Any, tools: list[Any], max_tool_rounds: int):
    graph = StateGraph(AgentState)

    async def run_simple_baseline(state: AgentState) -> dict:
        return await single_shot_node(state, llm_with_tools, tools, max_tool_rounds)

    graph.add_node("simple_baseline", run_simple_baseline)
    graph.add_edge(START, "simple_baseline")
    graph.add_edge("simple_baseline", END)
    return graph.compile(checkpointer=MemorySaver())


async def _load_tools(mcp_url: str) -> list[Any]:
    client = MultiServerMCPClient(
        {
            "AI_MCP_Router": {
                "transport": "streamable_http",
                "url": mcp_url,
            },
        }
    )
    return await client.get_tools()


def _read_alert_input(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return ""

    try:
        return json.dumps(json.loads(raw), ensure_ascii=False)
    except json.JSONDecodeError:
        return raw


def _write_result(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the single-node baseline network agent.")
    parser.add_argument(
        "--alerts",
        default=str(DEFAULT_ALERTS),
        help="Path to the alert JSON file used as agent input.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path for structured JSON output.")
    parser.add_argument("--model", default="gpt-5-mini", help="OpenAI chat model to use.")
    parser.add_argument("--mcp-url", default=DEFAULT_MCP_URL, help="MCP streamable HTTP URL.")
    parser.add_argument("--max-tool-rounds", type=int, default=8, help="Maximum internal tool loops.")
    args = parser.parse_args()

    alert_input = _read_alert_input(Path(args.alerts))
    if not alert_input:
        print(f"No alert input found in {args.alerts}.")
        return

    try:
        tools = await _load_tools(args.mcp_url)
    except Exception as exc:
        print(f"Could not connect to MCP: {exc}")
        return

    print("TOOLS:", len(tools))
    print([getattr(tool, "name", None) for tool in tools])

    base = ChatOpenAI(model=args.model, temperature=0)
    llm_with_tools = base.bind_tools(tools)
    app = build_app(llm_with_tools, tools, args.max_tool_rounds)

    state = await app.ainvoke(
        {"user_input": alert_input},
        config={"configurable": {"thread_id": f"simple-baseline-{int(datetime.now().timestamp())}"}},
    )
    result = json.loads(state["messages"][-1].content)
    result["metadata"] = {
        "mode": "single_node_baseline",
        "model": args.model,
        "mcp_url": args.mcp_url,
        "alerts_file": str(Path(args.alerts)),
        "max_tool_rounds": args.max_tool_rounds,
        "generated_at": _now_iso(),
    }

    output_path = Path(args.output)
    _write_result(output_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\nWrote structured result to {output_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")
