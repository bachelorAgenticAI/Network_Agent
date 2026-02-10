import asyncio
import json
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from utils.json_logger import dump_messages, log_event
from utils.sanitize_message import sanitize_messages

load_dotenv()

PROMPT = """You are a helpful network AI assistant. 
You get tools from a mcp server.
You are only allowed to use these tools.
"""

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_input: str

def ingestion(state: AgentState) -> dict:
    log_event("ingestion", "enter", {"state": state})

    user_text = state.get("user_input", "").strip()
    if not user_text:
        return {}

    new_messages: list[BaseMessage] = []

    if not state.get("messages"):
        new_messages.append(SystemMessage(content=PROMPT))
    else:
         repaired = sanitize_messages(state["messages"])
         if len(repaired) > len(state["messages"]):
            new_messages.extend(
                repaired[len(state["messages"]):]
            )

    new_messages.append(HumanMessage(content=user_text))

    result = {"messages": new_messages}

    log_event(
        "ingestion",
        "exit",
        {"messages": dump_messages(new_messages)}
    )

    return result

def build_graph(llm, tools):
    async def agent(state: AgentState) -> dict:
        log_event(
            "llm",
            "enter",
            {"messages": dump_messages(state["messages"])}
        )
        try:
            response = await llm.ainvoke(state["messages"])
        except Exception as e:
            log_event("llm", "error", {"error": str(e)})
            if "tool_calls must be followed" in str(e):
                repaired = sanitize_messages(state["messages"])
                response = await llm.ainvoke(repaired)
                return {"messages": [response]}
            raise
        log_event(
            "llm",
            "exit",
            {"response": dump_messages([response])}
        )

        return {"messages": [response]}

    tool_node = ToolNode(tools)
    async def tools_wrapper(state: AgentState):
        log_event(
            "tools",
            "enter",
            {"messages": dump_messages(state["messages"])}
        )
        try:
            result = await tool_node.ainvoke(state)
        except Exception as e:
            log_event("tools", "error", {"error": str(e)})


            last_msg = state["messages"][-1]
            tool_calls = getattr(last_msg, "tool_calls", None) or []
            tool_responses = []
            for tc in tool_calls:
                tool_responses.append(
                    ToolMessage(
                        tool_call_id=tc["id"],
                        content=json.dumps(
                            {
                                "error": "tool_execution_failed",
                                "tool": tc.get("name"),
                                "message": str(e),
                            }
                        ),
                    )
                )
            return {"messages": tool_responses}

        log_event(
            "tools",
            "exit",
            {"messages": dump_messages(result["messages"])}
        )

        return result

    graph = StateGraph(AgentState)
    graph.add_node("ingestion", ingestion)
    graph.add_node("llm", agent)
    graph.add_node("tools", tools_wrapper)

    graph.add_edge(START, "ingestion")
    graph.add_edge("ingestion", "llm")

    # Hvis LLM ber om verktøy -> tools, ellers -> END
    graph.add_conditional_edges("llm", tools_condition, {"tools": "tools", "__end__": END})

    # Etter tools-kjøring, tilbake til llm for å fortsette
    graph.add_edge("tools", "llm")

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)

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

        tools = await client.get_tools()

    except Exception as e:
        log_event("mcp", "error", {"error": str(e)})
        print("Kunne ikke hente tools fra MCP")
        return

    llm = ChatOpenAI(model="gpt-5-mini", temperature=0).bind_tools(tools)
    app = build_graph(llm, tools)

    config = {"configurable": {"thread_id": "chat-1"}}

    while True:
        user_text = input("> ").strip()
        if user_text.lower() in {"exit", "quit"}:
            break
        try:
            state = await app.ainvoke({"user_input": user_text}, config=config)
        except Exception as e:
            log_event("graph", "error", {"error": str(e)})
            print("Graf-feil. Se logger.")
            continue

        log_event(
            "graph",
            "final_state",
            {"messages": dump_messages(state["messages"])}
        )

        # Siste AIMessage etter eventuelle tool-runder
        last = state["messages"][-1]
        if isinstance(last, AIMessage):
            print("Assistant:", last.content)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server stoppet av bruker")
