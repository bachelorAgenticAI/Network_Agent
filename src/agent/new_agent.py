import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from state.types import AgentState
from nodes.ingestion import ingestion
from nodes.intent import intent_node          # fungerer som "controller"
from nodes.get_info import get_info_node
from nodes.diagnose import diagnose_node
from nodes.remediation import remediation_node
from nodes.verify import verify_node
from nodes.summary import summary_node

load_dotenv()

def _wants_fix(intent: str | None) -> bool:
    # anbefalt: intent_node setter "check" eller "check_and_fix"
    return intent in {"check_and_fix", "fix"}

def _route_from_controller(state: AgentState) -> str:
    """
    Controller (intent_node) har satt intent/target/etc.
    Her ruter vi deterministisk basert på hva som finnes i state.
    """
    # verify-feil kan trigge ny runde uten ny user_input
    v = state.get("verify") or {}
    if v.get("passed") is False:
        # loop-sikring
        if int(state.get("attempts", 0)) >= 3:
            return "summary"
        return "get_info"

    if not state.get("observations"):
        return "get_info"
    if not state.get("diagnosis"):
        return "diagnose"

    # Har diagnose
    if state.get("needs_fix") is False:
        return "summary"

    # needs_fix=True
    if _wants_fix(state.get("intent")):
        # hvis du vil kreve godkjenning: bruk approved-gate her
        if state.get("approved") is False:
            return "summary"
        return "remediation"

    return "summary"

def _after_verify(state: AgentState) -> str:
    v = state.get("verify") or {}
    if v.get("passed") is True:
        return "summary"
    # verify fail -> intent for new round (reset state for diagnose/plan)
    if int(state.get("attempts", 0)) >= 3:
        return "summary"
    return "intent"

def _inc_attempts(state: AgentState) -> dict:
    return {"attempts": int(state.get("attempts", 0)) + 1}

def _reset_for_retry(state: AgentState) -> dict:
    """
    Ved verify-feil: fjern diagnose/needs_fix/plan slik at vi tvinger ny feilsøking.
    Beholder observations-historikk og messages.
    """
    return {
        "diagnosis": {},
        "needs_fix": True,   # ukjent/antatt feil når verify feiler
        "plan": {},
        # endringer beholdes (changes) så du kan rapportere hva som ble forsøkt
    }

def build_app(
    llm_intent, llm_info, llm_remediate, llm_verify,
    tools_info_node, tools_remediate_node, tools_verify_node,
):
    graph = StateGraph(AgentState)

    # Nodes (LLM)
    graph.add_node("ingestion", ingestion)

    # "intent" = controller node (LLM tolker brukerprompt og setter intent/target/approved)
    graph.add_node("intent", lambda s: intent_node(s, llm_intent))

    graph.add_node("get_info", lambda s: get_info_node(s, llm_info))
    graph.add_node("diagnose", lambda s: diagnose_node(s, llm_info))
    graph.add_node("remediation", lambda s: remediation_node(s, llm_remediate))
    graph.add_node("verify", lambda s: verify_node(s, llm_verify))
    graph.add_node("summary", lambda s: summary_node(s, llm_verify))

    # Tool nodes (scoped)
    graph.add_node("tools_info", tools_info_node)
    graph.add_node("tools_remediate", tools_remediate_node)
    graph.add_node("tools_verify", tools_verify_node)

    # Retry helpers
    graph.add_node("inc_attempts", _inc_attempts)
    graph.add_node("reset_for_retry", _reset_for_retry)

    # Wiring
    graph.add_edge(START, "ingestion")
    graph.add_edge("ingestion", "intent")

    # Controller -> next step basert på state
    graph.add_conditional_edges("intent", _route_from_controller, {
        "get_info": "get_info",
        "diagnose": "diagnose",
        "remediation": "remediation",
        "summary": "summary",
    })

    # get_info -> tools -> diagnose -> tilbake til controller (for å velge videre)
    graph.add_edge("get_info", "tools_info")
    graph.add_edge("tools_info", "diagnose")
    graph.add_edge("diagnose", "intent")

    # remediation -> tools -> verify -> tools -> route
    graph.add_edge("remediation", "tools_remediate")
    graph.add_edge("tools_remediate", "verify")
    graph.add_edge("verify", "tools_verify")

    # Etter verify-tools: ved feil -> reset/attempts -> controller; ved pass -> summary
    graph.add_conditional_edges("tools_verify", _after_verify, {
        "summary": "summary",
        "intent": "inc_attempts",
    })
    graph.add_edge("inc_attempts", "reset_for_retry")
    graph.add_edge("reset_for_retry", "intent")

    graph.add_edge("summary", END)
    return graph.compile(checkpointer=MemorySaver())

async def main():
    client = MultiServerMCPClient({
        "mcp_intent":     {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp/intent"},
        "mcp_info":       {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp/info"},
        "mcp_remediate":  {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp/remediate"},
        "mcp_verify":     {"transport": "streamable_http", "url": "http://127.0.0.1:8000/mcp/verify"},
    })

    # NB: hvis adapteren din ikke støtter server_name, lag én client per URL i stedet.
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

    config = {"configurable": {"thread_id": "chat-1"}}

    while True:
        txt = input("> ").strip()
        if txt.lower() in {"exit", "quit"}:
            break
        state = await app.ainvoke({"user_input": txt}, config=config)
        print(state["messages"][-1].content)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stoppet av bruker")
