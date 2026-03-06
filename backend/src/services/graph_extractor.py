"""Graph entity extraction: registry pattern with five deterministic regex extractors.

Provides:
  - ExtractedEntity dataclass for extracted graph entities
  - Extractor protocol for pluggable extraction
  - Registry (register_extractor, run_extractors) for composing extractors
  - Five built-in regex extractors: tickets, mentions, PR/commit refs, file paths, URLs

All extractors are pure functions that take content text and return extracted
entities. No database interaction, no LLM calls -- zero cost extraction.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)


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
# Git SHA references: 7+ hex chars (short SHA), isolated word
_SHA_PATTERN = re.compile(r"\b([0-9a-f]{7,40})\b")

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

        # Commit SHA references: 7+ hex chars, not all digits
        for match in _SHA_PATTERN.finditer(content):
            sha = match.group(1)
            if len(sha) >= 7 and not sha.isdigit():
                key = f"commit:{sha[:7]}"
                if key not in seen:
                    seen.add(key)
                    entities.append(
                        ExtractedEntity(
                            entity_type="PR",
                            external_id=key,
                            name=f"Commit {sha[:7]}",
                            properties={"sha": sha, "short_sha": sha[:7]},
                            relationship_type="references",
                        )
                    )

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
# Auto-registration
# ============================================================

register_extractor(TicketRefExtractor())
register_extractor(MentionExtractor())
register_extractor(PRRefExtractor())
register_extractor(FilePathExtractor())
register_extractor(URLExtractor())
