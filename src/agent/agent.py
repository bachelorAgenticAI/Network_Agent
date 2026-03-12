"""Build and run the LangGraph workflow for monitoring, diagnosis, remediation, and summary."""

import asyncio

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from agent.monitoring.compare_state import compare
from agent.nodes.assess_verify import assess_verify_node
from agent.nodes.collect_changes import collect_changes_node
from agent.nodes.diagnose import diagnose_node
from agent.nodes.format_network import format_network_node
from agent.nodes.get_info import get_info_node
from agent.nodes.ingestion import ingestion
from agent.nodes.intent import intent_node
from agent.nodes.remediation import remediation_node
from agent.nodes.summary import summary_node
from agent.nodes.verify import verify_node
from agent.state.types import AgentState
from agent.utils.extract_logs import write_extracted_logs
from agent.utils.logger import log_node_enter, log_node_exit

load_dotenv()


# Main controller: choose the next phase based on diagnosis + verification status.
def _route_from_controller(state: AgentState) -> str:
    v = state.get("verify") or {}
    # Only retry after verification failure if we're past initial phase
    if state.get("phase") != "start" and v.get("passed") is False:
        if int(state.get("attempts", 0)) >= 2:  # set value for retry limit
            return "summary"
        return "get_info"

    if state.get("phase") == "start":
        return "get_info"

    d = state.get("diagnosis")  # Can be None before diagnose node runs.
    if d is None:
        return "diagnose"
    if state.get("needs_fix") is True:
        return "remediation"

    if state.get("needs_fix") is False:
        return "summary"

    return "summary"


# After assess_verify: either finish or loop back for another attempt.
def _after_verify_assess(state: AgentState) -> str:
    v = state.get("verify") or {}
    if v.get("passed") is True:
        return "summary"
    if int(state.get("attempts", 0)) >= 2:  # set value for retry limit 2=3 rounds
        return "summary"
    return "intent"


# Continue remediation until all planned steps are executed.
def _after_collect_changes(state: AgentState) -> str:
    if state.get("remediation_done") is True:
        return "verify"
    return "remediation"


# Track how many remediation/verification loops have been attempted.
# After x attempts, give up and move to summary to avoid infinite loops on hard problems.
def _inc_attempts(state: AgentState) -> dict:
    attempts = state.get("attempts")
    if attempts is None:
        attempts = 0

    attempts += 1
    return {"attempts": attempts}


# Clear derived state so the next pass starts from fresh evidence.
def _reset_for_retry(state: AgentState) -> dict:
    return {
        "diagnosis": None,
        "needs_fix": None,
        "plan": {},
        "phase": "start",
        "verify": {},  # reset verify to avoid infinite loop
        "remediation_step_idx": 0,
        "remediation_done": False,
        "info_start_cursor": 0,
        "verify_start_cursor": 0,
    }


def build_app(
    llm_intent,
    llm_info,
    llm_remediate,
    llm_verify,
    tools_info_node,
    tools_remediate_node,
    tools_verify_node,
):
    # Build the state machine: info path -> diagnose -> (optional) fix -> verify -> summary.
    graph = StateGraph(AgentState)
    # Define each node, either as a simple function or a LangGraph node with tool access.
    graph.add_node("ingestion", ingestion)
    graph.add_node("intent", lambda s: intent_node(s, llm_intent))
    graph.add_node("get_info", lambda s: get_info_node(s, llm_info))
    graph.add_node("format_network", lambda s: format_network_node(s, llm_info))
    graph.add_node("diagnose", lambda s: diagnose_node(s, llm_info))
    graph.add_node("remediation", lambda s: remediation_node(s, llm_remediate))
    graph.add_node("collect_changes", collect_changes_node)
    graph.add_node("verify", lambda s: verify_node(s, llm_verify))
    graph.add_node("assess_verify", lambda s: assess_verify_node(s, llm_verify))
    graph.add_node("summary", lambda s: summary_node(s, llm_verify))

    graph.add_node("tools_info", tools_info_node)
    graph.add_node("tools_remediate", tools_remediate_node)
    graph.add_node("tools_verify", tools_verify_node)

    graph.add_node("inc_attempts", _inc_attempts)
    graph.add_node("reset_for_retry", _reset_for_retry)

    # Define edges between nodes, including conditional edges based on state.
    # The main controller node ("intent") routes to different phases based on current state (diagnosis, verification results, etc).
    graph.add_edge(START, "ingestion")
    graph.add_edge("ingestion", "intent")

    graph.add_conditional_edges(
        "intent",
        _route_from_controller,
        {
            "get_info": "get_info",
            "diagnose": "diagnose",
            "remediation": "remediation",
            "summary": "summary",
        },
    )

    # Info collection path.
    graph.add_edge("get_info", "tools_info")
    graph.add_edge("tools_info", "format_network")
    graph.add_edge("format_network", "diagnose")
    graph.add_edge("diagnose", "intent")

    # Remediation and verification path.
    graph.add_edge("remediation", "tools_remediate")
    graph.add_edge("tools_remediate", "collect_changes")
    graph.add_conditional_edges(
        "collect_changes",
        _after_collect_changes,
        {
            "remediation": "remediation",
            "verify": "verify",
        },
    )
    graph.add_edge("verify", "tools_verify")
    graph.add_edge("tools_verify", "assess_verify")
    # After verification, either loop back to intent for another round or finish with summary.
    graph.add_conditional_edges(
        "assess_verify",
        _after_verify_assess,
        {
            "summary": "summary",
            "intent": "inc_attempts",
        },
    )
    graph.add_edge("inc_attempts", "reset_for_retry")
    graph.add_edge("reset_for_retry", "intent")

    graph.add_edge("summary", END)
    return graph.compile(checkpointer=MemorySaver())


# Run the agent loop: monitor for alerts, then run the workflow for each alert.
# Runs asynchronously to allow for sleeping between monitoring cycles and to handle async tool calls.
async def main():

    try:
        client = MultiServerMCPClient(
            {
                "AI_MCP_Router": {
                    "transport": "streamable_http",
                    "url": "http://127.0.0.1:8000/mcp",
                },
            }
        )

        tools_all = await client.get_tools()
        print("TOOLS:", len(tools_all))
        print([getattr(t, "name", None) for t in tools_all])
    except Exception:
        print("Could not connect to MCP")
        return

    # Binds one shared tool set to all phases. For simplicity, using same LLM for all nodes'.
    tools_intent = tools_all
    tools_info = tools_all
    tools_remediate = tools_all
    tools_verify = tools_all

    base = ChatOpenAI(
        model="gpt-5-mini", temperature=0
    )  # Choice of model and temperature should be tuned based on needs of each node.
    llm_intent = base.bind_tools(tools_intent)
    llm_info = base.bind_tools(tools_info)
    llm_remediate = base.bind_tools(tools_remediate)
    llm_verify = base.bind_tools(tools_verify)

    tools_info_node = ToolNode(tools_info)
    tools_remediate_node = ToolNode(tools_remediate)
    tools_verify_node = ToolNode(tools_verify)

    app = build_app(
        llm_intent,
        llm_info,
        llm_remediate,
        llm_verify,
        tools_info_node,
        tools_remediate_node,
        tools_verify_node,
    )
    # The monitoring loop runs indefinitely, checking for new alerts in a set time. When an alert is detected, it triggers the workflow with the alert as input.
    config = {"configurable": {"thread_id": "monitor-driven"}}
    thread_id = 0

    while True:
        try:
            print("\n[Monitoring] Running check...")

            alerts = await compare()

            if alerts:
                thread_id += 1
                config["configurable"]["thread_id"] = f"alert-{thread_id}"
                log_node_enter(
                    "monitor_loop",
                    {"thread_id": config["configurable"]["thread_id"], "alerts": alerts},
                )
                # Main agent invocation with the detected alert as input.
                state = await app.ainvoke({"user_input": str(alerts)}, config=config)
                log_node_exit(
                    "monitor_loop",
                    {
                        "thread_id": config["configurable"]["thread_id"],
                        "last_message": (
                            state.get("messages", [])[-1].content if state.get("messages") else None
                        ),
                    },
                )
                print(state["messages"][-1].content)
                try:
                    # Produce simplified run metrics after every completed incident.
                    write_extracted_logs()
                except Exception as extract_err:
                    print(f"Extract logs failed: {extract_err}")

            # Sleep between monitoring cycles to avoid excessive resource use.
            await asyncio.sleep(10)

        except KeyboardInterrupt:
            break

        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(300)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")
