from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

PROMPT = """You are a helpful AI assistant. Answer the user's questions based on the provided context."""

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_input: str

llm = ChatOpenAI(model="gpt-5-mini", temperature=0, prompt=PROMPT)

def ingestion(state: AgentState) -> dict:
    user_text = state.get("user_input", "")
    if not user_text:
        return {}
    return {"messages": [HumanMessage(content=user_text)]}

def agent(state: AgentState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}

graph = StateGraph(AgentState)
graph.add_node("ingestion", ingestion)
graph.add_node("llm", agent)
graph.add_edge(START, "ingestion")
graph.add_edge("ingestion", "llm")
graph.add_edge("llm", END)

# ceckpointing previous conversations in memory
checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "chat-1"}}

while True:
    user_text = input("> ").strip()
    if user_text.lower() in {"exit", "quit"}:
        break

    state = app.invoke({"user_input": user_text}, config=config)
    last = state["messages"][-1]
    if isinstance(last, AIMessage):
        print("Assistant:", last.content)