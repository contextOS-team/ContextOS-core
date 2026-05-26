"""Linking engine for finding content related to a Linear ticket.

Combines three signals with weighted scores to find and rank related content:
- Explicit references (weight 1.0): PRs linked via FK, Slack messages containing
  ticket identifier, comments via ticket_id FK
- Hybrid search (weight 0.8): Combined vector similarity + full-text search
  via hybrid_search() SQL function
- Graph traversal (weight 0.8): Knowledge graph neighbors via traverse_graph()
  with exponential depth-decay scoring
"""

import asyncio
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
from src.models.gitlab import GitlabMergeRequest, GitlabReview
from src.models.graph_node import GraphNode
from src.models.jira import JiraComment, JiraIssue
from src.models.meeting import MeetingSegment, MeetingTranscript
from src.models.notion import NotionPage
from src.models.slack import SlackMessage
from src.models.telegram import TelegramMessage
from src.models.ticket import LinearComment, LinearTicket
from src.services.embedding import generate_embedding
from src.services.graph_ops import compute_fingerprint
from src.services.graph_rag_types import (
    RetrievalFeatures,
    RetrievalTarget,
    VerificationState,
)
from src.services.llm_client import get_llm_client
from src.services.slack_events import slack_archive_url

logger = logging.getLogger(__name__)

# Signal weights for combined scoring
WEIGHT_EXPLICIT = 1.0
WEIGHT_HYBRID = 0.8
WEIGHT_GRAPH = 0.8
DEPTH_DECAY = 0.6  # Exponential decay factor for graph depth scoring
RRF_K = 60  # Reciprocal Rank Fusion constant (standard value from literature)

# Top-k limit for hybrid search results. 10 balances recall vs noise —
# all results are ranked by combined_score, with a low floor (0.15) to
# exclude completely irrelevant items without filtering good matches.
HYBRID_SEARCH_LIMIT = 20
HYBRID_SEARCH_CODE_LIMIT = 8  # Dedicated budget for code_chunk results
HYBRID_SCORE_FLOOR = 0.10

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

_ALL_RETRIEVAL_TARGETS = frozenset(RetrievalTarget)
_SOURCE_RETRIEVAL_TARGETS = frozenset(
    {RetrievalTarget.SOURCE_EVIDENCE, RetrievalTarget.RELATED_WORK}
)
_GRAPH_RETRIEVAL_TARGETS = frozenset(
    {
        RetrievalTarget.DECISION_RECEIPTS,
        RetrievalTarget.GRAPH_NEIGHBORHOOD,
        RetrievalTarget.SOURCE_EVIDENCE,
    }
)
_GRAPH_ONLY_SOURCE_TYPES = {"decision", "person", "blocker", "feature", "component"}


def _validate_retrieval_targets(
    targets: list[RetrievalTarget] | None,
) -> frozenset[RetrievalTarget]:
    """Validate caller-requested retrieval targets.

    ``None`` preserves the historical broad retrieval behavior. Explicit
    empty lists or unknown values are rejected so callers cannot silently
    degrade to all-source retrieval.
    """
    if targets is None:
        return _ALL_RETRIEVAL_TARGETS
    if not targets:
        raise ValueError("retrieval targets cannot be empty")

    validated: list[RetrievalTarget] = []
    for target in targets:
        try:
            validated.append(
                target
                if isinstance(target, RetrievalTarget)
                else RetrievalTarget(str(target))
            )
        except ValueError as exc:
            raise ValueError(f"unsupported retrieval target: {target}") from exc
    return frozenset(validated)


def _targets_for_item(item: "LinkedItem") -> list[RetrievalTarget]:
    """Infer default target metadata for legacy or test-created items."""
    targets: set[RetrievalTarget] = set(item.targets)

    if item.source_type in _GRAPH_ONLY_SOURCE_TYPES:
        targets.add(RetrievalTarget.GRAPH_NEIGHBORHOOD)
        if item.source_type == "decision":
            targets.add(RetrievalTarget.DECISION_RECEIPTS)

    for signal in item.signals:
        if signal.startswith("graph:"):
            targets.add(RetrievalTarget.GRAPH_NEIGHBORHOOD)
            if item.source_type == "decision":
                targets.add(RetrievalTarget.DECISION_RECEIPTS)
        elif signal in ("explicit_link", "explicit_reference"):
            targets.update(_SOURCE_RETRIEVAL_TARGETS)
        elif signal == "hybrid_search":
            targets.update(_SOURCE_RETRIEVAL_TARGETS)

    if not targets:
        targets.update(_SOURCE_RETRIEVAL_TARGETS)

    return sorted(targets, key=lambda target: target.value)


def _ensure_item_retrieval_metadata(item: "LinkedItem") -> None:
    if not item.targets:
        item.targets = _targets_for_item(item)
    item.metadata.setdefault(
        "retrieval_targets",
        [target.value for target in item.targets],
    )
    item.metadata.setdefault("retrieval_signals", list(item.signals))


def _item_matches_targets(
    item: "LinkedItem",
    requested_targets: frozenset[RetrievalTarget],
) -> bool:
    _ensure_item_retrieval_metadata(item)
    return any(target in requested_targets for target in item.targets)


def _source_group_for_type(source_type: str) -> str | None:
    for source_name, source_types in SOURCE_TYPE_MAP.items():
        if source_type in source_types:
            return source_name
    if source_type in _GRAPH_ONLY_SOURCE_TYPES:
        return "graph"
    return None


def _source_group_matches_connected_sources(
    item: "LinkedItem",
    connected_sources: set[str] | None,
) -> bool:
    if connected_sources is None:
        return True
    source_group = _source_group_for_type(item.source_type)
    if source_group == "graph":
        return True
    return source_group in connected_sources


@dataclass
class LinkedItem:
    """A piece of content linked to a ticket with relevance scoring."""

    source_type: str
    source_id: UUID
    title: str
    snippet: str
    relevance_score: float
    signals: list[str] = field(default_factory=list)
    url: str | None = None
    targets: list[RetrievalTarget] = field(default_factory=list)
    features: RetrievalFeatures = field(default_factory=RetrievalFeatures)
    metadata: dict = field(default_factory=dict)


@dataclass
class CommunityContext:
    """A community surfaced for synthesis prompt rendering.

    Communities are clusters discovered by nightly Louvain. Synthesis picks
    up to N relevant ones (assignee's home cluster + clusters with multiple
    retrieved-item members) and renders a "Team & Feature Context" section.
    """

    community_id: int
    label: str | None
    summary: str | None
    person_count: int
    ticket_count: int
    member_count: int
    top_member_names: list[str]
    relevance_reason: str  # "assignee_primary" | "retrieved_member"


@dataclass
class LinkingResult:
    """Result of finding related content for a ticket."""

    ticket_id: UUID
    ticket_identifier: str
    items: list[LinkedItem] = field(default_factory=list)
    communities: list[CommunityContext] = field(default_factory=list)


async def _find_explicit_refs(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
    connected_sources: set[str] | None = None,
) -> dict[tuple[str, UUID], LinkedItem]:
    """Find content with explicit references to the ticket.

    The ``ticket`` param may be a real LinearTicket or a TicketProxy wrapping
    a Jira issue.  FK-based lookups (GitHub PRs, GitLab MRs, Linear comments)
    only work for Linear tickets because the FK columns reference
    linear_tickets.id.  For Jira tickets we query Jira comments instead.
    """
    items: dict[tuple[str, UUID], LinkedItem] = {}
    is_linear = isinstance(ticket, LinearTicket)

    # 1. GitHub PRs linked via FK (linear_ticket_id or jira_issue_id)
    if connected_sources is None or "github" in connected_sources:
        if is_linear:
            pr_fk_filter = GithubPullRequest.linear_ticket_id == ticket.id
        else:
            pr_fk_filter = GithubPullRequest.jira_issue_id == ticket.id

        pr_stmt = select(GithubPullRequest).where(
            GithubPullRequest.workspace_id == workspace_id,
            pr_fk_filter,
            GithubPullRequest.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        pr_result = await session.execute(pr_stmt)
        for pr in pr_result.scalars().all():
            key = ("github_pull_request", pr.id)
            pr_url = f"https://github.com/{pr.repo_full_name}/pull/{pr.number}"
            pr_state = "merged" if pr.github_merged_at else pr.state
            pr_snippet = f"**URL:** {pr_url}\n**State:** {pr_state} | **Author:** {pr.author} | **Branch:** {pr.branch_name} → {pr.base_branch}\n{(pr.description or '')[:200]}"
            items[key] = LinkedItem(
                source_type="github_pull_request",
                source_id=pr.id,
                title=f"PR #{pr.number}: {pr.title}",
                snippet=pr_snippet,
                relevance_score=WEIGHT_EXPLICIT,
                signals=["explicit_link"],
                url=pr_url,
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

    # 2. GitLab MRs linked via FK (linear_ticket_id or jira_issue_id)
    if connected_sources is None or "gitlab" in connected_sources:
        if is_linear:
            mr_fk_filter = GitlabMergeRequest.linear_ticket_id == ticket.id
        else:
            mr_fk_filter = GitlabMergeRequest.jira_issue_id == ticket.id

        gl_mr_stmt = select(GitlabMergeRequest).where(
            GitlabMergeRequest.workspace_id == workspace_id,
            mr_fk_filter,
            GitlabMergeRequest.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        gl_mr_result = await session.execute(gl_mr_stmt)
        for mr in gl_mr_result.scalars().all():
            key = ("gitlab_merge_request", mr.id)
            mr_url = f"https://gitlab.com/{mr.project_path}/-/merge_requests/{mr.iid}"
            mr_state = "merged" if mr.gitlab_merged_at else mr.state
            mr_snippet = f"**URL:** {mr_url}\n**State:** {mr_state} | **Author:** {mr.author} | **Branch:** {mr.source_branch} → {mr.target_branch}\n{(mr.description or '')[:200]}"
            items[key] = LinkedItem(
                source_type="gitlab_merge_request",
                source_id=mr.id,
                title=f"MR !{mr.iid}: {mr.title}",
                snippet=mr_snippet,
                relevance_score=WEIGHT_EXPLICIT,
                signals=["explicit_link"],
                url=mr_url,
            )

            # Also find reviews on linked MRs
            gl_review_stmt = select(GitlabReview).where(
                GitlabReview.merge_request_id == mr.id,
                GitlabReview.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            gl_review_result = await session.execute(gl_review_stmt)
            for review in gl_review_result.scalars().all():
                if review.body:
                    rkey = ("gitlab_review", review.id)
                    items[rkey] = LinkedItem(
                        source_type="gitlab_review",
                        source_id=review.id,
                        title=f"Review by {review.author} ({review.state})",
                        snippet=(review.body or "")[:200],
                        relevance_score=WEIGHT_EXPLICIT,
                        signals=["explicit_link"],
                    )

    # 3. Ticket comments via FK
    if is_linear and (connected_sources is None or "linear" in connected_sources):
        # Linear comments linked via ticket_id FK
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
                url=f"https://linear.app/issue/{ticket.identifier}",
            )
    elif not is_linear and (connected_sources is None or "jira" in connected_sources):
        # Jira comments linked via issue_id FK
        jira_comment_stmt = select(JiraComment).where(
            JiraComment.issue_id == ticket.id,
            JiraComment.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        jira_comment_result = await session.execute(jira_comment_stmt)
        for comment in jira_comment_result.scalars().all():
            if comment.body:
                key = ("jira_comment", comment.id)
                items[key] = LinkedItem(
                    source_type="jira_comment",
                    source_id=comment.id,
                    title=f"Comment by {comment.author_name or 'Unknown'}",
                    snippet=comment.body[:200],
                    relevance_score=WEIGHT_EXPLICIT,
                    signals=["explicit_link"],
                )

    # 4. Slack messages containing the ticket identifier
    if connected_sources is None or "slack" in connected_sources:
        # TODO: PERF-03 — The ILIKE '%...%' below triggers a sequential scan because
        # there is no index on slack_messages.text for leading-wildcard patterns.
        # For workspaces with many Slack messages this becomes a bottleneck.
        # Recommended fix: create a GIN trigram index
        #   CREATE INDEX idx_slack_messages_text_trgm ON slack_messages
        #     USING gin (text gin_trgm_ops);
        # or delegate to the hybrid_search() function which already uses the
        # embeddings GIN index.  Deferred from this hardening phase to avoid
        # schema churn — tracked for a future migration.
        # Cap fan-out: every match below also triggers a chat.getPermalink
        # call (Tier 4, ~100/min). A popular ticket identifier could
        # otherwise issue hundreds of concurrent Slack API calls and risk
        # 429s. Newest-first so we keep the most relevant matches.
        slack_stmt = (
            select(SlackMessage)
            .where(
                SlackMessage.workspace_id == workspace_id,
                SlackMessage.text.ilike(f"%{ticket.identifier}%"),  # type: ignore[union-attr]
                SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            .order_by(SlackMessage.slack_created_at.desc().nullslast())  # type: ignore[union-attr]
            .limit(HYBRID_SEARCH_LIMIT)
        )
        slack_result = await session.execute(slack_stmt)
        slack_msgs = slack_result.scalars().all()

        # Resolve canonical workspace permalinks via chat.getPermalink. A
        # hand-built https://slack.com/archives/... URL opens whichever
        # workspace the viewer is signed into, not the message's workspace.
        #
        # Read the bot token once here and pass it down, rather than letting
        # each resolve_slack_permalink() fetch it: that would add one Vault
        # read per Slack message to this hot path. If there's no token (Slack
        # not connected / revoked) we skip resolution entirely and every
        # message falls back to the bare URL.
        bot_token: str | None = None
        if slack_msgs:
            from src.services.slack_oauth import SlackOAuthError, get_bot_token

            try:
                bot_token = await get_bot_token(session, workspace_id)
            except SlackOAuthError:
                logger.debug(
                    "No Slack bot token for workspace %s; "
                    "Slack permalinks will use bare URLs",
                    workspace_id,
                )

        from src.services.slack_events import resolve_slack_permalink

        # Concurrent + cached + fail-silent, so a page with many Slack
        # sources doesn't serialize N chat.getPermalink round-trips.
        permalinks = await asyncio.gather(
            *(
                resolve_slack_permalink(
                    session,
                    workspace_id,
                    msg.channel_id,
                    msg.slack_ts,
                    token=bot_token,
                )
                for msg in slack_msgs
            ),
            return_exceptions=True,
        ) if bot_token else [None] * len(slack_msgs)

        for msg, resolved in zip(slack_msgs, permalinks):
            key = ("slack_message", msg.id)
            # Fall back to the bare URL when resolution fails; still better
            # than no link, and correct for single-workspace viewers.
            fallback = slack_archive_url(msg.channel_id, msg.slack_ts)
            slack_permalink = (
                resolved if isinstance(resolved, str) and resolved else fallback
            )
            items[key] = LinkedItem(
                source_type="slack_message",
                source_id=msg.id,
                title=f"Slack message by {msg.user_name or 'Unknown'} in #{msg.channel_name or 'unknown'}",
                snippet=msg.text[:200],
                relevance_score=WEIGHT_EXPLICIT,
                signals=["explicit_reference"],
                url=slack_permalink,
            )

    # 5. Telegram messages containing the ticket identifier
    if connected_sources is None or "telegram" in connected_sources:
        tg_stmt = select(TelegramMessage).where(
            TelegramMessage.workspace_id == workspace_id,
            TelegramMessage.text.ilike(f"%{ticket.identifier}%"),  # type: ignore[union-attr]
            TelegramMessage.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        tg_result = await session.execute(tg_stmt)
        for msg in tg_result.scalars().all():
            key = ("telegram_message", msg.id)
            items[key] = LinkedItem(
                source_type="telegram_message",
                source_id=msg.id,
                title=f"Telegram by {msg.from_first_name or msg.from_username or 'Unknown'} in {msg.chat_title or 'DM'}",
                snippet=msg.text[:200],
                relevance_score=WEIGHT_EXPLICIT,
                signals=["explicit_reference"],
            )

    for item in items.values():
        _ensure_item_retrieval_metadata(item)
    return items


async def _find_hybrid_matches(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
    connected_sources: set[str] | None = None,
) -> dict[tuple[str, UUID], LinkedItem]:
    """Find related content via hybrid vector + full-text search."""
    items: dict[tuple[str, UUID], LinkedItem] = {}

    # Build allowed source_types from connected_sources for post-filtering
    allowed_types: set[str] | None = None
    if connected_sources is not None:
        allowed_types = set()
        for src_name, src_types in SOURCE_TYPE_MAP.items():
            if src_name in connected_sources:
                allowed_types.update(src_types)

    query_text = f"{ticket.title}\n\n{ticket.description or ''}"

    # HyDE: Generate a hypothetical context document from the ticket, then embed
    # that instead of the raw query. This produces embeddings closer to actual
    # documents in the vector space, dramatically improving retrieval recall.
    hyde_text = query_text
    try:
        llm = get_llm_client()
        hyde_response = await llm.generate(
            prompt=f"Ticket: {ticket.title}\nDescription: {ticket.description or 'No description'}\n\nWrite a short technical summary (3-4 sentences) of what this ticket is about, what code or systems it might involve, and what decisions or discussions might exist around it.",
            system_prompt="You are a technical writer. Write a brief hypothetical context document based on the ticket. Be specific about technologies, components, and potential discussions. Do not use markdown formatting.",
        )
        if hyde_response.text:
            hyde_text = f"{query_text}\n\n{hyde_response.text}"
    except Exception:
        logger.debug("HyDE generation failed for %s, using raw query", ticket.identifier)

    try:
        query_embedding = await generate_embedding(hyde_text)
    except Exception:
        logger.warning("Failed to generate query embedding for %s", ticket.identifier)
        return items

    if not query_embedding or all(v == 0.0 for v in query_embedding):
        return items

    # Call hybrid_search() SQL function — use a low floor to exclude noise,
    # but rely primarily on top-k ranking rather than a strict threshold.
    # We run two searches: one general (all types) and one dedicated for
    # code_chunk, because code chunks would otherwise be crowded out when
    # other source types (MRs, comments, messages) fill the top-k slots.
    match_stmt = text("""
        SELECT id, source_type, source_id, similarity, keyword_rank, combined_score, metadata
        FROM hybrid_search(
            CAST(:query_embedding AS vector),
            :query_text,
            CAST(:workspace_id AS uuid),
            :source_type,
            0.7,
            0.3,
            :floor,
            :limit
        )
    """)

    common_params = {
        "query_embedding": str(query_embedding),
        "query_text": ticket.title,
        "workspace_id": str(workspace_id),
        "floor": HYBRID_SCORE_FLOOR,
    }

    # General search (all source types)
    result = await session.execute(
        match_stmt,
        {**common_params, "source_type": None, "limit": HYBRID_SEARCH_LIMIT},
    )

    # Collect all hybrid hits first (skip self-matches)
    hits: list[tuple[str, UUID, float]] = []
    seen_keys: set[tuple[str, UUID]] = set()
    for row in result.fetchall():
        source_type = row[1]
        source_id = row[2]
        combined_score = row[5]

        # Skip self-match (the ticket itself appearing as a search hit)
        if source_id == ticket.id and source_type in ("linear_ticket", "jira_issue"):
            continue

        # Skip hits from disconnected sources
        if allowed_types is not None and source_type not in allowed_types:
            continue

        hits.append((source_type, source_id, combined_score))
        seen_keys.add((source_type, source_id))

    # Dedicated code_chunk search — ensures code results aren't crowded out
    # by higher-scoring MRs/comments in the general search.
    if allowed_types is None or "code_chunk" in allowed_types:
        code_result = await session.execute(
            match_stmt,
            {**common_params, "source_type": "code_chunk", "limit": HYBRID_SEARCH_CODE_LIMIT},
        )
        for row in code_result.fetchall():
            source_type = row[1]
            source_id = row[2]
            key = (source_type, source_id)
            if key in seen_keys:
                continue
            hits.append((source_type, source_id, row[5]))
            seen_keys.add(key)

    # Bulk-fetch summaries for all hits
    summaries = await _bulk_lookup_source_summaries(
        session, [(st, sid) for st, sid, _ in hits]
    )

    for source_type, source_id, combined_score in hits:
        key = (source_type, source_id)

        # Skip hits whose source record no longer exists in the DB.
        # This happens when an embedding references a deleted/missing record.
        if key not in summaries:
            logger.debug(
                "Dropping hybrid hit %s/%s — source record not found",
                source_type, source_id,
            )
            continue

        title, snippet, url = summaries[key]
        score = combined_score * WEIGHT_HYBRID

        items[key] = LinkedItem(
            source_type=source_type,
            source_id=source_id,
            title=title,
            snippet=snippet,
            relevance_score=score,
            signals=["hybrid_search"],
            url=url,
        )

    for item in items.values():
        _ensure_item_retrieval_metadata(item)
    return items


# Map source_type -> (model class, title+snippet extractor)
_SOURCE_SUMMARY_MAP: dict[str, tuple] = {
    "linear_ticket": (
        LinearTicket,
        lambda r: (r.title, (r.description or "")[:200]),
        lambda r: f"https://linear.app/issue/{r.identifier}",
    ),
    "linear_comment": (
        LinearComment,
        lambda r: (f"Comment by {r.author_name or 'Unknown'}", r.body[:200]),
        lambda r: f"https://linear.app/issue/{r.raw_data.get('issue', {}).get('identifier', '')}" if r.raw_data.get("issue") else None,
    ),
    "slack_message": (
        SlackMessage,
        lambda r: (
            f"Slack by {r.user_name or 'Unknown'} in #{r.channel_name or 'unknown'}",
            r.text[:200],
        ),
        lambda r: slack_archive_url(r.channel_id, r.slack_ts),
    ),
    "meeting_transcript": (
        MeetingTranscript,
        lambda r: (f"Meeting: {r.title or 'Untitled'}", r.transcript[:200]),
        None,
    ),
    "meeting_segment": (
        MeetingSegment,
        lambda r: (
            f"Segment by {r.speaker_name or 'Unknown'}",
            r.text[:200],
        ),
        None,
    ),
    "github_pull_request": (
        GithubPullRequest,
        lambda r: (
            f"PR #{r.number}: {r.title}",
            f"**URL:** https://github.com/{r.repo_full_name}/pull/{r.number}\n"
            f"**State:** {'merged' if r.github_merged_at else r.state} | **Author:** {r.author} | **Branch:** {r.branch_name} → {r.base_branch}\n"
            f"{(r.description or '')[:200]}",
        ),
        lambda r: f"https://github.com/{r.repo_full_name}/pull/{r.number}",
    ),
    "github_review": (
        GithubReview,
        lambda r: (
            f"Review by {r.author} ({r.state})",
            (r.body or "")[:200],
        ),
        None,
    ),
    "notion_page": (
        NotionPage,
        lambda r: (r.title, (r.content or "")[:200]),
        lambda r: r.url,
    ),
    "gitlab_merge_request": (
        GitlabMergeRequest,
        lambda r: (
            f"MR !{r.iid}: {r.title}",
            f"**URL:** https://gitlab.com/{r.project_path}/-/merge_requests/{r.iid}\n"
            f"**State:** {'merged' if r.gitlab_merged_at else r.state} | **Author:** {r.author} | **Branch:** {r.source_branch} → {r.target_branch}\n"
            f"{(r.description or '')[:200]}",
        ),
        lambda r: f"https://gitlab.com/{r.project_path}/-/merge_requests/{r.iid}",
    ),
    "gitlab_review": (
        GitlabReview,
        lambda r: (
            f"Review by {r.author} ({r.state})",
            (r.body or "")[:200],
        ),
        None,
    ),
    "code_chunk": (
        CodeChunk,
        lambda r: (
            f"{r.symbol_type}: {r.symbol_name} ({r.repo_full_name}:{r.file_path})",
            r.content[:200],
        ),
        None,
    ),
    "telegram_message": (
        TelegramMessage,
        lambda r: (
            f"Telegram by {r.from_first_name or r.from_username or 'Unknown'} in {r.chat_title or 'DM'}",
            r.text[:200],
        ),
        None,
    ),
    "jira_issue": (
        JiraIssue,
        lambda r: (f"{r.jira_key}: {r.summary}", (r.description or "")[:200]),
        lambda r: r.raw_data.get("url") or (f"{r.raw_data['self'].split('/rest/')[0]}/browse/{r.jira_key}" if r.raw_data.get("self") else None),
    ),
    "jira_comment": (
        JiraComment,
        lambda r: (f"Jira comment by {r.author_name or 'Unknown'}", (r.body or "")[:200]),
        None,
    ),
}


async def _bulk_lookup_source_summaries(
    session: AsyncSession,
    keys: list[tuple[str, UUID]],
) -> dict[tuple[str, UUID], tuple[str, str, str | None]]:
    """Bulk-fetch title/snippet/url for multiple source records.

    Privacy-aware: first tries to read from embedding metadata (which
    persists after raw content deletion), then falls back to source tables.
    """
    from src.models.embedding import Embedding

    result_map: dict[tuple[str, UUID], tuple[str, str, str | None]] = {}
    if not keys:
        return result_map

    # Group IDs by source_type
    grouped: dict[str, list[UUID]] = {}
    for source_type, source_id in keys:
        grouped.setdefault(source_type, []).append(source_id)

    # Phase 1: Try embedding metadata first (works even after raw content deletion)
    all_ids = [sid for _, sid in keys]
    if all_ids:
        emb_stmt = select(Embedding).where(
            Embedding.source_id.in_(all_ids),
            Embedding.deleted_at.is_(None),
        )
        emb_result = await session.execute(emb_stmt)
        for emb in emb_result.scalars().all():
            meta = emb.metadata_ or {}
            if meta.get("title") and meta.get("snippet"):
                key = (emb.source_type, emb.source_id)
                result_map[key] = (meta["title"], meta["snippet"], meta.get("url"))

    # Phase 2: Fall back to source tables for any records not found in metadata
    for source_type, ids in grouped.items():
        fallback_ids = [sid for sid in ids if (source_type, sid) not in result_map]
        if not fallback_ids or source_type not in _SOURCE_SUMMARY_MAP:
            continue

        model_cls, extract, url_fn = _SOURCE_SUMMARY_MAP[source_type]
        stmt = select(model_cls).where(model_cls.id.in_(fallback_ids))  # type: ignore[union-attr]
        db_result = await session.execute(stmt)
        records = db_result.scalars().all()

        for record in records:
            title, snippet = extract(record)
            url = url_fn(record) if url_fn else None
            result_map[(source_type, record.id)] = (title, snippet, url)

    return result_map


async def _lookup_source_summary(
    session: AsyncSession,
    source_type: str,
    source_id: UUID,
) -> tuple[str, str] | None:
    """Look up a human-readable title and snippet for a single source record.

    Returns None if the source type is unknown or the record doesn't exist.
    Uses the shared _SOURCE_SUMMARY_MAP. Prefer _bulk_lookup_source_summaries
    when fetching multiple records to avoid N+1 queries.
    """
    if source_type not in _SOURCE_SUMMARY_MAP:
        return None

    model_cls, extract, _url_fn = _SOURCE_SUMMARY_MAP[source_type]
    stmt = select(model_cls).where(model_cls.id == source_id)
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record is None:
        return None
    return extract(record)


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, tuple | set):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _decision_verification_state(properties: dict) -> VerificationState:
    source_type = str(properties.get("source_type") or properties.get("source") or "")
    source_quote = properties.get("source_quote")
    source_link = properties.get("source_link")
    status = str(properties.get("status") or "").lower()

    if source_type == "context_page":
        return VerificationState.GENERATED_CONTEXT
    if status == "confirmed" and source_quote and source_link:
        return VerificationState.CONFIRMED_DECISION
    if source_quote and source_link:
        return VerificationState.SOURCE_BACKED_CANDIDATE
    return VerificationState.UNKNOWN


def _format_decision_graph_item(
    *,
    name: str,
    properties: dict,
    score: float,
    provenance: str,
    source_id: UUID,
    graph_depth: int,
) -> LinkedItem:
    """Render a graph Decision node using Phase 45 promoted properties first."""
    verification_state = _decision_verification_state(properties)
    person = (
        properties.get("person_name")
        or next(iter(_as_list(properties.get("participants"))), None)
        or properties.get("by")
        or "Unknown"
    )
    source_type = (
        "generated_context"
        if verification_state == VerificationState.GENERATED_CONTEXT
        else properties.get("source_type")
        or properties.get("source")
        or "Unknown"
    )
    affected = (
        _as_list(properties.get("affected_systems"))
        or _as_list(properties.get("ticket_refs"))
        or _as_list(properties.get("affects"))
    )
    source_quote = properties.get("source_quote")
    source_link = properties.get("source_link")
    confidence = properties.get("confidence", "N/A")

    parts = [f"[DECISION] {name}", f"By: {person}", f"In: {source_type}"]
    if affected:
        parts.append(f"Affects: {', '.join(affected)}")
    if source_quote:
        parts.append(f"Quote: {source_quote}")
    if source_link:
        parts.append(f"Source: {source_link}")
    parts.append(f"Confidence: {confidence}")

    targets = [RetrievalTarget.DECISION_RECEIPTS, RetrievalTarget.GRAPH_NEIGHBORHOOD]
    if verification_state in (
        VerificationState.CONFIRMED_DECISION,
        VerificationState.SOURCE_BACKED_CANDIDATE,
    ):
        targets.append(RetrievalTarget.SOURCE_EVIDENCE)

    item = LinkedItem(
        source_type="decision",
        source_id=source_id,
        title=name,
        snippet=" | ".join(parts),
        relevance_score=score,
        signals=[provenance],
        url=str(source_link) if source_link else None,
        targets=targets,
        features=RetrievalFeatures(
            verification_state=verification_state,
            graph_depth=graph_depth,
        ),
        metadata={
            "source_type": source_type,
            "person_name": str(person),
            "source_quote": str(source_quote) if source_quote else None,
            "source_link": str(source_link) if source_link else None,
            "provenance_label": verification_state.value,
            "status": properties.get("status"),
        },
    )
    _ensure_item_retrieval_metadata(item)
    return item


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
                    GraphNode.workspace_id == workspace_id,
                    GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
                )
            )
            for nid, sid in source_lookup.fetchall():
                node_source_map[nid] = sid

        # 5. Process each result row
        source_backed_keys: list[tuple[str, UUID]] = []
        pending: list[tuple[tuple[str, UUID], float, str, str, int]] = []

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
                pending.append((key, score, provenance, row.name, effective_depth))
            elif entity_type in _GRAPH_ONLY_ENTITIES:
                # Graph-only entities use node_id as source_id
                source_type = entity_type.lower()
                source_id = row.node_id
                key = (source_type, source_id)

                # Special formatting for Decision nodes
                if entity_type == "Decision":
                    props = row.properties or {}
                    items[key] = _format_decision_graph_item(
                        name=row.name,
                        properties=props,
                        score=score,
                        provenance=provenance,
                        source_id=source_id,
                        graph_depth=effective_depth,
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
                        targets=[RetrievalTarget.GRAPH_NEIGHBORHOOD],
                        features=RetrievalFeatures(
                            verification_state=VerificationState.UNKNOWN,
                            graph_depth=effective_depth,
                        ),
                    )

        # 6. Bulk-fetch summaries for source-backed entities
        if source_backed_keys:
            summaries = await _bulk_lookup_source_summaries(
                session, source_backed_keys
            )

            for key, score, provenance, node_name, graph_depth in pending:
                title, snippet, url = summaries.get(key, (key[0], "", None))
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
                    url=url,
                    targets=[
                        RetrievalTarget.GRAPH_NEIGHBORHOOD,
                        RetrievalTarget.SOURCE_EVIDENCE,
                    ],
                    features=RetrievalFeatures(
                        verification_state=VerificationState.SOURCE_EVIDENCE,
                        graph_depth=graph_depth,
                    ),
                )

    except Exception:
        logger.warning(
            "Graph traversal failed for ticket %s, falling back to empty graph results",
            ticket.identifier,
        )
        return {}

    for item in items.values():
        _ensure_item_retrieval_metadata(item)
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
    "github": ["github_pull_request", "github_review"],
    "gitlab": ["gitlab_merge_request", "gitlab_review"],
    "code": ["code_chunk"],
    "notion": ["notion_page"],
    "fathom": ["meeting_transcript", "meeting_segment"],
    "slack_huddle": ["meeting_transcript", "meeting_segment"],
    "linear": ["linear_comment"],
    "telegram": ["telegram_message"],
    "jira": ["jira_issue", "jira_comment"],
}


async def find_content_by_source(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
    connected_sources: set[str] | None = None,
    targets: list[RetrievalTarget] | None = None,
) -> AsyncGenerator[tuple[str, list[LinkedItem], str], None]:
    """Find related content and yield results grouped by source.

    Yields (source_name, items, detail_string) tuples for each source
    that has content. Runs all queries upfront, then groups by source.

    Args:
        connected_sources: If provided, skip queries for source types
            not in this set.  When ``None``, query all sources (backward
            compatible).  Source names match keys in ``SOURCE_TYPE_MAP``.
    """
    requested_targets = _validate_retrieval_targets(targets)
    result = await _collect_targeted_linked_items(
        session,
        workspace_id,
        ticket,
        requested_targets=requested_targets,
        connected_sources=connected_sources,
    )
    merged_items = result.items

    def _source_targets(source_name: str) -> set[RetrievalTarget]:
        if source_name == "graph":
            return {
                RetrievalTarget.GRAPH_NEIGHBORHOOD,
                RetrievalTarget.DECISION_RECEIPTS,
            }
        return {
            RetrievalTarget.SOURCE_EVIDENCE,
            RetrievalTarget.RELATED_WORK,
        }

    # Group by source — skip disconnected providers when caller provides the set
    for source_name, source_types in SOURCE_TYPE_MAP.items():
        if connected_sources is not None and source_name not in connected_sources:
            continue

        source_items = [
            item for item in merged_items
            if item.source_type in source_types
        ]
        source_items.sort(key=lambda x: x.relevance_score, reverse=True)

        # Build detail string
        if not (_source_targets(source_name) & set(requested_targets)):
            detail = "Target not requested"
        elif source_name == "github":
            prs = sum(1 for i in source_items if i.source_type == "github_pull_request")
            reviews = sum(1 for i in source_items if i.source_type == "github_review")
            parts = []
            if prs:
                parts.append(f"{prs} PR{'s' if prs > 1 else ''}")
            if reviews:
                parts.append(f"{reviews} review{'s' if reviews > 1 else ''}")
            detail = f"Found {', '.join(parts)}" if parts else "No PRs found"
        elif source_name == "slack":
            n = len(source_items)
            detail = f"Found {n} message{'s' if n != 1 else ''}" if n else "No messages found"
        elif source_name == "notion":
            n = len(source_items)
            detail = f"Found {n} page{'s' if n != 1 else ''}" if n else "No pages found"
        elif source_name == "gitlab":
            mrs = sum(1 for i in source_items if i.source_type == "gitlab_merge_request")
            reviews = sum(1 for i in source_items if i.source_type == "gitlab_review")
            parts = []
            if mrs:
                parts.append(f"{mrs} MR{'s' if mrs > 1 else ''}")
            if reviews:
                parts.append(f"{reviews} review{'s' if reviews > 1 else ''}")
            detail = f"Found {', '.join(parts)}" if parts else "No MRs found"
        elif source_name == "code":
            n = len(source_items)
            detail = f"Found {n} code file{'s' if n != 1 else ''}" if n else "No code found"
        elif source_name in ("fathom", "slack_huddle"):
            n = len(source_items)
            detail = f"Found {n} meeting segment{'s' if n != 1 else ''}" if n else "No meetings found"
        elif source_name == "linear":
            n = len(source_items)
            detail = f"Found {n} comment{'s' if n != 1 else ''}" if n else "No comments found"
        elif source_name == "telegram":
            n = len(source_items)
            detail = f"Found {n} message{'s' if n != 1 else ''}" if n else "No messages found"
        elif source_name == "jira":
            n = len(source_items)
            detail = f"Found {n} item{'s' if n != 1 else ''}" if n else "No items found"
        else:
            detail = f"Found {len(source_items)} items" if source_items else "No items found"

        yield source_name, source_items, detail

    graph_items = [
        item for item in merged_items
        if _source_group_for_type(item.source_type) == "graph"
    ]
    if graph_items:
        graph_items.sort(key=lambda x: x.relevance_score, reverse=True)
        detail = (
            f"Found {len(graph_items)} graph item"
            f"{'s' if len(graph_items) != 1 else ''}"
        )
        yield "graph", graph_items, detail


async def _llm_rerank(
    ticket: LinearTicket,
    items: list[LinkedItem],
    top_n: int = 30,
) -> list[LinkedItem]:
    """Rerank retrieved items using LLM-based relevance scoring.

    Sends the top candidates to Gemini with the ticket query and asks it to
    score each item's relevance from 0-10. This cross-encoder-style approach
    evaluates query-document pairs jointly, producing much better relevance
    scores than independent retrieval-time heuristics.

    Falls back to original scores if LLM reranking fails.
    """
    if not items or len(items) <= 3:
        return items

    # Only rerank the top candidates to limit cost/latency
    candidates = sorted(items, key=lambda x: x.relevance_score, reverse=True)[:top_n]
    remaining = items[top_n:] if len(items) > top_n else []

    # Build item descriptions for the LLM
    item_lines = []
    for i, item in enumerate(candidates):
        item_lines.append(f"[{i}] ({item.source_type}) {item.title}: {item.snippet[:150]}")

    prompt = (
        f"Ticket: {ticket.title}\n"
        f"Description: {(ticket.description or 'No description')[:300]}\n\n"
        f"Rate each item's relevance to this ticket from 0 (irrelevant) to 10 (directly relevant).\n"
        f"Return ONLY a comma-separated list of scores in order, e.g.: 8,3,9,1,7\n\n"
        + "\n".join(item_lines)
    )

    try:
        llm = get_llm_client()
        response = await llm.generate(
            prompt=prompt,
            system_prompt="You are a relevance scorer. Return ONLY comma-separated integer scores 0-10, nothing else.",
        )

        scores_text = response.text.strip()
        scores = [int(s.strip()) for s in scores_text.split(",") if s.strip().isdigit()]

        if len(scores) == len(candidates):
            for item, score in zip(candidates, scores):
                item.relevance_score = score / 10.0
        else:
            logger.debug("LLM rerank returned %d scores for %d items, skipping", len(scores), len(candidates))
    except Exception:
        logger.debug("LLM reranking failed, using original scores")

    return candidates + remaining


MAX_COMMUNITIES_IN_PROMPT = 3


def _select_communities(
    candidates: list[CommunityContext],
    max_communities: int = MAX_COMMUNITIES_IN_PROMPT,
) -> list[CommunityContext]:
    """Pick the top communities for the synthesis prompt.

    Order: assignee_primary first (always at index 0 if present),
    then retrieved_member sorted by member_count descending. Cap at max.
    """
    primary = [c for c in candidates if c.relevance_reason == "assignee_primary"]
    others = [c for c in candidates if c.relevance_reason != "assignee_primary"]
    others.sort(key=lambda c: c.member_count, reverse=True)
    chosen = (primary + others)[:max_communities]
    return chosen


async def _fetch_communities_for_ticket(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
    items: list[LinkedItem],
) -> list[CommunityContext]:
    """Resolve up to MAX_COMMUNITIES_IN_PROMPT relevant communities.

    Strategy:
    1. Find the ticket's graph node by fingerprint (ticket.identifier), then follow
       an assigned_to edge to the canonical Person node and read its community_id.
       (Person nodes use external_id="canonical:<uuid>"; there is no email-based
       fingerprint in this codebase — assignee links are created via identity
       mapping lookups during Linear sync.)
    2. For each retrieved item that's a ticket source (linear_ticket / jira_issue),
       look up the GraphNode by source_id and tally community_id occurrences. Any
       community with >=2 distinct retrieved-item members gets tagged "retrieved_member".
    3. Look up labels/summaries from graph_communities. Drop NULL-summary entries.

    Failure modes (missing tables, DB errors) return [] so synthesis silently degrades.
    """
    from collections import Counter

    from sqlalchemy.exc import OperationalError, ProgrammingError

    from src.models.graph_community import GraphCommunity
    from src.models.graph_edge import GraphEdge

    try:
        # 1. Assignee primary community: find ticket node, follow assigned_to edge
        #    to canonical Person node, read community_id.
        #    Person nodes in this codebase use external_id="canonical:<uuid>",
        #    not email-based fingerprints. The graph edge (assigned_to) is the
        #    reliable link from ticket -> person.
        assignee_community_id: int | None = None
        ticket_fp = compute_fingerprint("Ticket", ticket.identifier)
        ticket_node_stmt = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.fingerprint == ticket_fp,
            GraphNode.deleted_at.is_(None),
        )
        ticket_node_res = await session.execute(ticket_node_stmt)
        ticket_graph_node = ticket_node_res.scalar_one_or_none()

        if ticket_graph_node is not None:
            # Find Person node connected via assigned_to edge from the ticket node
            edge_stmt = select(GraphEdge).where(
                GraphEdge.workspace_id == workspace_id,
                GraphEdge.source_node_id == ticket_graph_node.id,
                GraphEdge.relationship_type == "assigned_to",
            )
            edge_res = await session.execute(edge_stmt)
            assignee_edge = edge_res.scalar_one_or_none()
            if assignee_edge is not None:
                person_stmt = select(GraphNode).where(
                    GraphNode.workspace_id == workspace_id,
                    GraphNode.id == assignee_edge.target_node_id,
                    GraphNode.entity_type == "Person",
                    GraphNode.deleted_at.is_(None),
                )
                person_res = await session.execute(person_stmt)
                person_node = person_res.scalar_one_or_none()
                if person_node is not None:
                    assignee_community_id = person_node.community_id

        # 2. Tally communities from retrieved items via their source -> graph_node.
        retrieved_community_counts: Counter[int] = Counter()
        item_source_pairs = {
            (it.source_type, it.source_id) for it in items
            if it.source_type in ("linear_ticket", "jira_issue")
        }
        if item_source_pairs:
            ids = [sid for _, sid in item_source_pairs]
            node_stmt = select(GraphNode).where(
                GraphNode.workspace_id == workspace_id,
                GraphNode.source_id.in_(ids),
                GraphNode.community_id.isnot(None),
                GraphNode.deleted_at.is_(None),
            )
            node_res = await session.execute(node_stmt)
            for n in node_res.scalars().all():
                if n.community_id is not None:
                    retrieved_community_counts[n.community_id] += 1

        # 3. Build candidate set.
        candidate_ids: set[int] = set()
        if assignee_community_id is not None:
            candidate_ids.add(assignee_community_id)
        for cid, count in retrieved_community_counts.items():
            if count >= 2:
                candidate_ids.add(cid)
        if not candidate_ids:
            return []

        # 4. Fetch labels/summaries.
        comm_stmt = select(GraphCommunity).where(
            GraphCommunity.workspace_id == workspace_id,
            GraphCommunity.community_id.in_(list(candidate_ids)),
        )
        comm_res = await session.execute(comm_stmt)
        contexts: list[CommunityContext] = []
        for c in comm_res.scalars().all():
            if c.summary is None:  # drop NULL-summary clusters
                continue
            reason = (
                "assignee_primary"
                if c.community_id == assignee_community_id
                else "retrieved_member"
            )
            contexts.append(CommunityContext(
                community_id=c.community_id,
                label=c.label,
                summary=c.summary,
                person_count=c.person_count,
                ticket_count=c.ticket_count,
                member_count=c.member_count,
                top_member_names=list(c.top_member_names or []),
                relevance_reason=reason,
            ))

        return _select_communities(contexts)
    except (OperationalError, ProgrammingError):
        # community_id column or graph_communities table missing — pre-migration env.
        return []
    except Exception:
        logger.warning("Community fetch failed for %s; degrading gracefully",
                       getattr(ticket, "identifier", "?"))
        return []


async def _collect_targeted_linked_items(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
    *,
    requested_targets: frozenset[RetrievalTarget],
    connected_sources: set[str] | None = None,
) -> LinkingResult:
    """Collect related content once using the target-aware retrieval policy."""
    signal_results: list[dict[tuple[str, UUID], LinkedItem]] = []

    if requested_targets & _SOURCE_RETRIEVAL_TARGETS:
        explicit = await _find_explicit_refs(
            session, workspace_id, ticket, connected_sources
        )
        hybrid = await _find_hybrid_matches(
            session, workspace_id, ticket, connected_sources
        )
        signal_results.extend([explicit, hybrid])

    if requested_targets & _GRAPH_RETRIEVAL_TARGETS:
        graph = await _find_graph_results(session, workspace_id, ticket)
        signal_results.append(graph)

    filtered_results: list[dict[tuple[str, UUID], LinkedItem]] = []
    for signal_items in signal_results:
        filtered: dict[tuple[str, UUID], LinkedItem] = {}
        for key, item in signal_items.items():
            if not _item_matches_targets(item, requested_targets):
                continue
            if not _source_group_matches_connected_sources(item, connected_sources):
                item.metadata["route_omission_reason"] = "source_not_connected"
                continue
            filtered[key] = item
        if filtered:
            filtered_results.append(filtered)

    # Merge results using Reciprocal Rank Fusion (RRF) for better ranking.
    merged: dict[tuple[str, UUID], LinkedItem] = {}
    signal_ranked_lists: list[list[tuple[tuple[str, UUID], LinkedItem]]] = []
    for signal_items in filtered_results:
        ranked = sorted(
            signal_items.items(),
            key=lambda x: x[1].relevance_score,
            reverse=True,
        )
        if ranked:
            signal_ranked_lists.append(ranked)

    rrf_scores: dict[tuple[str, UUID], float] = {}
    for ranked_list in signal_ranked_lists:
        for rank, (key, _item) in enumerate(ranked_list):
            rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (RRF_K + rank + 1)

    for signal_items in filtered_results:
        for key, item in signal_items.items():
            _ensure_item_retrieval_metadata(item)
            if key in merged:
                existing = merged[key]
                existing.signals.extend(item.signals)
                for target in item.targets:
                    if target not in existing.targets:
                        existing.targets.append(target)
                existing.metadata["retrieval_targets"] = [
                    target.value for target in existing.targets
                ]
                existing.metadata["retrieval_signals"] = list(existing.signals)
                if not existing.url and item.url:
                    existing.url = item.url
            else:
                merged[key] = item

    if rrf_scores:
        max_rrf = max(rrf_scores.values())
        for key, item in merged.items():
            item.relevance_score = (
                rrf_scores.get(key, 0.0) / max_rrf if max_rrf > 0 else 0.0
            )
            item.features.rrf_score = item.relevance_score

    merged_items = list(merged.values())
    reranked = await _llm_rerank(ticket, merged_items)

    for item in reranked:
        _ensure_item_retrieval_metadata(item)

    budget_trimmed = _apply_token_budget(reranked)
    communities = await _fetch_communities_for_ticket(
        session, workspace_id, ticket, budget_trimmed
    )
    return LinkingResult(
        ticket_id=ticket.id,
        ticket_identifier=ticket.identifier,
        items=budget_trimmed,
        communities=communities,
    )


async def find_related_content(
    session: AsyncSession,
    workspace_id: UUID,
    ticket: LinearTicket,
    targets: list[RetrievalTarget] | None = None,
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
    requested_targets = _validate_retrieval_targets(targets)
    return await _collect_targeted_linked_items(
        session,
        workspace_id,
        ticket,
        requested_targets=requested_targets,
    )
