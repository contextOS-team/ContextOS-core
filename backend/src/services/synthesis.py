"""Context page synthesis service.

Generates AI-powered context pages for Linear tickets by combining
linked content from multiple sources into a structured document.
"""

import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.context_page import ContextPage
from src.models.integration import OAuthToken
from src.models.ticket import LinearTicket
from src.services.linking import LinkedItem, find_content_by_source, find_related_content
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """\
You are a context synthesis assistant for engineering teams. Your job is to produce
a structured context page that helps an engineer quickly understand the full story
behind a ticket — decisions made, requirements, related work, and open questions.

Rules:
- Do NOT include a title heading — the UI already provides the ticket title.
- Only include sections that have real content from the provided sources. Skip empty sections entirely.
- Never fabricate meetings, people, messages, or code not present in the provided content.
- Be concise and scannable. Use bullet points and bold labels over long paragraphs.
- Cite sources inline when referencing specific messages, PRs, or meetings.
- If sources are limited, acknowledge it honestly rather than padding with filler."""

SYNTHESIS_TEMPLATE = """\
{identifier} | {title} | {status} | {assignee} | {priority} | {labels}

### Ticket Description
{description}

### Related Content
{related_content}

---

Based on the ticket and related content above, produce a context page. Do NOT start with a title heading. Use only these sections (skip any section that has no real content from the sources):

## Summary
2-3 sentence overview of what this ticket is about and why it matters.

## Background & Decisions
Only include if there are actual discussions, Slack messages, meeting notes, or comments. Key decisions and context from those sources.

## Requirements
What needs to be built or fixed, extracted from the ticket and discussions.

## Related Work
Only include if there are actual PRs, linked tickets, or other engineering artifacts in the sources.

## Relevant Code
Only include if code chunks are present in the related content. Include function signatures, class definitions, and route handlers with file paths and repo names.

## Open Questions
Only include if there are genuinely unresolved questions or ambiguities in the sources.

## Key People
Only include if multiple people are involved. Who is involved and their roles."""


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
        await session.commit()
    else:
        # Create a placeholder so the page appears in the feed immediately
        existing_page = ContextPage(
            workspace_id=workspace_id,
            ticket_id=ticket.id,
            ticket_identifier=ticket.identifier,
            title=f"Context: {ticket.title}",
            content="",
            status="generating",
            sources=[],
        )
        session.add(existing_page)
        await session.flush()
        await session.commit()

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

    # 5. Update the context page (placeholder was created above)
    existing_page.title = f"Context: {ticket.title}"
    existing_page.content = llm_response.text
    existing_page.summary = llm_response.text[:500]
    existing_page.status = "ready"
    existing_page.sources = sources
    existing_page.generated_at = now
    existing_page.generation_model = llm_response.model
    existing_page.generation_tokens_used = llm_response.total_tokens
    context_page = existing_page

    await session.flush()

    logger.info(
        "Generated context page for %s (tokens=%d, sources=%d)",
        ticket_identifier,
        llm_response.total_tokens,
        len(sources),
    )

    return context_page


async def generate_context_page_stream(
    session: AsyncSession,
    workspace_id: UUID,
    ticket_identifier: str,
) -> AsyncGenerator[dict, None]:
    """Generate a context page while yielding progress events per source.

    SSE Event Protocol:
    - {"event": "start", "steps": ["slack", "github", ...]}
    - {"event": "step_start", "source": "slack"}
    - {"event": "step_complete", "source": "slack", "count": 3, "detail": "Found 3 messages"}
    - {"event": "step_error", "source": "slack", "error": "..."}
    - {"event": "step_start", "source": "synthesize"}
    - {"event": "step_complete", "source": "synthesize", "detail": "Context generated"}
    - {"event": "complete", "context_page_id": "..."}
    - {"event": "error", "message": "..."}
    """
    try:
        # 1. Look up ticket
        stmt = select(LinearTicket).where(
            LinearTicket.workspace_id == workspace_id,
            LinearTicket.identifier == ticket_identifier,
            LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        ticket = result.scalar_one_or_none()

        if ticket is None:
            yield {"event": "error", "message": f"Ticket {ticket_identifier} not found"}
            return

        # 2. Determine connected integrations
        token_stmt = select(OAuthToken.provider).where(
            OAuthToken.workspace_id == workspace_id,
            OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        token_result = await session.execute(token_stmt)
        connected_providers = {row[0] for row in token_result.fetchall()}

        # linear is always connected (required by onboarding)
        connected_sources = ["linear"]
        for provider in ["slack", "github", "notion", "fathom"]:
            if provider in connected_providers:
                connected_sources.append(provider)

        # 3. Create/update context page with status="generating"
        existing_stmt = select(ContextPage).where(
            ContextPage.workspace_id == workspace_id,
            ContextPage.ticket_identifier == ticket_identifier,
            ContextPage.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        existing_result = await session.execute(existing_stmt)
        context_page = existing_result.scalar_one_or_none()

        if context_page:
            context_page.status = "generating"
            await session.flush()
        else:
            context_page = ContextPage(
                workspace_id=workspace_id,
                ticket_id=ticket.id,
                ticket_identifier=ticket.identifier,
                title=f"Context: {ticket.title}",
                content="",
                status="generating",
                sources=[],
            )
            session.add(context_page)
            await session.flush()

        # 4. Emit start event
        yield {"event": "start", "steps": connected_sources + ["synthesize"]}

        # 5. Find content by source, yielding progress events
        all_items: list[LinkedItem] = []

        async for source_name, items, detail in find_content_by_source(
            session, workspace_id, ticket
        ):
            if source_name not in connected_sources:
                continue

            yield {"event": "step_start", "source": source_name}
            all_items.extend(items)
            yield {
                "event": "step_complete",
                "source": source_name,
                "count": len(items),
                "detail": detail,
            }

        # 6. Synthesize
        yield {"event": "step_start", "source": "synthesize"}

        related_text = _format_related_content(all_items)
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

        llm = get_llm_client()
        llm_response = await llm.generate(
            prompt=prompt,
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            workspace_id=workspace_id,
            ticket_identifier=ticket_identifier,
        )

        # 7. Update context page with results
        sources_list = [
            {
                "type": item.source_type,
                "id": str(item.source_id),
                "title": item.title,
                "relevance_score": round(item.relevance_score, 3),
            }
            for item in all_items
        ]

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        context_page.title = f"Context: {ticket.title}"
        context_page.content = llm_response.text
        context_page.summary = llm_response.text[:500]
        context_page.status = "ready"
        context_page.sources = sources_list
        context_page.generated_at = now
        context_page.generation_model = llm_response.model
        context_page.generation_tokens_used = llm_response.total_tokens

        await session.flush()

        yield {"event": "step_complete", "source": "synthesize", "detail": "Context generated"}
        yield {"event": "complete", "context_page_id": str(context_page.id)}

        logger.info(
            "Stream-generated context page for %s (tokens=%d, sources=%d)",
            ticket_identifier,
            llm_response.total_tokens,
            len(sources_list),
        )

    except Exception as e:
        logger.exception("Stream generation failed for %s", ticket_identifier)
        yield {"event": "error", "message": str(e)}


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
