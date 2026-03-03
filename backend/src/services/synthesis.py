"""Context page synthesis service.

Generates AI-powered context pages for Linear tickets by combining
linked content from multiple sources into a structured document.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.context_page import ContextPage
from src.models.ticket import LinearTicket
from src.services.linking import find_related_content
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """\
You are a context synthesis assistant for engineering teams. Your job is to produce
a structured context page that helps an engineer quickly understand the full story
behind a ticket — decisions made, requirements, related work, and open questions.

Write in clear, concise technical prose. Use markdown formatting. Be factual and
cite sources when referencing specific messages, PRs, or meetings."""

SYNTHESIS_TEMPLATE = """\
## Ticket: {identifier}
**Title:** {title}
**Status:** {status}
**Assignee:** {assignee}
**Priority:** {priority}
**Labels:** {labels}

### Ticket Description
{description}

### Related Content
{related_content}

---

Based on the ticket and all related content above, produce a context page with these sections:

1. **Summary** — 2-3 sentence overview of what this ticket is about and why it matters
2. **Background & Decisions** — Key decisions, discussions, and context from Slack, meetings, and comments
3. **Requirements** — What needs to be built or fixed, extracted from the ticket and discussions
4. **Related Work** — PRs, linked tickets, and other relevant engineering artifacts
5. **Relevant Code** — Code snippets from across the codebase that are relevant to this ticket. Include function signatures, class definitions, and route handlers with file paths and repo names. This helps engineers understand existing implementations even from repos they have never worked in.
6. **Open Questions** — Unresolved questions or ambiguities that need clarification
7. **Key People** — Who is involved and their roles (assignee, reviewers, participants in discussions)"""


def _format_related_content(items: list) -> str:
    """Format linked items into a structured text block for the LLM prompt."""
    if not items:
        return "No related content found."

    sections = []
    for item in items:
        if item.source_type == "code_chunk":
            section = (
                f"#### [{item.source_type}] {item.title}\n"
                f"**Relevance:** {item.relevance_score:.2f} | **Signals:** {', '.join(item.signals)}\n\n"
                f"```\n{item.snippet}\n```"
            )
        else:
            section = (
                f"#### [{item.source_type}] {item.title}\n"
                f"**Relevance:** {item.relevance_score:.2f} | **Signals:** {', '.join(item.signals)}\n\n"
                f"{item.snippet}"
            )
        sections.append(section)

    return "\n\n---\n\n".join(sections)


def _priority_label(priority: int | None) -> str:
    """Convert priority int to human-readable label."""
    labels = {0: "None", 1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}
    return labels.get(priority, "Unknown") if priority is not None else "None"


async def generate_context_page(
    session: AsyncSession,
    workspace_id: UUID,
    ticket_identifier: str,
) -> ContextPage:
    """Generate a context page for a Linear ticket.

    Flow:
    1. Look up LinearTicket by identifier
    2. Call find_related_content() to get all linked content
    3. Build structured prompt with 7-section template
    4. Call LLMClient.generate() (Gemini, Laminar-traced)
    5. Upsert into context_pages table

    Args:
        session: Async database session.
        workspace_id: Workspace the ticket belongs to.
        ticket_identifier: Human-readable ticket identifier (e.g. "CON-16").

    Returns:
        The generated ContextPage record.

    Raises:
        ValueError: If ticket not found.
    """
    # 1. Look up ticket
    stmt = select(LinearTicket).where(
        LinearTicket.workspace_id == workspace_id,
        LinearTicket.identifier == ticket_identifier,
        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    ticket = result.scalar_one_or_none()

    if ticket is None:
        raise ValueError(f"Ticket {ticket_identifier} not found")

    # Mark existing context page as generating
    existing_stmt = select(ContextPage).where(
        ContextPage.workspace_id == workspace_id,
        ContextPage.ticket_identifier == ticket_identifier,
        ContextPage.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    existing_result = await session.execute(existing_stmt)
    existing_page = existing_result.scalar_one_or_none()

    if existing_page:
        existing_page.status = "generating"
        await session.flush()

    # 2. Find related content
    linking_result = await find_related_content(session, workspace_id, ticket)

    # 3. Build prompt
    related_text = _format_related_content(linking_result.items)

    prompt = SYNTHESIS_TEMPLATE.format(
        identifier=ticket.identifier,
        title=ticket.title,
        status=ticket.status or "Unknown",
        assignee=ticket.assignee_name or "Unassigned",
        priority=_priority_label(ticket.priority),
        labels=", ".join(ticket.labels) if ticket.labels else "None",
        description=ticket.description or "No description provided.",
        related_content=related_text,
    )

    # 4. Call LLM
    llm = get_llm_client()
    llm_response = await llm.generate(
        prompt=prompt,
        system_prompt=SYNTHESIS_SYSTEM_PROMPT,
        workspace_id=workspace_id,
        ticket_identifier=ticket_identifier,
    )

    # Build sources list for the context page
    import json
    sources_list = [
        {
            "type": item.source_type,
            "id": str(item.source_id),
            "title": item.title,
            "relevance_score": round(item.relevance_score, 3),
        }
        for item in linking_result.items
    ]
    sources = sources_list

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 5. Upsert context page
    if existing_page:
        existing_page.title = f"Context: {ticket.title}"
        existing_page.content = llm_response.text
        existing_page.summary = llm_response.text[:500]
        existing_page.status = "ready"
        existing_page.sources = sources
        existing_page.generated_at = now
        existing_page.generation_model = llm_response.model
        existing_page.generation_tokens_used = llm_response.total_tokens
        context_page = existing_page
    else:
        context_page = ContextPage(
            workspace_id=workspace_id,
            ticket_id=ticket.id,
            ticket_identifier=ticket.identifier,
            title=f"Context: {ticket.title}",
            content=llm_response.text,
            summary=llm_response.text[:500],
            status="ready",
            sources=sources,
            generated_at=now,
            generation_model=llm_response.model,
            generation_tokens_used=llm_response.total_tokens,
        )
        session.add(context_page)

    await session.flush()

    logger.info(
        "Generated context page for %s (tokens=%d, sources=%d)",
        ticket_identifier,
        llm_response.total_tokens,
        len(sources),
    )

    return context_page


async def mark_context_stale(
    session: AsyncSession,
    workspace_id: UUID,
    ticket_id: UUID,
) -> None:
    """Mark a context page as stale for debounced regeneration.

    Called when source data changes (ticket updated, new comment, PR merged, etc.)
    to signal that the context page should be regenerated.

    Args:
        session: Async database session.
        workspace_id: Workspace the ticket belongs to.
        ticket_id: UUID of the LinearTicket whose context is stale.
    """
    stmt = select(ContextPage).where(
        ContextPage.workspace_id == workspace_id,
        ContextPage.ticket_id == ticket_id,
        ContextPage.deleted_at.is_(None),  # type: ignore[union-attr]
        ContextPage.status == "ready",
    )
    result = await session.execute(stmt)
    page = result.scalar_one_or_none()

    if page:
        page.status = "stale"
        logger.info(
            "Marked context page stale for ticket %s",
            page.ticket_identifier,
        )
