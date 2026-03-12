"""Context page synthesis service.

Generates AI-powered context pages for Linear tickets (and Jira issues)
by combining linked content from multiple sources into a structured document.
"""

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
from src.models.ticket import LinearTicket
from src.services.graph_ops import compute_fingerprint
from src.services.linking import find_related_content
from src.services.linking import LinkedItem, find_content_by_source, find_related_content
from src.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)


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

{graph_section}
---

Based on the ticket and related content above, produce a context page. Do NOT start with a title heading. Use only these sections (skip any section that has no real content from the sources):

1. **Summary** — 2-3 sentence overview of what this ticket is about and why it matters
2. **Background & Decisions** — Key decisions, discussions, and context from Slack, meetings, and comments. If the Graph Connections section above contains [DECISION] items, weave each into the narrative as a decision trail: state what was decided, who decided it (citing the person), where it was discussed (citing the source like Slack thread name or meeting title), and which tickets it affects. Include the confidence level (e.g., "confirmed" for high confidence, "likely decided" for lower). Always cite the source so engineers can verify. Show all decisions regardless of confidence.
3. **Requirements** — What needs to be built or fixed, extracted from the ticket and discussions
4. **Related Work** — PRs, linked tickets, and other relevant engineering artifacts. If the Graph Connections section above shows relationships between items, explain WHY they are connected in natural language (e.g., "This PR was discussed in Slack thread #deploy-v2 by @alex, who also authored the spec in Notion") rather than listing raw connections. Focus on the most important relationship paths and skip mechanical hops.
5. **Relevant Code** — Code snippets from across the codebase that are relevant to this ticket. Include function signatures, class definitions, and route handlers with file paths and repo names. This helps engineers understand existing implementations even from repos they have never worked in. If any code snippets have associated discussion provenance (noted as "Discussed in:" annotations in the Related Content), include that context so engineers know where this code was talked about.
6. **Open Questions** — Unresolved questions or ambiguities that need clarification
7. **Key People** — Who is involved and their roles (assignee, reviewers, participants in discussions). If graph data shows a person's involvement across multiple sources (e.g., authored ticket, discussed in Slack, reviewed PR), list their cross-source involvement to show the full picture of their engagement."""
from src.services.linking import LinkedItem, find_content_by_source, find_related_content


def _format_decision_node(name: str, properties: dict) -> str:
    """Format a decision node with special highlighting.

    Args:
        name: Decision description/name.
        properties: Dict with person_name, source_type, ticket_refs, confidence.

    Returns:
        Formatted string: [DECISION] name | By: person | In: source | Affects: tickets | Confidence: X.X
    """
    person = properties.get("person_name", "Unknown")
    source = properties.get("source_type", "Unknown")
    tickets = ", ".join(properties.get("ticket_refs", []))
    confidence = properties.get("confidence", "N/A")
    parts = [f"[DECISION] {name}"]
    parts.append(f"By: {person}")
    parts.append(f"In: {source}")
    if tickets:
        parts.append(f"Affects: {tickets}")
    parts.append(f"Confidence: {confidence}")
    return " | ".join(parts)


GRAPH_SECTION_TEMPLATE = """\
### Graph Connections
The following items were discovered through knowledge graph traversal --
connections between entities that may not appear in direct text search:

{graph_content}"""


def _format_graph_section(items: list) -> str:
    """Format graph-discovered items into a separate prompt section.

    Items with graph signals are rendered with their graph path provenance
    and entity types. Decision nodes get special [DECISION] highlighting.

    Args:
        items: List of LinkedItems with graph signals.

    Returns:
        Formatted graph section string, or empty string if no items.
    """
    if not items:
        return ""

    sections = []
    for item in items:
        if item.source_type == "Decision":
            # Decision items already have [DECISION] format in their snippet
            path_signal = next((s for s in item.signals if s.startswith("graph:")), "")
            section = f"**{path_signal}**\n{item.snippet}"
        else:
            path_signal = next((s for s in item.signals if s.startswith("graph:")), "")
            section = f"**{path_signal}**\n{item.snippet}\n*Type: {item.source_type}*"
        sections.append(section)

    return GRAPH_SECTION_TEMPLATE.format(graph_content="\n\n---\n\n".join(sections))


def _format_related_content(
    items: list,
    code_provenance: dict[UUID, list[str]] | None = None,
) -> str:
    """Format linked items into a structured text block for the LLM prompt.

    Args:
        items: List of LinkedItems to format.
        code_provenance: Optional dict mapping code_chunk source_id to list of
            discussion annotation strings. When provided, code_chunk items with
            matching source_ids get 'Discussed in:' annotations appended.

    Returns:
        Formatted markdown text block for the synthesis prompt.
    """
    if not items:
        return "No related content found."

    sections = []
    for item in items:
        if item.source_type == "code_chunk":
            # Build optional provenance annotation
            annotation = ""
            if code_provenance and item.source_id in code_provenance:
                discussions = code_provenance[item.source_id]
                annotation = f"\nDiscussed in: {'; '.join(discussions)}"

            section = (
                f"#### [{item.source_type}] {item.title}\n"
                f"**Relevance:** {item.relevance_score:.2f} | **Signals:** {', '.join(item.signals)}\n\n"
                f"```\n{item.snippet}\n```{annotation}"
            )
        else:
            section = (
                f"#### [{item.source_type}] {item.title}\n"
                f"**Relevance:** {item.relevance_score:.2f} | **Signals:** {', '.join(item.signals)}\n\n"
                f"{item.snippet}"
            )
        sections.append(section)

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


# Entity types considered "discussion" sources for provenance annotations
_DISCUSSION_ENTITY_TYPES = frozenset({"SlackThread", "Meeting"})

# Relationship types that indicate code-to-discussion provenance
_PROVENANCE_RELATIONSHIP_TYPES = frozenset({"mentions", "discussed_in"})


async def _get_code_provenance(
    session: AsyncSession,
    workspace_id: UUID,
    items: list,
) -> dict[UUID, list[str]]:
    """Query graph edges to find discussion provenance for code_chunk items.

    For each code_chunk LinkedItem, looks up the corresponding CodeChunk graph
    node (by fingerprint), finds connected discussion nodes (SlackThread, Meeting)
    via 'mentions' or 'discussed_in' edges, and builds annotation strings.

    Fail-silent: returns empty dict on any error.

    Args:
        session: Async database session.
        workspace_id: Workspace to query graph in.
        items: List of LinkedItems (filters for code_chunk source_type).

    Returns:
        Dict mapping code_chunk source_id to list of discussion annotation strings
        (e.g., ["#backend-chat", "Meeting: Sprint Review"]).
    """
    try:
        # Filter for code_chunk items only
        code_items = [item for item in items if item.source_type == "code_chunk"]
        if not code_items:
            return {}

        from src.models.graph_edge import GraphEdge
        from src.models.graph_node import GraphNode

        # Build fingerprint -> source_id mapping for batch lookup
        fp_to_source_id: dict[str, UUID] = {}
        for item in code_items:
            fp = compute_fingerprint("CodeChunk", f"chunk:{item.source_id}")
            fp_to_source_id[fp] = item.source_id

        # Batch query: find GraphNode records matching those fingerprints
        fingerprints = list(fp_to_source_id.keys())
        node_stmt = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.fingerprint.in_(fingerprints),  # type: ignore[union-attr]
            GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        node_result = await session.execute(node_stmt)
        chunk_nodes = node_result.scalars().all()

        if not chunk_nodes:
            return {}

        # Map node_id -> source_id for result building
        node_id_to_source_id: dict[UUID, UUID] = {}
        chunk_node_ids = []
        for node in chunk_nodes:
            chunk_node_ids.append(node.id)
            # Reverse lookup: node fingerprint -> original source_id
            fp = compute_fingerprint(node.entity_type, f"chunk:{fp_to_source_id.get(node.fingerprint, '')}")
            # Direct lookup via fingerprint
            if node.fingerprint in fp_to_source_id:
                node_id_to_source_id[node.id] = fp_to_source_id[node.fingerprint]

        # Batch query: find edges where these chunk nodes are the TARGET
        # (source_node --(mentions/discussed_in)--> chunk_node)
        # We want to find what SOURCE nodes point to our code chunks
        edge_stmt = select(GraphEdge).where(
            GraphEdge.workspace_id == workspace_id,
            GraphEdge.target_node_id.in_(chunk_node_ids),  # type: ignore[union-attr]
            GraphEdge.relationship_type.in_(_PROVENANCE_RELATIONSHIP_TYPES),  # type: ignore[union-attr]
            GraphEdge.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        edge_result = await session.execute(edge_stmt)
        edges = edge_result.scalars().all()

        if not edges:
            return {}

        # Collect source node IDs (the discussion nodes) and map to chunk node IDs
        source_node_ids = set()
        chunk_to_sources: dict[UUID, list[UUID]] = {}  # chunk_node_id -> [source_node_ids]
        for edge in edges:
            source_node_ids.add(edge.source_node_id)
            chunk_to_sources.setdefault(edge.target_node_id, []).append(edge.source_node_id)

        # Look up the source nodes to get their entity types and names
        disc_stmt = select(GraphNode).where(
            GraphNode.id.in_(list(source_node_ids)),  # type: ignore[union-attr]
            GraphNode.entity_type.in_(_DISCUSSION_ENTITY_TYPES),  # type: ignore[union-attr]
            GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        disc_result = await session.execute(disc_stmt)
        disc_nodes = disc_result.scalars().all()

        # Build node_id -> annotation string map
        disc_annotations: dict[UUID, str] = {}
        for node in disc_nodes:
            if node.entity_type == "SlackThread":
                disc_annotations[node.id] = f"#{node.name}" if not node.name.startswith("#") else node.name
            elif node.entity_type == "Meeting":
                disc_annotations[node.id] = f"Meeting: {node.name}"
            else:
                disc_annotations[node.id] = node.name

        # Build final result: source_id -> list of annotation strings
        result: dict[UUID, list[str]] = {}
        for chunk_node_id, source_ids in chunk_to_sources.items():
            source_id = node_id_to_source_id.get(chunk_node_id)
            if source_id is None:
                continue
            annotations = []
            for sid in source_ids:
                if sid in disc_annotations:
                    annotations.append(disc_annotations[sid])
            if annotations:
                result[source_id] = annotations

        return result

    except Exception:
        logger.warning(
            "Code provenance query failed (workspace=%s)",
            workspace_id,
            exc_info=True,
        )
        return {}


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
    # 1. Look up ticket (Linear first, then Jira)
    ticket = None
    ticket_id_for_fk = None

    stmt = select(LinearTicket).where(
        LinearTicket.workspace_id == workspace_id,
        LinearTicket.identifier == ticket_identifier,
        LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    linear_ticket = result.scalar_one_or_none()

    if linear_ticket:
        ticket = linear_ticket
        ticket_id_for_fk = linear_ticket.id
    else:
        jira_stmt = select(JiraIssue).where(
            JiraIssue.workspace_id == workspace_id,
            JiraIssue.jira_key == ticket_identifier,
            JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        jira_result = await session.execute(jira_stmt)
        jira_issue = jira_result.scalar_one_or_none()
        if jira_issue:
            ticket = TicketProxy.from_jira(jira_issue)

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
            ticket_id=ticket_id_for_fk,
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

    # 3. Separate graph items from non-graph items
    graph_items = [
        item for item in linking_result.items
        if any(s.startswith("graph:") for s in item.signals)
    ]
    non_graph_items = [
        item for item in linking_result.items
        if not any(s.startswith("graph:") for s in item.signals)
    ]

    # Query code provenance for non-graph code_chunk items (CODE-03)
    code_provenance = await _get_code_provenance(session, workspace_id, non_graph_items)

    # Build prompt with both sections
    related_text = _format_related_content(non_graph_items, code_provenance=code_provenance)
    graph_text = _format_graph_section(graph_items)

    prompt = SYNTHESIS_TEMPLATE.format(
        identifier=ticket.identifier,
        title=ticket.title,
        status=ticket.status or "Unknown",
        assignee=ticket.assignee_name or "Unassigned",
        priority=_priority_label(ticket.priority),
        labels=", ".join(ticket.labels) if ticket.labels else "None",
        description=ticket.description or "No description provided.",
        related_content=related_text,
        graph_section=graph_text,
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
        # 1. Look up ticket (Linear first, then Jira)
        ticket = None
        ticket_id_for_fk = None  # Only set for LinearTicket (FK constraint)

        stmt = select(LinearTicket).where(
            LinearTicket.workspace_id == workspace_id,
            LinearTicket.identifier == ticket_identifier,
            LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(stmt)
        linear_ticket = result.scalar_one_or_none()

        if linear_ticket:
            ticket = linear_ticket
            ticket_id_for_fk = linear_ticket.id
        else:
            # Try Jira
            jira_stmt = select(JiraIssue).where(
                JiraIssue.workspace_id == workspace_id,
                JiraIssue.jira_key == ticket_identifier,
                JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            jira_result = await session.execute(jira_stmt)
            jira_issue = jira_result.scalar_one_or_none()
            if jira_issue:
                ticket = TicketProxy.from_jira(jira_issue)

        if ticket is None:
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

        # linear is always connected (required by onboarding)
        connected_sources = ["linear"]
        for provider in ["slack", "github", "notion", "fathom", "jira"]:
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
                ticket_id=ticket_id_for_fk,
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

        # Separate graph items from non-graph items
        graph_items = [
            item for item in all_items
            if any(s.startswith("graph:") for s in item.signals)
        ]
        non_graph_items = [
            item for item in all_items
            if not any(s.startswith("graph:") for s in item.signals)
        ]

        code_provenance = await _get_code_provenance(session, workspace_id, non_graph_items)
        related_text = _format_related_content(non_graph_items, code_provenance=code_provenance)
        graph_text = _format_graph_section(graph_items)

        prompt = SYNTHESIS_TEMPLATE.format(
            identifier=ticket.identifier,
            title=ticket.title,
            status=ticket.status or "Unknown",
            assignee=ticket.assignee_name or "Unassigned",
            priority=_priority_label(ticket.priority),
            labels=", ".join(ticket.labels) if ticket.labels else "None",
            description=ticket.description or "No description provided.",
            related_content=related_text,
            graph_section=graph_text,
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
