"""LangGraph agent for context synthesis.

Defines a StateGraph that gathers data from multiple sources
(Slack, Notion, Linear) and synthesizes a unified context page.
"""

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class ContextState(TypedDict):
    """State passed between nodes in the context synthesis graph."""

    ticket_id: str
    slack_data: list[dict[str, Any]]
    notion_data: list[dict[str, Any]]
    linear_data: list[dict[str, Any]]
    synthesized_context: str
    errors: list[str]


async def gather_slack(state: ContextState) -> ContextState:
    """Gather relevant Slack threads and messages for the ticket.

    Args:
        state: The current graph state containing the ticket ID.

    Returns:
        Updated state with Slack data populated.
    """
    # TODO: implement — use Slack ingestion to fetch relevant threads
    state["slack_data"] = []
    return state


async def gather_notion(state: ContextState) -> ContextState:
    """Gather relevant Notion documents for the ticket.

    Args:
        state: The current graph state containing the ticket ID.

    Returns:
        Updated state with Notion data populated.
    """
    # TODO: implement — use Notion ingestion to fetch relevant pages
    state["notion_data"] = []
    return state


async def gather_linear(state: ContextState) -> ContextState:
    """Gather Linear issue details, comments, and activity for the ticket.

    Args:
        state: The current graph state containing the ticket ID.

    Returns:
        Updated state with Linear data populated.
    """
    # TODO: implement — use Linear ingestion to fetch issue details
    state["linear_data"] = []
    return state


async def synthesize(state: ContextState) -> ContextState:
    """Synthesize gathered data into a unified context page using Claude.

    Args:
        state: The current graph state with all gathered source data.

    Returns:
        Updated state with the synthesized context string.
    """
    # TODO: implement — call Anthropic Claude to synthesize context
    state["synthesized_context"] = ""
    return state


def build_context_graph() -> StateGraph:
    """Build and compile the context synthesis LangGraph.

    The graph runs gather nodes in parallel, then synthesizes results.

    Returns:
        A compiled StateGraph ready for invocation.
    """
    graph = StateGraph(ContextState)

    # Add nodes
    graph.add_node("gather_slack", gather_slack)
    graph.add_node("gather_notion", gather_notion)
    graph.add_node("gather_linear", gather_linear)
    graph.add_node("synthesize", synthesize)

    # Define edges: gather nodes run from START, then converge on synthesize
    graph.set_entry_point("gather_slack")

    graph.add_edge("gather_slack", "gather_notion")
    graph.add_edge("gather_notion", "gather_linear")
    graph.add_edge("gather_linear", "synthesize")
    graph.add_edge("synthesize", END)

    return graph


# Compiled graph instance ready for use
context_graph = build_context_graph().compile()
