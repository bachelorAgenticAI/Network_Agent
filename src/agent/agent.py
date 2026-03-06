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

load_dotenv()


def _wants_fix(intent: str | None) -> bool:
    return intent in {"check_and_fix", "fix"}


def _route_from_controller(state: AgentState) -> str:
    v = state.get("verify") or {}
    # Only retry after verification failure if we're past initial phase
    if state.get("phase") != "start" and v.get("passed") is False:
        if int(state.get("attempts", 0)) >= 2:  # set value for retry limit
            return "summary"
        return "get_info"

    if state.get("phase") == "start":
        return "get_info"
    if not state.get("diagnosis"):
        return "diagnose"

    if state.get("needs_fix") is False:
        return "summary"

    if _wants_fix(state.get("intent")):
        if state.get("approved") is False and (state.get("plan") or {}).get(
            "requires_approval", True
        ):
            return "summary"
        return "remediation"

    return "summary"


def _after_verify_assess(state: AgentState) -> str:
    v = state.get("verify") or {}
    if v.get("passed") is True:
        return "summary"
    if int(state.get("attempts", 0)) >= 5:  # set value for retry limit
        return "summary"
    return "intent"


def _inc_attempts(state: AgentState) -> dict:
    return {"attempts": int(state.get("attempts", 0)) + 1}


def _reset_for_retry(state: AgentState) -> dict:
    return {
        "diagnosis": {},
        "needs_fix": None,
        "plan": {},
        "phase": "start",
        "verify": {},  # Clear verify to avoid stale failure state
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
    graph = StateGraph(AgentState)

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

    # Info path
    graph.add_edge("get_info", "tools_info")
    graph.add_edge("tools_info", "format_network")
    graph.add_edge("format_network", "diagnose")
    graph.add_edge("diagnose", "intent")

    # Remediation + verify path
    graph.add_edge("remediation", "tools_remediate")
    graph.add_edge("tools_remediate", "collect_changes")
    graph.add_edge("collect_changes", "verify")
    graph.add_edge("verify", "tools_verify")
    graph.add_edge("tools_verify", "assess_verify")

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


async def main():
    """
    client = MultiServerMCPClient({
        "mcp_intent":     {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp/intent"},
        "mcp_info":       {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp/info"},
        "mcp_remediate":  {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp/remediate"},
        "mcp_verify":     {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp/verify"},
    })

    tools_intent = await client.get_tools(server_name="mcp_intent")
    tools_info = await client.get_tools(server_name="mcp_info")
    tools_remediate = await client.get_tools(server_name="mcp_remediate")
    tools_verify = await client.get_tools(server_name="mcp_verify")

    base = ChatOpenAI(model="gpt-5-mini", temperature=0)
    llm_intent = base.bind_tools(tools_intent)
    llm_info = base.bind_tools(tools_info)
    llm_remediate = base.bind_tools(tools_remediate)
    llm_verify = base.bind_tools(tools_verify)

    tools_info_node = ToolNode(tools_info)
    tools_remediate_node = ToolNode(tools_remediate)
    tools_verify_node = ToolNode(tools_verify)

    app = build_app(
        llm_intent, llm_info, llm_remediate, llm_verify,
        tools_info_node, tools_remediate_node, tools_verify_node,
    )
    """
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
        print("Kunne ikke hente tools fra MCP")
        return

    # Quick test: samme tools overalt
    tools_intent = tools_all
    tools_info = tools_all
    tools_remediate = tools_all
    tools_verify = tools_all

    base = ChatOpenAI(model="gpt-5-mini", temperature=0)
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

    config = {"configurable": {"thread_id": "monitor-driven"}}
    thread_id = 0

    while True:
        try:
            print("\n[Monitoring] Running check...")

            alerts = await compare()

            if alerts:
                thread_id += 1
                config["configurable"]["thread_id"] = f"alert-{thread_id}"

                state = await app.ainvoke({"user_input": str(alerts)}, config=config)

                print(state["messages"][-1].content)

            # Ensure monitoring never runs more often than every 5 minutes
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
