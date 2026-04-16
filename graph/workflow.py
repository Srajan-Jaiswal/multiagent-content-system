from langgraph.graph import StateGraph, END, START

from agents import research, seo, strategy, writer
from graph.state import ContentState


def build_graph():
    graph = StateGraph(ContentState)

    # ── Nodes ─────────────────────────────────────────────────────────────── #
    graph.add_node("research", research.run)
    graph.add_node("seo", seo.run)
    graph.add_node("strategy", strategy.run)
    graph.add_node("writer", writer.run)

    # ── Edges ─────────────────────────────────────────────────────────────── #

    # Fan out: research and seo start in parallel from START
    graph.add_edge(START, "research")
    graph.add_edge(START, "seo")

    # Fan in: strategy waits for BOTH research and seo to complete
    graph.add_edge("research", "strategy")
    graph.add_edge("seo", "strategy")

    # Sequential: strategy → writer → END
    graph.add_edge("strategy", "writer")
    graph.add_edge("writer", END)

    return graph.compile()


pipeline = build_graph()