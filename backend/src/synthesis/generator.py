"""Context page generator using Anthropic Claude.

Takes gathered data from multiple sources and synthesizes a structured
context page that gives developers the full picture of a ticket.
"""

from typing import Any

from pydantic import BaseModel


class ContextPageData(BaseModel):
    """Structured output of the context page generator."""

    ticket_id: str
    title: str
    summary: str
    key_decisions: list[str]
    open_questions: list[str]
    related_discussions: list[dict[str, Any]]
    technical_context: str
    timeline: list[dict[str, Any]]


class ContextGenerator:
    """Generate context pages by synthesizing data with Claude.

    Uses the Anthropic API to process gathered data from Slack, Notion,
    Linear, and meeting transcripts into a cohesive context page.
    """

    def __init__(self, anthropic_api_key: str) -> None:
        """Initialize the context generator.

        Args:
            anthropic_api_key: The Anthropic API key for Claude access.
        """
        self.api_key = anthropic_api_key
        # TODO: implement — initialize Anthropic client
        # from anthropic import Anthropic
        # self.client = Anthropic(api_key=anthropic_api_key)

    async def generate(
        self,
        ticket_id: str,
        slack_data: list[dict[str, Any]],
        notion_data: list[dict[str, Any]],
        linear_data: list[dict[str, Any]],
        transcript_data: list[dict[str, Any]] | None = None,
    ) -> ContextPageData:
        """Generate a synthesized context page from gathered data.

        Calls Anthropic Claude with all the gathered data to produce
        a structured context page with summary, decisions, questions, etc.

        Args:
            ticket_id: The ticket identifier this context is for.
            slack_data: Gathered Slack messages and threads.
            notion_data: Gathered Notion documents.
            linear_data: Gathered Linear issue data and comments.
            transcript_data: Optional meeting transcript excerpts.

        Returns:
            A structured context page with synthesized information.
        """
        # TODO: implement — build prompt and call Claude API
        _ = slack_data, notion_data, linear_data, transcript_data

        return ContextPageData(
            ticket_id=ticket_id,
            title="",
            summary="",
            key_decisions=[],
            open_questions=[],
            related_discussions=[],
            technical_context="",
            timeline=[],
        )


async def generate_context_page(
    ticket_id: str,
    gathered_data: dict[str, Any],
    anthropic_api_key: str,
) -> ContextPageData:
    """Convenience function to generate a context page.

    Args:
        ticket_id: The ticket identifier.
        gathered_data: Dictionary with keys 'slack', 'notion', 'linear', 'transcripts'.
        anthropic_api_key: The Anthropic API key.

    Returns:
        A structured context page.
    """
    generator = ContextGenerator(anthropic_api_key=anthropic_api_key)
    return await generator.generate(
        ticket_id=ticket_id,
        slack_data=gathered_data.get("slack", []),
        notion_data=gathered_data.get("notion", []),
        linear_data=gathered_data.get("linear", []),
        transcript_data=gathered_data.get("transcripts"),
    )
