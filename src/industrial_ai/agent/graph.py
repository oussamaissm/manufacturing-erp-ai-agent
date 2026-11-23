from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from ..config import Settings
from ..erp.client import ERPNextClient
from ..erp.service import ERPService
from .prompts import SYSTEM_PROMPT
from .tools import build_tools


def build_graph(llm, tools, checkpointer=None):
    llm_with_tools = llm.bind_tools(tools)

    def call_model(state: MessagesState) -> dict:
        system = SystemMessage(SYSTEM_PROMPT.format(today=date.today().isoformat()))
        return {"messages": [llm_with_tools.invoke([system, *state["messages"]])]}

    def route(state: MessagesState) -> str:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    g = StateGraph(MessagesState)
    g.add_node("agent", call_model)
    g.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, {"tools": "tools", END: END})
    g.add_edge("tools", "agent")
    return g.compile(checkpointer=checkpointer or MemorySaver())


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[dict] = field(default_factory=list)
    elapsed_s: float = 0.0


class Agent:
    """Convenience wrapper: ask(question, thread_id) -> AgentResult."""

    def __init__(self, llm, tools, recursion_limit: int = 14, checkpointer=None) -> None:
        self.graph = build_graph(llm, tools, checkpointer)
        self.recursion_limit = recursion_limit

    def ask(self, message: str, thread_id: str = "default") -> AgentResult:
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": self.recursion_limit}
        t0 = time.perf_counter()
        try:
            out = self.graph.invoke({"messages": [HumanMessage(message)]}, config)
        except GraphRecursionError:
            return AgentResult(
                "I got stuck calling tools in a loop and stopped. Try rephrasing or being more specific.",
                [], time.perf_counter() - t0,
            )
        msgs = out["messages"]
        last_human = max(i for i, m in enumerate(msgs) if isinstance(m, HumanMessage))
        turn = msgs[last_human + 1:]
        results = {m.tool_call_id: m.content for m in turn if isinstance(m, ToolMessage)}
        calls = [
            {"name": c["name"], "args": c["args"], "result_preview": str(results.get(c["id"], ""))[:300],
             "result": str(results.get(c["id"], ""))}
            for m in turn if isinstance(m, AIMessage) for c in (m.tool_calls or [])
        ]
        final = next((m for m in reversed(turn) if isinstance(m, AIMessage) and not m.tool_calls), None)
        return AgentResult(_text(final.content) if final else "", calls, time.perf_counter() - t0)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)


def build_default_agent(settings: Settings | None = None, *, with_rag: bool = True, retriever=None) -> Agent:
    """Wire everything for real use: ERPNext + Ollama (+ RAG over data/docs)."""
    s = settings or Settings.from_env()
    erp = ERPService(ERPNextClient.from_settings(s))
    if retriever is None and with_rag:
        from ..rag.retriever import build_default_retriever
        retriever = build_default_retriever(s)
    if s.llm_provider == "groq":
        from langchain_groq import ChatGroq
        llm = ChatGroq(model=s.llm_model, api_key=s.groq_api_key, temperature=0)
    elif s.llm_provider == "llamacpp":
        # llama-server speaks the OpenAI API; it serves one model, so the name is only a label
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=s.llm_model, base_url=s.llamacpp_base_url, api_key="not-needed", temperature=0)
    else:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model=s.llm_model, base_url=s.ollama_host, temperature=0)
    return Agent(llm, build_tools(erp, retriever), recursion_limit=s.recursion_limit)
