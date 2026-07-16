"""Сборка LangGraph-графа диалога.

guardrail -> extract_facts -> check_completeness -> (ask_clarification | classify_stage)
classify_stage -> retrieve_content -> compose_response -> END
"""

from langgraph.graph import END, StateGraph

from app.ai.llm import LLMClient
from app.ai.nodes import GraphState, make_nodes
from app.ai.rag import Retriever


def build_graph(llm: LLMClient, retriever: Retriever):
    nodes = make_nodes(llm, retriever)

    graph = StateGraph(GraphState)
    for name, fn in nodes.items():
        graph.add_node(name, fn)

    graph.set_entry_point("guardrail")
    graph.add_conditional_edges(
        "guardrail",
        lambda s: "refused" if s.get("refusal_key") else "ok",
        {"refused": END, "ok": "extract_facts"},
    )
    graph.add_edge("extract_facts", "check_completeness")
    graph.add_conditional_edges(
        "check_completeness",
        lambda s: "incomplete" if s.get("next_question") else "complete",
        {"incomplete": "ask_clarification", "complete": "classify_stage"},
    )
    graph.add_edge("ask_clarification", END)
    graph.add_edge("classify_stage", "retrieve_content")
    graph.add_edge("retrieve_content", "compose_response")
    graph.add_edge("compose_response", END)

    return graph.compile()
