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
from src.services.graph_ops import compute_fingerprint
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
You are a senior context synthesis engine embedded in an engineering intelligence \
platform. You produce structured context pages that serve as the single source of \
truth for an engineering ticket — consumed by both human engineers and downstream \
AI agents (code-review bots, sprint planners, dependency analyzers). Your output \
must be simultaneously human-scannable and machine-parseable.

## Output Contract
- Do NOT emit a title heading — the UI renders the ticket title separately.
- Only emit sections that contain substantive content derived from the provided \
sources. Omit any section entirely rather than writing "No information available."
- Never fabricate, hallucinate, or speculate about meetings, people, messages, \
code, decisions, or artifacts not explicitly present in the provided content. \
If you infer a connection, mark it with [inferred] and state your reasoning.

## Synthesis Quality Standards

### Source Attribution & Provenance
- Every factual claim must trace to a specific source. Use inline citations: \
**(Slack: #channel-name)**, **(PR: repo#123)**, **(Meeting: title)**, \
**(Notion: page-title)**, **(Comment: author)**, **(Code: repo/path/file.ext)**.
- When multiple sources corroborate the same fact, cite all of them to show \
convergence: "Auth must use PKCE flow **(Slack: #backend-auth, PR: core#412 \
review comment, Notion: Auth RFC v2)**."
- When sources conflict, present both sides with their provenance and flag the \
conflict explicitly: "⚠️ **Conflicting information:** Slack says X while the \
PR description says Y — needs resolution."

### Decision Trail Reconstruction
- Decisions are first-class objects. For each decision found in the sources:
  - State the decision clearly as an actionable conclusion.
  - Attribute it: who made or approved it, with source citation.
  - Provide temporal ordering when timestamps are available.
  - Note the confidence level: **confirmed** (explicit statement in source), \
**strongly implied** (clear from context), **inferred** (derived from indirect \
evidence — explain your reasoning).
  - If a decision was later reversed or superseded, show the full arc.

### Cross-Source Signal Synthesis
- Your primary value is connecting dots across sources that no single source \
reveals on its own. Actively look for:
  - A Slack discussion that led to a requirement in the ticket description.
  - A PR that implements what was discussed in a meeting.
  - A person who appears across multiple contexts (authored ticket, discussed \
in Slack, reviewed PR) — surface their full involvement arc.
  - Code that was referenced in discussions — link the implementation to the \
conversation context.
- Present these cross-source connections as narrative threads, not isolated \
bullet lists.

### Information Density & Structure
- Lead every section with the most decision-relevant information first.
- Use bold labels for scannable structure: **Decision:**, **Blocker:**, \
**Owner:**, **Dependency:**, **Risk:**, **Open question:**.
- Prefer structured bullet points over prose paragraphs. Each bullet should \
be a self-contained, actionable piece of information.
- For code references, always include the file path, function/class name, \
and repo when available. Format as: `repo/path/file.ext::function_name`.
- Quantify when possible: "3 PRs merged", "discussed in 2 Slack threads \
over 4 days", "5 related tickets in the same epic."

### Completeness & Honesty
- If the provided sources cover only part of the story, explicitly state what \
is well-documented and what has gaps: "**Coverage note:** Requirements are \
well-documented via Slack and Notion, but no code references were found — \
implementation may not have started."
- Rate overall context completeness at the end of the Summary section using: \
📊 **Context density: high | medium | low** — based on the volume, recency, \
and diversity of available sources.
- If critical information is missing (e.g., no requirements found, no assignee \
discussions), call it out as an explicit gap rather than silently omitting it.

### Temporal Coherence
- When timestamps are available, present information in chronological order \
within each section to show how understanding evolved.
- Use relative time markers when helpful: "3 days before the ticket was created", \
"after the PR was merged."

### Machine-Readable Markers
- Use consistent semantic markers that downstream AI agents can parse:
  - **[DECISION]** for confirmed decisions.
  - **[BLOCKER]** for blocking issues or dependencies.
  - **[RISK]** for identified risks or concerns.
  - **[GAP]** for missing information that should exist.
  - **[ACTION]** for explicit next steps or to-dos extracted from discussions.
  - **[CONFLICT]** for contradictory information across sources."""

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

    Respects MAX_PROMPT_CHARS budget — once the next item would exceed the
    limit, a truncation notice is appended and remaining items are skipped.
    """
    if not items:
        return "No related content found."

    sections: list[str] = []
    char_count = 0

    for idx, item in enumerate(items):
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
) -> tuple[LinearTicket | TicketProxy, UUID | None, UUID | None, bool]:
    """Look up a ticket by identifier, trying Linear first then Jira.

    Returns:
        (ticket, linear_ticket_id, jira_issue_id, is_linear) where the FK UUIDs
        are set for the matching provider and None for the other.

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
        return linear_ticket, linear_ticket.id, None, True

    # Fallback to Jira
    jira_stmt = select(JiraIssue).where(
        JiraIssue.workspace_id == workspace_id,
        JiraIssue.jira_key == ticket_identifier,
        JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    jira_result = await session.execute(jira_stmt)
    jira_issue = jira_result.scalar_one_or_none()

    if jira_issue:
        return TicketProxy.from_jira(jira_issue), None, jira_issue.id, False

    raise ValueError(f"Ticket {ticket_identifier} not found")


async def _upsert_context_page_placeholder(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket | TicketProxy,
    ticket_id_for_fk: UUID | None,
    jira_issue_id: UUID | None = None,
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
        # Backfill jira_issue_id for pages created before this fix
        if jira_issue_id and not context_page.jira_issue_id:
            context_page.jira_issue_id = jira_issue_id
    else:
        context_page = ContextPage(
            workspace_id=workspace_id,
            ticket_id=ticket_id_for_fk,
            jira_issue_id=jira_issue_id,
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
    code_provenance: dict[UUID, list[str]] | None = None,
) -> str:
    """Format the SYNTHESIS_TEMPLATE with ticket info and related content.

    Separates graph items from non-graph items and formats them into
    distinct sections for the synthesis prompt.
    """
    # Separate graph items from non-graph items
    graph_items = [
        item for item in related_items
        if any(s.startswith("graph:") for s in item.signals)
    ]
    non_graph_items = [
        item for item in related_items
        if not any(s.startswith("graph:") for s in item.signals)
    ]

    related_text = _format_related_content(non_graph_items, code_provenance=code_provenance)
    graph_text = _format_graph_section(graph_items)

    return SYNTHESIS_TEMPLATE.format(
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
    """
    try:
        code_items = [item for item in items if item.source_type == "code_chunk"]
        if not code_items:
            return {}

        from src.models.graph_edge import GraphEdge
        from src.models.graph_node import GraphNode

        fp_to_source_id: dict[str, UUID] = {}
        for item in code_items:
            fp = compute_fingerprint("CodeChunk", f"chunk:{item.source_id}")
            fp_to_source_id[fp] = item.source_id

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

        node_id_to_source_id: dict[UUID, UUID] = {}
        chunk_node_ids = []
        for node in chunk_nodes:
            chunk_node_ids.append(node.id)
            if node.fingerprint in fp_to_source_id:
                node_id_to_source_id[node.id] = fp_to_source_id[node.fingerprint]

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

        source_node_ids = set()
        chunk_to_sources: dict[UUID, list[UUID]] = {}
        for edge in edges:
            source_node_ids.add(edge.source_node_id)
            chunk_to_sources.setdefault(edge.target_node_id, []).append(edge.source_node_id)

        disc_stmt = select(GraphNode).where(
            GraphNode.id.in_(list(source_node_ids)),  # type: ignore[union-attr]
            GraphNode.entity_type.in_(_DISCUSSION_ENTITY_TYPES),  # type: ignore[union-attr]
            GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        disc_result = await session.execute(disc_stmt)
        disc_nodes = disc_result.scalars().all()

        disc_annotations: dict[UUID, str] = {}
        for node in disc_nodes:
            if node.entity_type == "SlackThread":
                disc_annotations[node.id] = f"#{node.name}" if not node.name.startswith("#") else node.name
            elif node.entity_type == "Meeting":
                disc_annotations[node.id] = f"Meeting: {node.name}"
            else:
                disc_annotations[node.id] = node.name

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
        ticket, ticket_id_for_fk, jira_issue_id, _is_linear = await _lookup_ticket(
            session, workspace_id, ticket_identifier
        )

        # 2. Create/update placeholder with status="generating"
        context_page = await _upsert_context_page_placeholder(
            session, workspace_id, ticket, ticket_id_for_fk, jira_issue_id
        )

        # 3. Find related content
        linking_result = await find_related_content(session, workspace_id, ticket)

        # 3b. Query code provenance for code_chunk items
        code_provenance = await _get_code_provenance(session, workspace_id, linking_result.items)

        # 4. Build prompt
        prompt = _build_synthesis_prompt(ticket, linking_result.items, code_provenance=code_provenance)

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
            ticket, ticket_id_for_fk, jira_issue_id, is_linear = await _lookup_ticket(
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

        # Slack huddles piggyback on the Slack OAuth token -- if Slack is
        # connected, huddle transcripts are also available for linking.
        if "slack" in connected_sources:
            connected_sources.append("slack_huddle")

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
            session, workspace_id, ticket, ticket_id_for_fk, jira_issue_id
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

        code_provenance = await _get_code_provenance(session, workspace_id, all_items)
        prompt = _build_synthesis_prompt(ticket, all_items, code_provenance=code_provenance)

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
