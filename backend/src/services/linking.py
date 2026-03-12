"""Linking engine for finding content related to a Linear ticket.

Combines three signals with weighted scores to find and rank related content:
- Explicit references (weight 1.0): PRs linked via FK, Slack messages containing
  ticket identifier, comments via ticket_id FK
- Hybrid search (weight 0.8): Combined vector similarity + full-text search
  via hybrid_search() SQL function
- Graph traversal (weight 0.8): Knowledge graph neighbors via traverse_graph()
  with exponential depth-decay scoring
"""

import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import CONTEXT_TOKEN_BUDGET, GRAPH_MAX_DEPTH
from src.models.code_chunk import CodeChunk
from src.models.github import GithubPullRequest, GithubReview
from src.models.graph_node import GraphNode
from src.models.meeting import MeetingSegment, MeetingTranscript
from src.models.notion import NotionPage
from src.models.slack import SlackMessage
from src.models.telegram import TelegramMessage
from src.models.jira import JiraComment, JiraIssue
from src.models.ticket import LinearComment, LinearTicket
from src.services.embedding import generate_embedding
from src.services.graph_ops import compute_fingerprint

logger = logging.getLogger(__name__)

# Signal weights for combined scoring
WEIGHT_EXPLICIT = 1.0
WEIGHT_HYBRID = 0.8
WEIGHT_GRAPH = 0.8
DEPTH_DECAY = 0.6  # Exponential decay factor for graph depth scoring

# Top-k limit for hybrid search results. 10 balances recall vs noise —
# all results are ranked by combined_score, with a low floor (0.15) to
# exclude completely irrelevant items without filtering good matches.
HYBRID_SEARCH_LIMIT = 10
HYBRID_SCORE_FLOOR = 0.15

# Graph entity type to source type mapping for source-backed entities
_GRAPH_ENTITY_TO_SOURCE: dict[str, str] = {
    "Ticket": "linear_ticket",
    "SlackThread": "slack_message",
    "PR": "github_pull_request",
    "CodeChunk": "code_chunk",
    "NotionPage": "notion_page",
    "Meeting": "meeting_transcript",
}
_GRAPH_ONLY_ENTITIES = {"Person", "Decision", "Blocker", "Feature", "Component"}

# Maximum number of graph results to prevent same_as expansion explosion
_GRAPH_MAX_RESULTS = 20


@dataclass
class LinkedItem:
    """A piece of content linked to a ticket with relevance scoring."""

    source_type: str
    source_id: UUID
    title: str
    snippet: str
    relevance_score: float
    signals: list[str] = field(default_factory=list)


@dataclass
class LinkingResult:
    """Result of finding related content for a ticket."""

    ticket_id: UUID
    ticket_identifier: str
    items: list[LinkedItem] = field(default_factory=list)


async def _find_explicit_refs(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> dict[tuple[str, UUID], LinkedItem]:
    """Find content with explicit references to the ticket."""
    items: dict[tuple[str, UUID], LinkedItem] = {}

    # 1. PRs linked via linear_ticket_id FK
    pr_stmt = select(GithubPullRequest).where(
        GithubPullRequest.workspace_id == workspace_id,
        GithubPullRequest.linear_ticket_id == ticket.id,
        GithubPullRequest.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    pr_result = await session.execute(pr_stmt)
    for pr in pr_result.scalars().all():
        key = ("github_pull_request", pr.id)
        items[key] = LinkedItem(
            source_type="github_pull_request",
            source_id=pr.id,
            title=f"PR #{pr.number}: {pr.title}",
            snippet=(pr.description or "")[:200],
            relevance_score=WEIGHT_EXPLICIT,
            signals=["explicit_link"],
        )

        # Also find reviews on linked PRs
        review_stmt = select(GithubReview).where(
            GithubReview.pull_request_id == pr.id,
            GithubReview.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        review_result = await session.execute(review_stmt)
        for review in review_result.scalars().all():
            if review.body:
                rkey = ("github_review", review.id)
                items[rkey] = LinkedItem(
                    source_type="github_review",
                    source_id=review.id,
                    title=f"Review by {review.author} ({review.state})",
                    snippet=(review.body or "")[:200],
                    relevance_score=WEIGHT_EXPLICIT,
                    signals=["explicit_link"],
                )

    # 2. Comments on this ticket via ticket_id FK
    comment_stmt = select(LinearComment).where(
        LinearComment.ticket_id == ticket.id,
        LinearComment.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    comment_result = await session.execute(comment_stmt)
    for comment in comment_result.scalars().all():
        key = ("linear_comment", comment.id)
        items[key] = LinkedItem(
            source_type="linear_comment",
            source_id=comment.id,
            title=f"Comment by {comment.author_name or 'Unknown'}",
            snippet=comment.body[:200],
            relevance_score=WEIGHT_EXPLICIT,
            signals=["explicit_link"],
        )

    # 3. Slack messages containing the ticket identifier
    slack_stmt = select(SlackMessage).where(
        SlackMessage.workspace_id == workspace_id,
        SlackMessage.text.ilike(f"%{ticket.identifier}%"),  # type: ignore[union-attr]
        SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    slack_result = await session.execute(slack_stmt)
    for msg in slack_result.scalars().all():
        key = ("slack_message", msg.id)
        items[key] = LinkedItem(
            source_type="slack_message",
            source_id=msg.id,
            title=f"Slack message by {msg.user_name or 'Unknown'} in #{msg.channel_name or 'unknown'}",
            snippet=msg.text[:200],
            relevance_score=WEIGHT_EXPLICIT,
            signals=["explicit_reference"],
        )

    return items


async def _find_hybrid_matches(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> dict[tuple[str, UUID], LinkedItem]:
    """Find related content via hybrid vector + full-text search."""
    items: dict[tuple[str, UUID], LinkedItem] = {}

    query_text = f"{ticket.title}\n\n{ticket.description or ''}"
    try:
        query_embedding = await generate_embedding(query_text)
    except Exception:
        logger.warning("Failed to generate query embedding for %s", ticket.identifier)
        return items

    if not query_embedding or all(v == 0.0 for v in query_embedding):
        return items

    # Call hybrid_search() SQL function — use a low floor to exclude noise,
    # but rely primarily on top-k ranking rather than a strict threshold
    match_stmt = text("""
        SELECT id, source_type, source_id, similarity, keyword_rank, combined_score, metadata
        FROM hybrid_search(
            CAST(:query_embedding AS vector),
            :query_text,
            CAST(:workspace_id AS uuid),
            NULL,
            0.7,
            0.3,
            :floor,
            :limit
        )
    """)

    result = await session.execute(
        match_stmt,
        {
            "query_embedding": str(query_embedding),
            "query_text": ticket.title,
            "workspace_id": str(workspace_id),
            "floor": HYBRID_SCORE_FLOOR,
            "limit": HYBRID_SEARCH_LIMIT,
        },
    )

    # Collect all hybrid hits first (skip self-matches)
    hits: list[tuple[str, UUID, float]] = []
    for row in result.fetchall():
        source_type = row[1]
        source_id = row[2]
        combined_score = row[5]

        if source_type == "linear_ticket" and source_id == ticket.id:
            continue

        hits.append((source_type, source_id, combined_score))

    # Bulk-fetch summaries for all hits
    summaries = await _bulk_lookup_source_summaries(
        session, [(st, sid) for st, sid, _ in hits]
    )

    for source_type, source_id, combined_score in hits:
        key = (source_type, source_id)
        score = combined_score * WEIGHT_HYBRID
        title, snippet = summaries.get(key, (source_type, ""))

        items[key] = LinkedItem(
            source_type=source_type,
            source_id=source_id,
            title=title,
            snippet=snippet,
            relevance_score=score,
            signals=["hybrid_search"],
        )

    return items


# Map source_type -> (model class, title+snippet extractor)
_SOURCE_SUMMARY_MAP: dict[str, tuple[type, callable]] = {
    "linear_ticket": (LinearTicket, lambda r: (r.title, (r.description or "")[:200])),
    "linear_comment": (
        LinearComment,
        lambda r: (f"Comment by {r.author_name or 'Unknown'}", r.body[:200]),
    ),
    "slack_message": (
        SlackMessage,
        lambda r: (
            f"Slack by {r.user_name or 'Unknown'} in #{r.channel_name or 'unknown'}",
            r.text[:200],
        ),
    ),
    "meeting_transcript": (
        MeetingTranscript,
        lambda r: (f"Meeting: {r.title or 'Untitled'}", r.transcript[:200]),
    ),
    "meeting_segment": (
        MeetingSegment,
        lambda r: (
            f"Segment by {r.speaker_name or 'Unknown'}",
            r.text[:200],
        ),
    ),
    "github_pull_request": (
        GithubPullRequest,
        lambda r: (f"PR #{r.number}: {r.title}", (r.description or "")[:200]),
    ),
    "github_review": (
        GithubReview,
        lambda r: (
            f"Review by {r.author} ({r.state})",
            (r.body or "")[:200],
        ),
    ),
    "notion_page": (
        NotionPage,
        lambda r: (r.title, (r.content or "")[:200]),
    ),
    "code_chunk": (
        CodeChunk,
        lambda r: (
            f"{r.symbol_type}: {r.symbol_name} ({r.repo_full_name}:{r.file_path})",
            r.content[:200],
        ),
    ),
    "telegram_message": (
        TelegramMessage,
        lambda r: (
            f"Telegram by {r.from_first_name or r.from_username or 'Unknown'} in {r.chat_title or 'DM'}",
            r.text[:200],
        ),
    ),
    "jira_issue": (
        JiraIssue,
        lambda r: (f"{r.jira_key}: {r.summary}", (r.description or "")[:200]),
    ),
    "jira_comment": (
        JiraComment,
        lambda r: (f"Jira comment by {r.author_name or 'Unknown'}", (r.body or "")[:200]),
    ),
}


async def _bulk_lookup_source_summaries(
    session: AsyncSession,
    keys: list[tuple[str, UUID]],
) -> dict[tuple[str, UUID], tuple[str, str]]:
    """Bulk-fetch title/snippet for multiple source records.

    Groups IDs by source_type, performs one query per type, then
    maps results in-memory. Eliminates the N+1 from per-result lookups.
    """
    result_map: dict[tuple[str, UUID], tuple[str, str]] = {}
    if not keys:
        return result_map

    # Group IDs by source_type
    grouped: dict[str, list[UUID]] = {}
    for source_type, source_id in keys:
        grouped.setdefault(source_type, []).append(source_id)

    for source_type, ids in grouped.items():
        if source_type not in _SOURCE_SUMMARY_MAP:
            for sid in ids:
                result_map[(source_type, sid)] = (source_type, "")
            continue

        model_cls, extract = _SOURCE_SUMMARY_MAP[source_type]
        stmt = select(model_cls).where(model_cls.id.in_(ids))  # type: ignore[union-attr]
        db_result = await session.execute(stmt)
        records = db_result.scalars().all()

        for record in records:
            result_map[(source_type, record.id)] = extract(record)

        # Fill missing IDs
        fetched_ids = {r.id for r in records}
        for sid in ids:
            if sid not in fetched_ids:
                result_map[(source_type, sid)] = (source_type, "")

    return result_map


async def _lookup_source_summary(
    session: AsyncSession,
    source_type: str,
    source_id: UUID,
) -> tuple[str, str]:
    """Look up a human-readable title and snippet for a single source record.

    Uses the shared _SOURCE_SUMMARY_MAP. Prefer _bulk_lookup_source_summaries
    when fetching multiple records to avoid N+1 queries.
    """
    if source_type not in _SOURCE_SUMMARY_MAP:
        return (source_type, "")

    model_cls, extract = _SOURCE_SUMMARY_MAP[source_type]
    stmt = select(model_cls).where(model_cls.id == source_id)
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        return (source_type, "")
    return extract(record)


async def _find_graph_results(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> dict[tuple[str, UUID], LinkedItem]:
    """Find related content via knowledge graph traversal.

    Looks up the ticket's graph node by fingerprint, then traverses
    neighboring nodes using the traverse_graph() SQL function. Results
    are scored with exponential depth decay and returned as LinkedItems
    with graph provenance metadata.

    Fails silently on missing graph nodes or database errors, returning
    an empty dict so retrieval continues with explicit + hybrid signals.

    Args:
        session: Async database session.
        workspace_id: Workspace to search within.
        ticket: The LinearTicket to find graph neighbors for.

    Returns:
        Dict mapping (source_type, source_id) to LinkedItem with graph signals.
    """
    items: dict[tuple[str, UUID], LinkedItem] = {}

    try:
        # 1. Find the ticket's graph node by fingerprint
        fingerprint = compute_fingerprint("Ticket", ticket.identifier)
        node_stmt = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.fingerprint == fingerprint,
            GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        node_result = await session.execute(node_stmt)
        graph_node = node_result.scalar_one_or_none()

        if graph_node is None:
            return items

        # 2. Traverse the graph from this node
        # Extra hop budget for same_as edges that don't count as real hops
        traverse_stmt = text("""
            SELECT node_id, entity_type, name, properties,
                   edge_relationship_type, depth, path
            FROM traverse_graph(
                CAST(:start_node_id AS uuid),
                CAST(:workspace_id AS uuid),
                :max_depth,
                'both',
                NULL,
                NULL
            )
            WHERE depth > 0
        """)
        traverse_result = await session.execute(
            traverse_stmt,
            {
                "start_node_id": str(graph_node.id),
                "workspace_id": str(workspace_id),
                "max_depth": GRAPH_MAX_DEPTH + 1,
            },
        )
        rows = traverse_result.fetchall()

        if not rows:
            return items

        # 3. Build node map for provenance path construction and
        #    track which nodes were reached via same_as edges
        same_as_node_ids: set[UUID] = set()
        result_rows = []

        for row in rows:
            if row.edge_relationship_type == "same_as":
                same_as_node_ids.add(row.node_id)
                continue  # same_as nodes themselves are not results
            result_rows.append(row)

        # Cap results to prevent explosion
        result_rows = result_rows[:_GRAPH_MAX_RESULTS]

        # 4. Bulk-fetch source_id for source-backed graph nodes
        #    traverse_graph() returns node_id (graph UUID) but we need
        #    graph_nodes.source_id (FK to the actual source table)
        source_backed_node_ids = [
            row.node_id
            for row in result_rows
            if row.entity_type in _GRAPH_ENTITY_TO_SOURCE
        ]
        node_source_map: dict[UUID, UUID | None] = {}
        if source_backed_node_ids:
            source_lookup = await session.execute(
                select(GraphNode.id, GraphNode.source_id).where(
                    GraphNode.id.in_(source_backed_node_ids),
                )
            )
            for nid, sid in source_lookup.fetchall():
                node_source_map[nid] = sid

        # 5. Process each result row
        source_backed_keys: list[tuple[str, UUID]] = []
        pending: list[tuple[tuple[str, UUID], float, str, str]] = []

        for row in result_rows:
            entity_type = row.entity_type
            effective_depth = row.depth

            # Adjust effective depth: if any ancestor in the path is a
            # same_as node, reduce depth by the number of same_as hops
            if row.path:
                same_as_count = sum(
                    1 for nid in row.path
                    if nid in same_as_node_ids
                )
                effective_depth = max(1, row.depth - same_as_count)

            score = WEIGHT_GRAPH * (DEPTH_DECAY ** effective_depth)

            # Build provenance path string
            provenance = f"graph:{entity_type}({row.edge_relationship_type},d={effective_depth})"

            if entity_type in _GRAPH_ENTITY_TO_SOURCE:
                source_type = _GRAPH_ENTITY_TO_SOURCE[entity_type]
                source_id = node_source_map.get(row.node_id) or row.node_id
                key = (source_type, source_id)
                source_backed_keys.append(key)
                pending.append((key, score, provenance, row.name))
            elif entity_type in _GRAPH_ONLY_ENTITIES:
                # Graph-only entities use node_id as source_id
                source_type = entity_type.lower()
                source_id = row.node_id
                key = (source_type, source_id)

                # Special formatting for Decision nodes
                if entity_type == "Decision":
                    props = row.properties or {}
                    snippet = (
                        f"[DECISION] {row.name}"
                        f" | By: {props.get('by', 'Unknown')}"
                        f" | In: {props.get('source', 'Unknown')}"
                        f" | Affects: {props.get('affects', 'Unknown')}"
                        f" | Confidence: {props.get('confidence', 'N/A')}"
                    )
                    items[key] = LinkedItem(
                        source_type=source_type,
                        source_id=source_id,
                        title=row.name,
                        snippet=snippet,
                        relevance_score=score,
                        signals=[provenance],
                    )
                else:
                    props = row.properties or {}
                    snippet = props.get("description", row.name)[:200]
                    items[key] = LinkedItem(
                        source_type=source_type,
                        source_id=source_id,
                        title=row.name,
                        snippet=snippet,
                        relevance_score=score,
                        signals=[provenance],
                    )

        # 6. Bulk-fetch summaries for source-backed entities
        if source_backed_keys:
            summaries = await _bulk_lookup_source_summaries(
                session, source_backed_keys
            )

            for key, score, provenance, node_name in pending:
                title, snippet = summaries.get(key, (key[0], ""))
                # Fall back to graph node name when source lookup fails
                if title == key[0]:
                    title = node_name
                items[key] = LinkedItem(
                    source_type=key[0],
                    source_id=key[1],
                    title=title,
                    snippet=snippet,
                    relevance_score=score,
                    signals=[provenance],
                )

    except Exception:
        logger.warning(
            "Graph traversal failed for ticket %s, falling back to empty graph results",
            ticket.identifier,
        )
        return {}

    return items


def _estimate_tokens(item: LinkedItem) -> int:
    """Estimate the token count for a LinkedItem.

    Uses a simple heuristic: total character length of title, snippet,
    and signals divided by 4 (average chars per token), plus overhead
    for formatting.
    """
    text_len = len(item.title) + len(item.snippet) + sum(len(s) for s in item.signals)
    return (text_len + 50) // 4


def _normalize_signal(signal: str) -> str:
    """Normalize a signal string to its base type for grouping.

    Maps specific signal names to categories:
    - "graph:..." -> "graph"
    - "explicit_link" / "explicit_reference" -> "explicit"
    - "hybrid_search" -> "hybrid"
    """
    if signal.startswith("graph:"):
        return "graph"
    if signal in ("explicit_link", "explicit_reference"):
        return "explicit"
    if signal == "hybrid_search":
        return "hybrid"
    return signal


def _apply_token_budget(
    items: list[LinkedItem],
    budget_tokens: int = CONTEXT_TOKEN_BUDGET,
) -> list[LinkedItem]:
    """Trim a list of LinkedItems to fit within a token budget.

    Guarantees signal diversity by reserving the top-1 item from each
    signal type before filling remaining budget by score. This ensures
    that even minority signals (e.g., a single graph result) are
    represented in the final output.

    Args:
        items: List of LinkedItems to trim.
        budget_tokens: Maximum token budget (default: CONTEXT_TOKEN_BUDGET).

    Returns:
        Trimmed list of LinkedItems sorted by relevance_score descending.
    """
    if not items:
        return items

    # Group items by primary signal type (first signal, normalized)
    groups: dict[str, list[LinkedItem]] = {}
    for item in items:
        primary = _normalize_signal(item.signals[0]) if item.signals else "unknown"
        groups.setdefault(primary, []).append(item)

    # Sort each group by relevance_score descending
    for group_items in groups.values():
        group_items.sort(key=lambda x: x.relevance_score, reverse=True)

    # Reserve top-1 from each signal group
    reserved: list[LinkedItem] = []
    remaining_pool: list[LinkedItem] = []

    for signal_type, group_items in groups.items():
        reserved.append(group_items[0])
        remaining_pool.extend(group_items[1:])

    # Sort remaining pool by score descending
    remaining_pool.sort(key=lambda x: x.relevance_score, reverse=True)

    # Build result starting with reserved items
    result = list(reserved)
    used_tokens = sum(_estimate_tokens(it) for it in result)

    # Fill from pool while within budget
    for item in remaining_pool:
        item_tokens = _estimate_tokens(item)
        if used_tokens + item_tokens > budget_tokens:
            break
        result.append(item)
        used_tokens += item_tokens

    # Sort final result by relevance_score descending
    result.sort(key=lambda x: x.relevance_score, reverse=True)
    return result

SOURCE_TYPE_MAP = {
    "slack": ["slack_message"],
    "github": ["github_pull_request", "github_review", "code_chunk"],
    "notion": ["notion_page"],
    "fathom": ["meeting_transcript", "meeting_segment"],
    "linear": ["linear_comment"],
    "telegram": ["telegram_message"],
    "jira": ["jira_issue", "jira_comment"],
}


async def find_content_by_source(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> AsyncGenerator[tuple[str, list[LinkedItem], str], None]:
    """Find related content and yield results grouped by source.

    Yields (source_name, items, detail_string) tuples for each source
    that has content. Runs all queries upfront, then groups by source.
    """
    # Run existing queries
    explicit = await _find_explicit_refs(session, workspace_id, ticket)
    hybrid = await _find_hybrid_matches(session, workspace_id, ticket)

    # Merge
    merged: dict[tuple[str, UUID], LinkedItem] = {}
    for signal_items in [explicit, hybrid]:
        for key, item in signal_items.items():
            if key in merged:
                merged[key].relevance_score += item.relevance_score
                merged[key].signals.extend(item.signals)
            else:
                merged[key] = item

    # Group by source
    for source_name, source_types in SOURCE_TYPE_MAP.items():
        source_items = [
            item for item in merged.values()
            if item.source_type in source_types
        ]
        source_items.sort(key=lambda x: x.relevance_score, reverse=True)

        # Build detail string
        if source_name == "github":
            prs = sum(1 for i in source_items if i.source_type == "github_pull_request")
            reviews = sum(1 for i in source_items if i.source_type == "github_review")
            code = sum(1 for i in source_items if i.source_type == "code_chunk")
            parts = []
            if prs:
                parts.append(f"{prs} PR{'s' if prs > 1 else ''}")
            if reviews:
                parts.append(f"{reviews} review{'s' if reviews > 1 else ''}")
            if code:
                parts.append(f"{code} code file{'s' if code > 1 else ''}")
            detail = f"Found {', '.join(parts)}" if parts else "No PRs or code found"
        elif source_name == "slack":
            n = len(source_items)
            detail = f"Found {n} message{'s' if n != 1 else ''}" if n else "No messages found"
        elif source_name == "notion":
            n = len(source_items)
            detail = f"Found {n} page{'s' if n != 1 else ''}" if n else "No pages found"
        elif source_name == "fathom":
            n = len(source_items)
            detail = f"Found {n} meeting segment{'s' if n != 1 else ''}" if n else "No meetings found"
        elif source_name == "linear":
            n = len(source_items)
            detail = f"Found {n} comment{'s' if n != 1 else ''}" if n else "No comments found"
        elif source_name == "telegram":
            n = len(source_items)
            detail = f"Found {n} message{'s' if n != 1 else ''}" if n else "No messages found"
        else:
            detail = f"Found {len(source_items)} items" if source_items else "No items found"

        yield source_name, source_items, detail


async def find_related_content(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
) -> LinkingResult:
    """Find all content related to a Linear ticket using multi-signal search.

    Combines explicit references, hybrid search (vector + full-text), and
    graph traversal with weighted scores to produce a ranked, budget-trimmed
    list of related items.

    Args:
        session: Async database session.
        workspace_id: Workspace to search within.
        ticket: The LinearTicket to find related content for.

    Returns:
        LinkingResult with ranked list of LinkedItem objects.
    """
    # Gather signals from all three sources
    explicit = await _find_explicit_refs(session, workspace_id, ticket)
    hybrid = await _find_hybrid_matches(session, workspace_id, ticket)
    graph = await _find_graph_results(session, workspace_id, ticket)

    # Merge results: combine scores for items found by multiple signals
    merged: dict[tuple[str, UUID], LinkedItem] = {}

    for source, signal_items in [
        ("explicit", explicit),
        ("hybrid", hybrid),
        ("graph", graph),
    ]:
        for key, item in signal_items.items():
            if key in merged:
                existing = merged[key]
                existing.relevance_score = max(
                    existing.relevance_score + item.relevance_score, 0.0
                )
                existing.signals.extend(item.signals)
            else:
                merged[key] = item

    # Apply token budget trimming with signal diversity guarantee
    merged_items = list(merged.values())
    budget_trimmed = _apply_token_budget(merged_items)

    return LinkingResult(
        ticket_id=ticket.id,
        ticket_identifier=ticket.identifier,
        items=budget_trimmed,
    )
