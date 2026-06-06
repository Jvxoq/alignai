from langgraph.graph import END, START, StateGraph

from app.graph.edges import check_relevance, should_retrieve
from app.graph.state import AgentState
from app.nodes.fallback_node import fallback_node
from app.nodes.generator_node import generator_node
from app.nodes.intent_node import intent_node
from app.nodes.retriever_node import retriever_node
from app.nodes.rewrite_objective_node import rewrite_objective_node


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("intent", intent_node)
    graph.add_node("retrieve", retriever_node)
    graph.add_node("generate", generator_node)
    graph.add_node("rewrite_objective", rewrite_objective_node)
    graph.add_node("fallback", fallback_node)

    graph.add_edge(START, "intent")
    graph.add_conditional_edges("intent", should_retrieve, {"retrieve": "retrieve", "generate": "generate"})
    graph.add_conditional_edges(
        "retrieve",
        check_relevance,
        {"generate": "generate", "rewrite_objective": "rewrite_objective", "fallback": "fallback"},
    )
    graph.add_edge("rewrite_objective", "retrieve")
    graph.add_edge("generate", END)
    graph.add_edge("fallback", END)

    return graph


graph = build_graph().compile()
