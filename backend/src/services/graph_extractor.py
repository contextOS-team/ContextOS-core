"""Graph entity extraction: registry pattern with five deterministic regex extractors.

Provides:
  - ExtractedEntity dataclass for extracted graph entities
  - Extractor protocol for pluggable extraction
  - Registry (register_extractor, run_extractors) for composing extractors
  - Five built-in regex extractors: tickets, mentions, PR/commit refs, file paths, URLs
  - extract_and_populate_graph() orchestrator for inline graph population

All extractors are pure functions that take content text and return extracted
entities. No database interaction, no LLM calls -- zero cost extraction.
The orchestrator bridges extractors to graph_ops for persistence.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Source type to entity type mapping for creating source nodes
SOURCE_TYPE_TO_ENTITY: dict[str, str] = {
    "linear_ticket": "Ticket",
    "linear_comment": "Ticket",
    "jira_issue": "Ticket",
    "jira_comment": "Ticket",
    "slack_message": "SlackThread",
    "github_pull_request": "PR",
    "github_review": "PR",
    "notion_page": "NotionPage",
    "meeting_transcript": "Meeting",
    "meeting_segment": "Meeting",
    "code_chunk": "CodeChunk",
    "context_page": "Ticket",
}


# ============================================================
# Data model
# ============================================================


@dataclass
class ExtractedEntity:
    """An entity extracted from content text.

    Attributes:
        entity_type: Graph node type (must match graph_nodes CHECK constraint).
        external_id: External identifier used with entity_type for fingerprint.
        name: Human-readable display name.
        properties: Additional metadata (default empty dict).
        relationship_type: Edge type from source to this entity.
    """

    entity_type: str
    external_id: str
    name: str
    properties: dict = field(default_factory=dict)
    relationship_type: str = "references"


# ============================================================
# Protocol & Registry
# ============================================================


class Extractor(Protocol):
    """Protocol for entity extractors."""

    def extract(self, content: str, source_type: str) -> list[ExtractedEntity]: ...


_EXTRACTORS: list[Extractor] = []


def register_extractor(extractor: Extractor) -> None:
    """Register an extractor with the global registry."""
    _EXTRACTORS.append(extractor)


def run_extractors(content: str, source_type: str) -> list[ExtractedEntity]:
    """Run all registered extractors against content and return deduplicated results.

    Each extractor is called in a try/except so a failing extractor does not
    prevent others from running. Results are deduplicated by
    (entity_type, external_id), keeping the first occurrence.

    Args:
        content: Text content to extract entities from.
        source_type: Type of the content source (e.g. 'slack_message').

    Returns:
        List of unique ExtractedEntity instances.
    """
    results: list[ExtractedEntity] = []
    for extractor in _EXTRACTORS:
        try:
            results.extend(extractor.extract(content, source_type))
        except Exception:
            logger.warning(
                "Extractor %s failed", type(extractor).__name__, exc_info=True
            )

    # Deduplicate by (entity_type, external_id), keeping first occurrence
    seen: set[tuple[str, str]] = set()
    unique: list[ExtractedEntity] = []
    for entity in results:
        key = (entity.entity_type, entity.external_id)
        if key not in seen:
            seen.add(key)
            unique.append(entity)
    return unique


# ============================================================
# Extractor 1: Ticket References
# ============================================================

# Matches ticket identifiers like ENG-123, CON-45, BUG-1
# Team prefix: 2-10 uppercase letters. Number: 1-6 digits.
_TICKET_REF_PATTERN = re.compile(r"\b([A-Z]{2,10})-(\d{1,6})\b")


class TicketRefExtractor:
    """Extracts ticket references (e.g. ENG-123, CON-45) as Ticket entities."""

    def extract(self, content: str, source_type: str) -> list[ExtractedEntity]:
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()
        for match in _TICKET_REF_PATTERN.finditer(content):
            identifier = match.group(0)  # e.g. "ENG-123"
            if identifier not in seen:
                seen.add(identifier)
                entities.append(
                    ExtractedEntity(
                        entity_type="Ticket",
                        external_id=identifier,
                        name=identifier,
                        properties={
                            "identifier": identifier,
                            "team_prefix": match.group(1),
                        },
                        relationship_type="references",
                    )
                )
        return entities


# ============================================================
# Extractor 2: @Mentions (Slack UIDs + platform usernames)
# ============================================================

# Slack user IDs: <@U12345ABC> format
_SLACK_MENTION_PATTERN = re.compile(r"<@(U[A-Z0-9]{6,12})>")
# Platform @usernames: @alice, @bob-smith (not preceded by non-whitespace)
_AT_MENTION_PATTERN = re.compile(r"(?<!\S)@([a-zA-Z][a-zA-Z0-9._-]{1,38})\b")

# Blocklist of @-mention patterns that are NOT real people.
# JSDoc / annotation tags (lowercase single words):
_JSDOC_TAGS = frozenset({
    "abstract", "access", "alias", "async", "augments", "author", "borrows",
    "callback", "class", "classdesc", "constant", "constructs", "copyright",
    "default", "deprecated", "description", "enum", "event", "example",
    "exports", "external", "file", "fires", "function", "global", "grant",
    "icon", "ignore", "implements", "import", "inheritdoc", "inner",
    "instance", "interface", "kind", "lends", "license", "link", "match",
    "member", "memberof", "method", "mixes", "mixin", "module", "name",
    "namespace", "override", "package", "param", "private", "property",
    "protected", "public", "readonly", "requires", "return", "returns",
    "run-at", "see", "since", "static", "summary", "suppress", "template",
    "this", "throws", "todo", "tutorial", "type", "typedef", "variation",
    "version", "virtual", "yields",
})

# npm scoped package prefixes and well-known non-person @-names
_NPM_PACKAGE_PREFIXES = (
    "typescript-eslint", "angular-eslint", "angular", "babel", "types",
    "eslint", "jest", "testing-library", "storybook", "vue", "nuxt",
    "nestjs", "ngrx", "react-native", "sentry", "emotion", "mui",
    "fortawesome", "fontsource", "rollup", "vitejs", "sveltejs",
    "tailwindcss", "prisma", "trpc",
)

# Config / decorator keywords (PascalCase or known patterns)
_CONFIG_KEYWORDS = frozenset({
    "Config", "Component", "Module", "Injectable", "Controller", "Service",
    "Entity", "Column", "Table", "Index", "Inject", "Optional", "Input",
    "Output", "Directive", "Pipe", "Guard", "Middleware", "Body", "Query",
    "Param", "Header", "Headers", "Get", "Post", "Put", "Delete", "Patch",
    "Override", "Deprecated", "SuppressWarnings", "FunctionalInterface",
    "Repository", "Transactional", "Autowired", "Bean", "Value",
    "RequestMapping", "PathVariable", "RequestBody", "ResponseBody",
})


def _is_false_positive_mention(username: str) -> bool:
    """Return True if the @-mention username is a known false positive."""
    lower = username.lower()

    # JSDoc / annotation tags
    if lower in _JSDOC_TAGS:
        return True

    # npm scoped packages: e.g. typescript-eslint/parser -> "typescript-eslint"
    for prefix in _NPM_PACKAGE_PREFIXES:
        if lower == prefix or lower.startswith(prefix + "/"):
            return True

    # Config / decorator keywords (case-sensitive check)
    if username in _CONFIG_KEYWORDS:
        return True

    # Heuristic: skip if it contains a slash (scoped package path)
    if "/" in username:
        return True

    return False


class MentionExtractor:
    """Extracts @mentions (Slack UIDs and platform usernames) as Person entities."""

    def extract(self, content: str, source_type: str) -> list[ExtractedEntity]:
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()

        # Slack user ID mentions: <@U12345ABC>
        for match in _SLACK_MENTION_PATTERN.finditer(content):
            user_id = match.group(1)
            key = f"slack:{user_id}"
            if key not in seen:
                seen.add(key)
                entities.append(
                    ExtractedEntity(
                        entity_type="Person",
                        external_id=key,
                        name=f"Slack user {user_id}",
                        properties={
                            "platform": "slack",
                            "platform_user_id": user_id,
                        },
                        relationship_type="mentions",
                    )
                )

        # @username mentions (Linear, GitHub)
        for match in _AT_MENTION_PATTERN.finditer(content):
            username = match.group(1)
            if _is_false_positive_mention(username):
                continue
            key = f"username:{username}"
            if key not in seen:
                seen.add(key)
                entities.append(
                    ExtractedEntity(
                        entity_type="Person",
                        external_id=key,
                        name=f"@{username}",
                        properties={
                            "platform": source_type.split("_")[0],
                            "username": username,
                        },
                        relationship_type="mentions",
                    )
                )

        return entities


# ============================================================
# Extractor 3: PR / Commit References
# ============================================================

# PR references: #123 (preceded by non-word char)
_PR_REF_PATTERN = re.compile(r"(?<!\w)#(\d{1,6})\b")

# Source types considered GitHub-related (PR refs are unambiguous)
_GITHUB_SOURCE_TYPES = frozenset(
    {
        "github_pull_request",
        "github_review",
        "github_commit",
        "github_issue",
        "github",
    }
)


class PRRefExtractor:
    """Extracts PR numbers (#123) and commit SHA references as PR entities."""

    def extract(self, content: str, source_type: str) -> list[ExtractedEntity]:
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()
        is_github = source_type in _GITHUB_SOURCE_TYPES

        # PR number references: #123
        for match in _PR_REF_PATTERN.finditer(content):
            pr_num = match.group(1)
            key = f"PR:#{pr_num}"
            if key not in seen:
                seen.add(key)
                props: dict = {"number": int(pr_num)}
                if not is_github:
                    props["status"] = "ambiguous"
                entities.append(
                    ExtractedEntity(
                        entity_type="PR",
                        external_id=key,
                        name=f"PR #{pr_num}",
                        properties=props,
                        relationship_type="references",
                    )
                )

        # Commit SHA references removed -- they create low-signal noise nodes.
        # Commits are not actionable graph entities; PRs are the meaningful unit.

        return entities


# ============================================================
# Extractor 4: File Paths
# ============================================================

# File paths with common code extensions
_FILE_PATH_PATTERN = re.compile(
    r"(?<!\S)"  # not preceded by non-whitespace
    r"((?:\.{0,2}/)?"  # optional ./ or ../
    r"(?:[a-zA-Z0-9_.-]+/)*"  # directory segments
    r"[a-zA-Z0-9_.-]+"  # filename
    r"\.(?:ts|tsx|js|jsx|py|rs|go|sql|md|json|yaml|yml|toml|css|html))"  # extension
    r"(?=\s|$|[,;)\]}])",  # lookahead for word boundary (doesn't consume)
    re.MULTILINE,
)


class FilePathExtractor:
    """Extracts file path references as CodeChunk entities."""

    def extract(self, content: str, source_type: str) -> list[ExtractedEntity]:
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()

        for match in _FILE_PATH_PATTERN.finditer(content):
            path = match.group(1)
            if path not in seen:
                seen.add(path)
                entities.append(
                    ExtractedEntity(
                        entity_type="CodeChunk",
                        external_id=f"path:{path}",
                        name=path,
                        properties={"file_path": path},
                        relationship_type="references",
                    )
                )

        return entities


# ============================================================
# Extractor 5: Known Integration URLs
# ============================================================

_URL_PATTERNS = {
    "linear": re.compile(
        r"https?://linear\.app/[a-zA-Z0-9-]+/issue/([A-Z]+-\d+)"
    ),
    "github_pr": re.compile(
        r"https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)/pull/(\d+)"
    ),
    "github_commit": re.compile(
        r"https?://github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)/commit/([0-9a-f]{7,40})"
    ),
    "notion": re.compile(
        r"https?://(?:www\.)?notion\.so/(?:[a-zA-Z0-9-]+/)?([a-f0-9]{32})"
    ),
    "slack": re.compile(
        r"https?://[a-zA-Z0-9-]+\.slack\.com/archives/([A-Z0-9]+)/p(\d+)"
    ),
}


class URLExtractor:
    """Extracts known integration URLs and resolves them to entity types."""

    def extract(self, content: str, source_type: str) -> list[ExtractedEntity]:
        entities: list[ExtractedEntity] = []
        seen: set[str] = set()

        for platform, pattern in _URL_PATTERNS.items():
            for match in pattern.finditer(content):
                full_url = match.group(0)

                if platform == "linear":
                    identifier = match.group(1)
                    key = ("Ticket", identifier)
                    if key not in seen:
                        seen.add(key)
                        entities.append(
                            ExtractedEntity(
                                entity_type="Ticket",
                                external_id=identifier,
                                name=identifier,
                                properties={
                                    "url": full_url,
                                    "resolved_from": "url",
                                },
                                relationship_type="references",
                            )
                        )

                elif platform == "github_pr":
                    repo, pr_num = match.group(1), match.group(2)
                    ext_id = f"PR:{repo}#{pr_num}"
                    key = ("PR", ext_id)
                    if key not in seen:
                        seen.add(key)
                        entities.append(
                            ExtractedEntity(
                                entity_type="PR",
                                external_id=ext_id,
                                name=f"PR {repo}#{pr_num}",
                                properties={
                                    "repo": repo,
                                    "number": int(pr_num),
                                    "url": full_url,
                                    "resolved_from": "url",
                                },
                                relationship_type="references",
                            )
                        )

                elif platform == "github_commit":
                    repo, sha = match.group(1), match.group(2)
                    ext_id = f"commit:{repo}:{sha[:7]}"
                    key = ("PR", ext_id)
                    if key not in seen:
                        seen.add(key)
                        entities.append(
                            ExtractedEntity(
                                entity_type="PR",
                                external_id=ext_id,
                                name=f"Commit {sha[:7]} in {repo}",
                                properties={
                                    "repo": repo,
                                    "sha": sha,
                                    "short_sha": sha[:7],
                                    "url": full_url,
                                    "resolved_from": "url",
                                },
                                relationship_type="references",
                            )
                        )

                elif platform == "notion":
                    page_id = match.group(1)
                    key = ("NotionPage", page_id)
                    if key not in seen:
                        seen.add(key)
                        entities.append(
                            ExtractedEntity(
                                entity_type="NotionPage",
                                external_id=f"notion:{page_id}",
                                name=f"Notion page {page_id[:8]}...",
                                properties={
                                    "page_id": page_id,
                                    "url": full_url,
                                    "resolved_from": "url",
                                },
                                relationship_type="references",
                            )
                        )

                elif platform == "slack":
                    channel, ts = match.group(1), match.group(2)
                    ext_id = f"slack:{channel}:{ts}"
                    key = ("SlackThread", ext_id)
                    if key not in seen:
                        seen.add(key)
                        entities.append(
                            ExtractedEntity(
                                entity_type="SlackThread",
                                external_id=ext_id,
                                name=f"Slack thread {channel}",
                                properties={
                                    "channel_id": channel,
                                    "thread_ts": ts,
                                    "url": full_url,
                                    "resolved_from": "url",
                                },
                                relationship_type="references",
                            )
                        )

        return entities


# ============================================================
# Code-to-discussion linking (CODE-01, CODE-02)
# ============================================================

# Source types that may mention code files in their content
_CODE_MENTION_SOURCE_TYPES = frozenset(
    {
        "slack_message",
        "linear_comment",
        "meeting_transcript",
        "meeting_segment",
    }
)

# Entity types considered "discussion" nodes for transitive linking
_DISCUSSION_ENTITY_TYPES = frozenset({"SlackThread", "Meeting"})


async def link_code_mentions_to_chunks(
    session: AsyncSession,
    workspace_id: UUID,
    source_node_id: UUID,
    entities: list[ExtractedEntity],
) -> None:
    """Match CodeChunk entities against actual code_chunks table records.

    For each CodeChunk entity with at least one directory segment (contains '/'),
    queries the code_chunks table for matching file paths (suffix match) and creates
    'mentions' edges from the source node to CodeChunk graph nodes backed by those records.

    This bridges the gap between FilePathExtractor's dangling reference nodes
    (external_id=path:{filepath}) and actual code_chunks in the database.

    Fail-silent: errors are logged but never raised.

    Args:
        session: Async database session.
        workspace_id: Workspace to search code_chunks in.
        source_node_id: The source node (e.g., SlackThread) to create edges from.
        entities: Extracted entities from content (filters for CodeChunk only).
    """
    from src.services import graph_ops

    try:
        for entity in entities:
            if entity.entity_type != "CodeChunk":
                continue

            file_path = entity.properties.get("file_path", "")
            if not file_path or "/" not in file_path:
                continue  # Skip bare filenames to avoid false positives

            # Lazy import to avoid circular dependency at module level
            from sqlmodel import select

            from src.models.code_chunk import CodeChunk

            # Find matching code_chunks by suffix match
            stmt = select(CodeChunk).where(
                CodeChunk.workspace_id == workspace_id,
                CodeChunk.file_path.endswith(file_path),  # type: ignore[union-attr]
                CodeChunk.deleted_at.is_(None),  # type: ignore[union-attr]
            )
            result = await session.execute(stmt)
            chunks = result.scalars().all()

            for chunk in chunks:
                # Create/get the CodeChunk graph node for the actual code_chunk record
                chunk_node_id = await graph_ops.upsert_node(
                    session=session,
                    workspace_id=workspace_id,
                    entity_type="CodeChunk",
                    external_id=f"chunk:{chunk.id}",
                    name=f"{chunk.symbol_type}: {chunk.symbol_name}",
                    source_type="code_chunk",
                    source_id=chunk.id,
                )
                # Create edge: SourceNode --(mentions)--> CodeChunkNode
                await graph_ops.upsert_edge(
                    session=session,
                    workspace_id=workspace_id,
                    source_node_id=source_node_id,
                    target_node_id=chunk_node_id,
                    relationship_type="mentions",
                    properties={"matched_path": file_path},
                )

    except Exception:
        logger.warning(
            "Code mention linking failed (workspace=%s, source_node=%s)",
            workspace_id,
            source_node_id,
            exc_info=True,
        )


async def link_pr_code_to_discussions(
    session: AsyncSession,
    workspace_id: UUID,
    source_node_id: UUID,
    source_id: UUID,
) -> None:
    """Create transitive 'discussed_in' edges from PR's CodeChunk neighbors to discussion nodes.

    For PRs linked to a ticket via linear_ticket_id FK:
    1. Find the ticket's graph node
    2. Find CodeChunk entity neighbors of the PR source node (from FilePathExtractor)
    3. Find SlackThread/Meeting discussion neighbors of the ticket node
    4. Create 'discussed_in' edges from each CodeChunk to each discussion node

    Fail-silent: errors are logged but never raised.

    Args:
        session: Async database session.
        workspace_id: Workspace to operate in.
        source_node_id: The PR source node in the graph.
        source_id: The GithubPullRequest record UUID.
    """
    from src.services import graph_ops

    try:
        from sqlmodel import select

        from src.models.github import GithubPullRequest
        from src.models.graph_edge import GraphEdge
        from src.models.graph_node import GraphNode
        from src.models.ticket import LinearTicket

        # 1. Look up the PR to get its ticket link
        pr_stmt = select(GithubPullRequest).where(
            GithubPullRequest.id == source_id,
        )
        pr_result = await session.execute(pr_stmt)
        pr = pr_result.scalar_one_or_none()
        if pr is None or pr.linear_ticket_id is None:
            return  # No ticket link, nothing to do

        # 2. Look up the ticket to get its identifier (for fingerprint)
        ticket_stmt = select(LinearTicket).where(
            LinearTicket.id == pr.linear_ticket_id,
        )
        ticket_result = await session.execute(ticket_stmt)
        ticket = ticket_result.scalar_one_or_none()
        if ticket is None:
            return

        # 3. Find the ticket's graph node by fingerprint
        ticket_fingerprint = graph_ops.compute_fingerprint("Ticket", ticket.identifier)
        ticket_node_stmt = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.fingerprint == ticket_fingerprint,
            GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        ticket_node_result = await session.execute(ticket_node_stmt)
        ticket_node = ticket_node_result.scalar_one_or_none()
        if ticket_node is None:
            return

        # 4. Find CodeChunk neighbors of the PR source node
        cc_edges_stmt = select(GraphEdge).where(
            GraphEdge.workspace_id == workspace_id,
            GraphEdge.source_node_id == source_node_id,
            GraphEdge.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        cc_edges_result = await session.execute(cc_edges_stmt)
        cc_edges = cc_edges_result.scalars().all()
        code_chunk_node_ids = [e.target_node_id for e in cc_edges]

        if not code_chunk_node_ids:
            return

        # 5. Find discussion neighbors of the ticket node
        # (nodes connected via edges where ticket_node is source or target)
        disc_nodes_stmt = select(GraphNode).where(
            GraphNode.workspace_id == workspace_id,
            GraphNode.entity_type.in_(_DISCUSSION_ENTITY_TYPES),  # type: ignore[union-attr]
            GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
            GraphNode.id.in_(  # type: ignore[union-attr]
                select(GraphEdge.source_node_id).where(
                    GraphEdge.target_node_id == ticket_node.id,
                    GraphEdge.workspace_id == workspace_id,
                    GraphEdge.deleted_at.is_(None),  # type: ignore[union-attr]
                ).union(
                    select(GraphEdge.target_node_id).where(
                        GraphEdge.source_node_id == ticket_node.id,
                        GraphEdge.workspace_id == workspace_id,
                        GraphEdge.deleted_at.is_(None),  # type: ignore[union-attr]
                    )
                )
            ),
        )
        disc_result = await session.execute(disc_nodes_stmt)
        discussion_nodes = disc_result.scalars().all()

        if not discussion_nodes:
            return

        # 6. Create transitive 'discussed_in' edges: CodeChunk -> Discussion
        for cc_node_id in code_chunk_node_ids:
            for disc_node in discussion_nodes:
                await graph_ops.upsert_edge(
                    session=session,
                    workspace_id=workspace_id,
                    source_node_id=cc_node_id,
                    target_node_id=disc_node.id,
                    relationship_type="discussed_in",
                    properties={"transitive": True, "via": "pr_ticket_link"},
                )

    except Exception:
        logger.warning(
            "PR code-to-discussion linking failed (workspace=%s, source_id=%s)",
            workspace_id,
            source_id,
            exc_info=True,
        )


# ============================================================
# Orchestrator: extract_and_populate_graph
# ============================================================


async def extract_and_populate_graph(
    session: AsyncSession,
    workspace_id: UUID,
    content: str,
    source_type: str,
    source_id: UUID,
    source_name: str,
    source_external_id: str | None = None,
) -> None:
    """Extract entities from content and populate the graph.

    This is the single entry point that all webhook handlers call after
    content upsert. It:
    1. Creates a source node for the content being processed
    2. Runs all registered extractors to find entities
    3. Creates/updates entity nodes via upsert (fingerprint dedup)
    4. Creates edges from the source node to each entity node

    Graph extraction is additive -- failures are logged but never raised.
    Core ingestion (ticket upsert, embedding generation) must never fail
    because of graph extraction.

    Args:
        session: Async database session (same transaction as webhook handler).
        workspace_id: Workspace the content belongs to.
        content: Text content to extract entities from.
        source_type: Type of content source (e.g. 'linear_ticket').
        source_id: UUID of the source record.
        source_name: Human-readable name for the source node.
        source_external_id: External identifier for fingerprint. Falls back
            to str(source_id) if not provided.
    """
    from src.services.graph_ops import upsert_edge, upsert_node

    try:
        # Determine entity type for the source node
        entity_type = SOURCE_TYPE_TO_ENTITY.get(source_type, "Ticket")
        ext_id = source_external_id or str(source_id)

        # 1. Create source node
        # Build properties for the source node
        source_props: dict = {}
        if source_type in ("linear_ticket", "jira_issue") and source_external_id:
            source_props["identifier"] = source_external_id

        source_node_id = await upsert_node(
            session=session,
            workspace_id=workspace_id,
            entity_type=entity_type,
            external_id=ext_id,
            name=source_name,
            source_type=source_type,
            source_id=source_id,
            properties=source_props,
        )

        # 2. Run extractors to get entities
        entities = run_extractors(content, source_type)

        # 3-4. For each entity, create node and edge
        for entity in entities:
            props = dict(entity.properties)
            # Mark dangling references with status=unresolved
            if "status" not in props:
                props["status"] = "unresolved"

            entity_node_id = await upsert_node(
                session=session,
                workspace_id=workspace_id,
                entity_type=entity.entity_type,
                external_id=entity.external_id,
                name=entity.name,
                properties=props,
            )

            await upsert_edge(
                session=session,
                workspace_id=workspace_id,
                source_node_id=source_node_id,
                target_node_id=entity_node_id,
                relationship_type=entity.relationship_type,
            )

        # 5. Link code mentions to actual code_chunks records (CODE-01)
        if source_type in _CODE_MENTION_SOURCE_TYPES:
            await link_code_mentions_to_chunks(
                session, workspace_id, source_node_id, entities
            )

        # 6. Link PR code to discussions via ticket (CODE-02)
        if source_type == "github_pull_request":
            await link_pr_code_to_discussions(
                session, workspace_id, source_node_id, source_id
            )

        logger.info(
            "Graph extraction complete: source=%s, entities=%d, source_type=%s",
            source_name,
            len(entities),
            source_type,
        )

    except Exception:
        logger.warning(
            "Graph extraction failed for %s (source_type=%s, source_id=%s)",
            source_name,
            source_type,
            source_id,
            exc_info=True,
        )


# ============================================================
# Auto-registration
# ============================================================

register_extractor(TicketRefExtractor())
# MentionExtractor intentionally not registered: its Person entities are low-signal
# (e.g. @typescript-eslint, @Config). Person nodes should only come from
# roster-based identity resolution (Linear/Slack/GitHub).
register_extractor(PRRefExtractor())
register_extractor(FilePathExtractor())
register_extractor(URLExtractor())
