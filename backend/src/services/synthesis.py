"""Context page synthesis service.

Generates AI-powered context pages for Linear tickets (and Jira issues)
by combining linked content from multiple sources into a structured document.
"""

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.context_page import ContextPage
from src.models.integration import OAuthToken, WorkspaceIntegration
from src.models.jira import JiraIssue
from src.models.sync import SyncCursor
from src.models.ticket import LinearTicket
from src.services.linking import LinkedItem, find_content_by_source, find_related_content
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# Maximum characters for the synthesis prompt's related content section.
# ~25k tokens at ~4 chars/token.  Exceeding this risks hitting model context
# limits and increasing latency/cost with diminishing returns.
MAX_PROMPT_CHARS = 100_000


@dataclass
class TicketProxy:
    """Duck-typed proxy that lets Jira issues pass through the linking engine.

    The linking and synthesis code accesses ticket.id, .identifier, .title,
    .description, .status, .assignee_name, .priority, and .labels. This
    proxy maps JiraIssue fields to the expected interface.
    """

    id: UUID
    identifier: str
    title: str
    description: str | None = None
    status: str | None = None
    assignee_name: str | None = None
    priority: int | str | None = None
    labels: list[str] | None = None

    @classmethod
    def from_jira(cls, issue: JiraIssue) -> "TicketProxy":
        return cls(
            id=issue.id,
            identifier=issue.jira_key,
            title=issue.summary,
            description=issue.description,
            status=issue.status,
            assignee_name=issue.assignee_name,
            priority=issue.priority,  # pass Jira's string directly
            labels=issue.labels,
        )


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
    """Format linked items into a structured text block for the LLM prompt.

    Respects MAX_PROMPT_CHARS budget — once the next item would exceed the
    limit, a truncation notice is appended and remaining items are skipped.
    """
    if not items:
        return "No related content found."

    sections: list[str] = []
    char_count = 0

    for idx, item in enumerate(items):
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

        # Check token budget before adding
        separator_len = len("\n\n---\n\n") if sections else 0
        if char_count + separator_len + len(section) > MAX_PROMPT_CHARS:
            remaining = len(items) - idx
            sections.append(f"[Truncated: {remaining} more items omitted]")
            break

        sections.append(section)
        char_count += separator_len + len(section)

    return "\n\n---\n\n".join(sections)


def _priority_label(priority: int | str | None) -> str:
    """Convert priority to human-readable label.

    Handles Linear int priorities (0-4) and Jira string priorities
    (e.g. "High", "Medium") passed through from TicketProxy.
    """
    if priority is None:
        return "None"
    if isinstance(priority, str):
        return priority
    labels = {0: "None", 1: "Urgent", 2: "High", 3: "Normal", 4: "Low"}
    return labels.get(priority, "Unknown")


# ---------------------------------------------------------------------------
# Shared helpers — used by both generate_context_page and
# generate_context_page_stream to eliminate duplication (ARCH-02).
# ---------------------------------------------------------------------------


async def _lookup_ticket(
    session: AsyncSession,
    workspace_id: UUID,
    ticket_identifier: str,
) -> tuple[LinearTicket | TicketProxy, UUID | None, bool]:
    """Look up a ticket by identifier, trying Linear first then Jira.

    Returns:
        (ticket, ticket_id_for_fk, is_linear) where ticket_id_for_fk is the
        UUID to use as the ContextPage.ticket_id FK (set only for Linear rows),
        and is_linear indicates which provider the ticket was found in.

    Raises:
        ValueError: If the ticket is not found in any provider.
    """
    stmt = select(LinearTicket).where(
        LinearTicket.workspace_id == workspace_id,
        LinearTicket.identifier == ticket_identifier,
        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    linear_ticket = result.scalar_one_or_none()

    if linear_ticket:
        return linear_ticket, linear_ticket.id, True

    # Fallback to Jira
    jira_stmt = select(JiraIssue).where(
        JiraIssue.workspace_id == workspace_id,
        JiraIssue.jira_key == ticket_identifier,
        JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    jira_result = await session.execute(jira_stmt)
    jira_issue = jira_result.scalar_one_or_none()

    if jira_issue:
        return TicketProxy.from_jira(jira_issue), None, False

    raise ValueError(f"Ticket {ticket_identifier} not found")


async def _upsert_context_page_placeholder(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket | TicketProxy,
    ticket_id_for_fk: UUID | None,
) -> ContextPage:
    """Create or update a ContextPage with status='generating'.

    Flushes and commits immediately so that the placeholder is visible to
    other sessions (e.g. Realtime subscribers) before the LLM call starts.
    """
    existing_stmt = select(ContextPage).where(
        ContextPage.workspace_id == workspace_id,
        ContextPage.ticket_identifier == ticket.identifier,
        ContextPage.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    existing_result = await session.execute(existing_stmt)
    context_page = existing_result.scalar_one_or_none()

    if context_page:
        context_page.status = "generating"
    else:
        context_page = ContextPage(
            workspace_id=workspace_id,
            ticket_id=ticket_id_for_fk,
            ticket_identifier=ticket.identifier,
            title=f"Context: {ticket.title}",
            content="",
            status="generating",
            sources=[],
        )
        session.add(context_page)

    await session.flush()
    await session.commit()
    return context_page


def _build_synthesis_prompt(
    ticket: LinearTicket | TicketProxy,
    related_items: list[LinkedItem],
) -> str:
    """Format the SYNTHESIS_TEMPLATE with ticket info and related content.

    Pure function — no async, no DB access.
    """
    related_text = _format_related_content(related_items)

    return SYNTHESIS_TEMPLATE.format(
        identifier=ticket.identifier,
        title=ticket.title,
        status=ticket.status or "Unknown",
        assignee=ticket.assignee_name or "Unassigned",
        priority=_priority_label(ticket.priority),
        labels=", ".join(ticket.labels) if ticket.labels else "None",
        description=ticket.description or "No description provided.",
        related_content=related_text,
    )


# ---------------------------------------------------------------------------
# Public generation functions
# ---------------------------------------------------------------------------


async def generate_context_page(
    session: AsyncSession,
    workspace_id: UUID,
    ticket_identifier: str,
) -> ContextPage:
    """Generate a context page for a Linear ticket or Jira issue.

    Flow:
    1. Look up LinearTicket or JiraIssue by identifier
    2. Call find_related_content() to get all linked content
    3. Build structured prompt with 7-section template
    4. Call LLMClient.generate() (Gemini, Laminar-traced)
    5. Upsert into context_pages table

    Args:
        session: Async database session.
        workspace_id: Workspace the ticket belongs to.
        ticket_identifier: Human-readable ticket identifier (e.g. "CON-16", "PROJ-123").

    Returns:
        The generated ContextPage record.

    Raises:
        ValueError: If ticket not found.
    """
    context_page: ContextPage | None = None

    try:
        # 1. Look up ticket (Linear first, then Jira)
        ticket, ticket_id_for_fk, _is_linear = await _lookup_ticket(
            session, workspace_id, ticket_identifier
        )

        # 2. Create/update placeholder with status="generating"
        context_page = await _upsert_context_page_placeholder(
            session, workspace_id, ticket, ticket_id_for_fk
        )

        # 3. Find related content
        linking_result = await find_related_content(session, workspace_id, ticket)

        # 4. Build prompt
        prompt = _build_synthesis_prompt(ticket, linking_result.items)

        # 5. Call LLM
        llm = get_llm_client()
        llm_response = await llm.generate(
            prompt=prompt,
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            workspace_id=workspace_id,
            ticket_identifier=ticket_identifier,
        )

        # Build sources list for the context page
        sources_list = [
            {
                "type": item.source_type,
                "id": str(item.source_id),
                "title": item.title,
                "relevance_score": round(item.relevance_score, 3),
            }
            for item in linking_result.items
        ]

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # 6. Update the context page with LLM results
        context_page.title = f"Context: {ticket.title}"
        context_page.content = llm_response.text
        context_page.summary = llm_response.text[:500]
        context_page.status = "ready"
        context_page.sources = sources_list
        context_page.generated_at = now
        context_page.generation_model = llm_response.model
        context_page.generation_tokens_used = llm_response.total_tokens

        # BUG-03 fix: flush AND commit so the caller doesn't need to commit
        await session.flush()
        await session.commit()

        logger.info(
            "Generated context page for %s (tokens=%d, sources=%d)",
            ticket_identifier,
            llm_response.total_tokens,
            len(sources_list),
        )

        return context_page

    except Exception as e:
        logger.exception("Generation failed for %s", ticket_identifier)
        # BUG-01 fix: persist error status so page doesn't stay stuck in "generating"
        try:
            if context_page:
                context_page.status = "error"
                await session.flush()
                await session.commit()
        except Exception:
            logger.warning("Failed to persist error status for %s", ticket_identifier)
        raise


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
    context_page: ContextPage | None = None

    try:
        # 1. Look up ticket (Linear first, then Jira) using shared helper
        try:
            ticket, ticket_id_for_fk, is_linear = await _lookup_ticket(
                session, workspace_id, ticket_identifier
            )
        except ValueError:
            yield {"event": "error", "message": f"Ticket {ticket_identifier} not found"}
            return

        # 2. Determine connected integrations
        # Check OAuth tokens (slack, github, notion, linear)
        token_stmt = select(OAuthToken.provider).where(
            OAuthToken.workspace_id == workspace_id,
            OAuthToken.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        token_result = await session.execute(token_stmt)
        connected_providers = {row[0] for row in token_result.fetchall()}

        # Also check WorkspaceIntegration for API-key integrations (fathom)
        integration_stmt = select(WorkspaceIntegration.provider).where(
            WorkspaceIntegration.workspace_id == workspace_id,
            WorkspaceIntegration.status == "connected",
            WorkspaceIntegration.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        integration_result = await session.execute(integration_stmt)
        connected_providers.update(row[0] for row in integration_result.fetchall())

        # Build connected sources from actual OAuth tokens / integrations.
        # The ticket provider (linear or jira) is determined by which one the
        # ticket was found in, NOT by hardcoding.
        connected_sources: list[str] = []

        # Add the ticket provider based on the ticket type
        if is_linear:
            connected_sources.append("linear")
        elif ticket is not None:
            # Jira ticket — only show Jira, not Linear
            connected_sources.append("jira")

        for provider in ["slack", "github", "gitlab", "notion", "fathom", "telegram"]:
            if provider in connected_providers:
                connected_sources.append(provider)

        # 2b. Check sync status for connected providers
        syncing_providers: set[str] = set()
        if connected_sources:
            sync_stmt = select(SyncCursor.provider, SyncCursor.sync_status).where(
                SyncCursor.workspace_id == workspace_id,
                SyncCursor.provider.in_(connected_sources),
                SyncCursor.sync_status == "syncing",
            )
            sync_result = await session.execute(sync_stmt)
            syncing_providers = {row[0] for row in sync_result.fetchall()}

        # 3. Create/update context page with status="generating" using shared helper
        context_page = await _upsert_context_page_placeholder(
            session, workspace_id, ticket, ticket_id_for_fk
        )

        # 4. Emit start event
        yield {"event": "start", "steps": connected_sources + ["synthesize"]}

        # 5. Find content by source, yielding progress events
        all_items: list[LinkedItem] = []

        async for source_name, items, detail in find_content_by_source(
            session, workspace_id, ticket, connected_sources=set(connected_sources)
        ):
            # Belt-and-suspenders: find_content_by_source also filters internally
            if source_name not in connected_sources:
                continue

            yield {"event": "step_start", "source": source_name}
            all_items.extend(items)

            # Append sync warning if provider is still syncing
            step_detail = detail
            is_syncing = source_name in syncing_providers
            if is_syncing and len(items) == 0:
                step_detail = "Sync in progress — data not yet available"

            event: dict = {
                "event": "step_complete",
                "source": source_name,
                "count": len(items),
                "detail": step_detail,
            }
            if is_syncing:
                event["syncing"] = True
            yield event

        # 6. Synthesize
        yield {"event": "step_start", "source": "synthesize"}

        prompt = _build_synthesis_prompt(ticket, all_items)

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
        await session.commit()

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
        # BUG-01 fix: persist error status so page doesn't stay stuck in "generating"
        try:
            if context_page:
                context_page.status = "error"
                await session.flush()
                await session.commit()
        except Exception:
            logger.warning("Failed to persist error status for %s", ticket_identifier)
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
