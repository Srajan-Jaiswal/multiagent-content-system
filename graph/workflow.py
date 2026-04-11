from langgraph.graph import StateGraph, END

from agents import research, seo, strategy, writer
from graph.state import ContentState


def build_graph():
    graph = StateGraph(ContentState)

    graph.add_node("research", research.run)
    graph.add_node("seo", seo.run)
    graph.add_node("strategy", strategy.run)
    graph.add_node("writer", writer.run)

    graph.set_entry_point("research")
    graph.add_edge("research", "seo")
    graph.add_edge("seo", "strategy")
    graph.add_edge("strategy", "writer")
    graph.add_edge("writer", END)

    return graph.compile()


pipeline = build_graph()