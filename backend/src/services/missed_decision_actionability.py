"""Actionability gate for missed-decision candidates.

This module is intentionally metadata-only. It can suggest draft ticket/doc
copy or an internal Decision Receipt save, but it never writes external
provider artifacts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.github import GithubPullRequest, GithubReview
from src.models.gitlab import GitlabMergeRequest, GitlabReview
from src.models.integration import WorkspaceIntegration
from src.models.jira import JiraComment, JiraIssue
from src.models.missed_decision import MissedDecisionCandidate
from src.models.notion import NotionPage
from src.models.sync import SyncCursor
from src.models.ticket import LinearComment, LinearTicket
from src.services.missed_decision_attribution import candidate_source_timestamp
from src.services.missed_decision_autosave import should_auto_save_missed_decision
from src.services.missed_decision_dedupe import (
    MATCH_STRONG,
    MATCH_WEAK,
    SUPPRESSION_ALREADY_BACKED_BY_ARTIFACT,
    DedupeClassification,
)
from src.services.missed_decision_extractor import is_surfaceable_confidence

ACTIONABILITY_ACTIONABLE = "actionable"
ACTIONABILITY_ALREADY_BACKED = "already_backed"
ACTIONABILITY_POSSIBLE_MATCH = "possible_match"
ACTIONABILITY_STALE_SEARCH = "stale_search"
ACTIONABILITY_UNSUPPORTED_ARTIFACT = "unsupported_artifact"
ACTIONABILITY_INSUFFICIENT_EVIDENCE = "insufficient_evidence"

ACTION_SAVE_DECISION_RECEIPT = "save_decision_receipt"
ACTION_DRAFT_TICKET = "draft_ticket"
ACTION_DRAFT_DOC_UPDATE = "draft_doc_update"
ACTION_ATTACH_EVIDENCE = "attach_evidence"
ACTION_SUPPRESS_ALREADY_BACKED = "suppress_already_backed"
ACTION_HOLD_FOR_REPROCESS = "hold_for_reprocess"

WRITE_POLICY_AUTO_INTERNAL = "auto_internal"
WRITE_POLICY_DRAFT_EXTERNAL = "draft_external"
WRITE_POLICY_REVIEW_REQUIRED = "review_required"
WRITE_POLICY_NO_WRITE = "no_write"

ACTIONABILITY_SEARCHED_SOURCES = [
    "Decision memory",
    "Existing candidates",
    "Suggestions",
    "Jira issues and comments",
    "Linear tickets and comments",
    "GitHub PRs and reviews",
    "GitLab MRs and reviews",
    "Notion pages",
]

_SEARCH_PROVIDERS = ("jira", "linear", "github", "gitlab", "notion")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "be",
    "before",
    "by",
    "do",
    "for",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "should",
    "so",
    "the",
    "to",
    "we",
    "will",
}


@dataclass(frozen=True)
class ArtifactMatch:
    """Durable artifact match found during local actionability search."""

    entity_type: str
    entity_id: UUID
    title: str
    href: str | None = None
    match_status: str = MATCH_WEAK
    match_reason: str | None = None

    def to_payload(self) -> dict:
        return {
            "entity_type": self.entity_type,
            "entity_id": str(self.entity_id),
            "title": self.title,
            "href": self.href,
            "match_status": self.match_status,
            "match_reason": self.match_reason,
        }


@dataclass(frozen=True)
class NextAction:
    """Single proposed action for a candidate."""

    kind: str
    write_policy: str
    title: str
    body: str
    source_quote: str
    source_link: str
    artifact_type: str | None = None
    searched_sources: list[str] = field(default_factory=list)
    target_entity_type: str | None = None
    target_entity_id: str | None = None
    target_title: str | None = None
    target_href: str | None = None
    copyable: bool = False

    def to_hint(self) -> dict:
        return {
            "kind": self.kind,
            "write_policy": self.write_policy,
            "title": self.title,
            "body": self.body,
            "source_quote": self.source_quote,
            "source_link": self.source_link,
            "artifact_type": self.artifact_type,
            "searched_sources": self.searched_sources,
            "target_entity_type": self.target_entity_type,
            "target_entity_id": self.target_entity_id,
            "target_title": self.target_title,
            "target_href": self.target_href,
            "copyable": self.copyable,
        }


@dataclass(frozen=True)
class ActionabilityResult:
    """Actionability verdict persisted onto candidate evidence/action_hints."""

    status: str
    next_action: NextAction
    searched_sources: list[str]
    artifact_matches: list[ArtifactMatch] = field(default_factory=list)
    stale_providers: list[str] = field(default_factory=list)
    reason: str | None = None

    def to_payload(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "searched_sources": self.searched_sources,
            "stale_providers": self.stale_providers,
            "artifact_matches": [match.to_payload() for match in self.artifact_matches],
            "next_action": self.next_action.to_hint(),
        }


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in _TOKEN_RE.findall(value.lower())
        if token not in _STOPWORDS and len(token) > 1
    ]


def _normalized(value: str) -> str:
    tokens = sorted(set(_tokens(value)))
    return " ".join(tokens) if tokens else " ".join(value.lower().split())


def _token_overlap(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _trim(value: str, limit: int) -> str:
    value = " ".join(value.split())
    if len(value) <= limit:
        return value
    return f"{value[: limit - 3].rstrip()}..."


def _candidate_text(candidate: MissedDecisionCandidate) -> str:
    return " ".join(
        [
            candidate.inferred_decision or "",
            candidate.inferred_rationale or "",
            candidate.source_quote or "",
            " ".join(candidate.affected_systems or []),
        ]
    )


def _review_context(candidate: MissedDecisionCandidate) -> dict:
    evidence = candidate.evidence if isinstance(candidate.evidence, dict) else {}
    context = evidence.get("review_context")
    return dict(context) if isinstance(context, dict) else {}


def _expected_artifact_type(candidate: MissedDecisionCandidate) -> str:
    context = _review_context(candidate)
    value = context.get("expected_artifact_type")
    return value.strip().lower() if isinstance(value, str) else ""


def _expected_artifact(candidate: MissedDecisionCandidate) -> str:
    context = _review_context(candidate)
    value = context.get("expected_artifact")
    return value.strip() if isinstance(value, str) else ""


def _affected_object(candidate: MissedDecisionCandidate) -> str:
    context = _review_context(candidate)
    value = context.get("affected_object")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return (candidate.affected_systems or ["decision"])[0]


def _source_created_at(candidate: MissedDecisionCandidate) -> datetime | None:
    evidence = candidate.evidence if isinstance(candidate.evidence, dict) else {}
    for raw in (
        evidence.get("source_created_at"),
        candidate_source_timestamp(candidate),
    ):
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    if candidate.detected_at is None:
        return None
    if candidate.detected_at.tzinfo is None:
        return candidate.detected_at.replace(tzinfo=UTC)
    return candidate.detected_at.astimezone(UTC)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_sync_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    if isinstance(value, str) and value.strip():
        try:
            return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _is_ticket_artifact(artifact_type: str) -> bool:
    return any(
        term in artifact_type
        for term in ("ticket", "issue", "jira", "linear", "task")
    )


def _is_doc_artifact(artifact_type: str) -> bool:
    return any(
        term in artifact_type
        for term in (
            "doc",
            "spec",
            "runbook",
            "release",
            "adr",
            "postmortem",
            "checklist",
            "api",
            "notion",
            "customer",
        )
    )


def _is_receipt_artifact(artifact_type: str) -> bool:
    return any(term in artifact_type for term in ("decision", "receipt", "memory"))


def _classification_match(
    classification: DedupeClassification,
) -> ArtifactMatch | None:
    if not classification.matched_entity_id:
        return None
    title = classification.matched_title or "Existing artifact"
    entity_type = classification.matched_entity_type or "artifact"
    if entity_type == "graph_node":
        href = classification.matched_href
        if href and "/dashboard/decisions/" in href:
            entity_type = "Decision"
        else:
            entity_type = "artifact"
    return ArtifactMatch(
        entity_type=entity_type,
        entity_id=classification.matched_entity_id,
        title=title,
        href=classification.matched_href,
        match_status=classification.match_status,
        match_reason=classification.match_reason,
    )


def _artifact_match(
    candidate: MissedDecisionCandidate,
    *,
    entity_type: str,
    entity_id: UUID,
    title: str,
    text: str,
    href: str | None = None,
) -> ArtifactMatch | None:
    if not title and not text:
        return None
    artifact_text = " ".join([title, text])
    decision_overlap = _token_overlap(candidate.inferred_decision, artifact_text)
    full_overlap = _token_overlap(_candidate_text(candidate), artifact_text)
    same_signature = _normalized(candidate.inferred_decision) == _normalized(title)
    if same_signature or (decision_overlap >= 0.65 and full_overlap >= 0.30):
        return ArtifactMatch(
            entity_type=entity_type,
            entity_id=entity_id,
            title=title or entity_type,
            href=href,
            match_status=MATCH_STRONG,
            match_reason=f"Strong {entity_type} match on decision wording.",
        )
    if decision_overlap >= 0.25 or full_overlap >= 0.25:
        return ArtifactMatch(
            entity_type=entity_type,
            entity_id=entity_id,
            title=title or entity_type,
            href=href,
            match_status=MATCH_WEAK,
            match_reason=f"Possible {entity_type} match based on overlapping terms.",
        )
    return None


async def _connected_provider_syncs(
    session: AsyncSession,
    workspace_id: UUID,
) -> dict[str, datetime | None]:
    integration_result = await session.execute(
        select(WorkspaceIntegration).where(
            WorkspaceIntegration.workspace_id == workspace_id,
            WorkspaceIntegration.provider.in_(_SEARCH_PROVIDERS),  # type: ignore[attr-defined]
            WorkspaceIntegration.status == "connected",
            WorkspaceIntegration.deleted_at.is_(None),  # type: ignore[union-attr]
        )
    )
    provider_syncs: dict[str, datetime | None] = {}
    for integration in integration_result.scalars().all():
        config = integration.config if isinstance(integration.config, dict) else {}
        provider_syncs[integration.provider] = _parse_sync_timestamp(
            config.get("last_sync_at")
        )

    cursor_result = await session.execute(
        select(SyncCursor).where(
            SyncCursor.workspace_id == workspace_id,
            SyncCursor.provider.in_(list(provider_syncs)),  # type: ignore[attr-defined]
        )
    )
    for cursor in cursor_result.scalars().all():
        current = provider_syncs.get(cursor.provider)
        cursor_sync = _parse_sync_timestamp(cursor.last_sync_at)
        if current is None or (
            cursor_sync is not None and cursor_sync > current
        ):
            provider_syncs[cursor.provider] = cursor_sync
    return provider_syncs


def _stale_providers(
    provider_syncs: dict[str, datetime | None],
    source_created_at: datetime | None,
) -> list[str]:
    if source_created_at is None:
        return []
    return [
        provider
        for provider, last_sync_at in sorted(provider_syncs.items())
        if last_sync_at is None or last_sync_at < source_created_at
    ]


async def _find_linear_matches(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> list[ArtifactMatch]:
    matches: list[ArtifactMatch] = []
    result = await session.execute(
        select(LinearTicket)
        .where(
            LinearTicket.workspace_id == candidate.workspace_id,
            LinearTicket.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
    )
    for ticket in result.scalars().all():
        href = None
        raw_data = ticket.raw_data if isinstance(ticket.raw_data, dict) else {}
        for key in ("url", "link", "html_url"):
            value = raw_data.get(key)
            if isinstance(value, str) and value:
                href = value
                break
        match = _artifact_match(
            candidate,
            entity_type="linear_ticket",
            entity_id=ticket.id,
            title=ticket.title,
            text=" ".join(
                [ticket.identifier, ticket.description or "", ticket.status or ""]
            ),
            href=href,
        )
        if match:
            matches.append(match)

    result = await session.execute(
        select(LinearComment)
        .where(
            LinearComment.workspace_id == candidate.workspace_id,
            LinearComment.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
    )
    for comment in result.scalars().all():
        match = _artifact_match(
            candidate,
            entity_type="linear_comment",
            entity_id=comment.id,
            title="Linear comment",
            text=comment.body or "",
        )
        if match:
            matches.append(match)
    return matches


async def _find_jira_matches(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> list[ArtifactMatch]:
    matches: list[ArtifactMatch] = []
    result = await session.execute(
        select(JiraIssue)
        .where(
            JiraIssue.workspace_id == candidate.workspace_id,
            JiraIssue.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
    )
    for issue in result.scalars().all():
        raw_data = issue.raw_data if isinstance(issue.raw_data, dict) else {}
        href = raw_data.get("url") if isinstance(raw_data.get("url"), str) else None
        match = _artifact_match(
            candidate,
            entity_type="jira_issue",
            entity_id=issue.id,
            title=issue.summary,
            text=" ".join(
                [issue.jira_key, issue.description or "", issue.status or ""]
            ),
            href=href,
        )
        if match:
            matches.append(match)

    result = await session.execute(
        select(JiraComment)
        .where(
            JiraComment.workspace_id == candidate.workspace_id,
            JiraComment.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
    )
    for comment in result.scalars().all():
        match = _artifact_match(
            candidate,
            entity_type="jira_comment",
            entity_id=comment.id,
            title="Jira comment",
            text=comment.body or "",
        )
        if match:
            matches.append(match)
    return matches


async def _find_github_matches(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> list[ArtifactMatch]:
    matches: list[ArtifactMatch] = []
    result = await session.execute(
        select(GithubPullRequest)
        .where(
            GithubPullRequest.workspace_id == candidate.workspace_id,
            GithubPullRequest.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
    )
    for pr in result.scalars().all():
        href = f"https://github.com/{pr.repo_full_name}/pull/{pr.number}"
        match = _artifact_match(
            candidate,
            entity_type="github_pull_request",
            entity_id=pr.id,
            title=pr.title,
            text=" ".join([pr.description or "", pr.branch_name, pr.base_branch]),
            href=href,
        )
        if match:
            matches.append(match)

    result = await session.execute(
        select(GithubReview)
        .where(
            GithubReview.workspace_id == candidate.workspace_id,
            GithubReview.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
    )
    for review in result.scalars().all():
        match = _artifact_match(
            candidate,
            entity_type="github_review",
            entity_id=review.id,
            title="GitHub review",
            text=" ".join([review.body or "", review.file_path or ""]),
        )
        if match:
            matches.append(match)
    return matches


async def _find_gitlab_matches(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> list[ArtifactMatch]:
    matches: list[ArtifactMatch] = []
    result = await session.execute(
        select(GitlabMergeRequest)
        .where(
            GitlabMergeRequest.workspace_id == candidate.workspace_id,
            GitlabMergeRequest.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
    )
    for mr in result.scalars().all():
        href = f"https://gitlab.com/{mr.project_path}/-/merge_requests/{mr.iid}"
        match = _artifact_match(
            candidate,
            entity_type="gitlab_merge_request",
            entity_id=mr.id,
            title=mr.title,
            text=" ".join([mr.description or "", mr.source_branch, mr.target_branch]),
            href=href,
        )
        if match:
            matches.append(match)

    result = await session.execute(
        select(GitlabReview)
        .where(
            GitlabReview.workspace_id == candidate.workspace_id,
            GitlabReview.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
    )
    for review in result.scalars().all():
        match = _artifact_match(
            candidate,
            entity_type="gitlab_review",
            entity_id=review.id,
            title="GitLab review",
            text=" ".join([review.body or "", review.file_path or ""]),
        )
        if match:
            matches.append(match)
    return matches


async def _find_notion_matches(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
) -> list[ArtifactMatch]:
    matches: list[ArtifactMatch] = []
    result = await session.execute(
        select(NotionPage)
        .where(
            NotionPage.workspace_id == candidate.workspace_id,
            NotionPage.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .limit(50)
    )
    for page in result.scalars().all():
        match = _artifact_match(
            candidate,
            entity_type="notion_page",
            entity_id=page.id,
            title=page.title,
            text=page.content or "",
            href=page.url,
        )
        if match:
            matches.append(match)
    return matches


async def _find_artifact_matches(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
    artifact_type: str,
) -> list[ArtifactMatch]:
    if _is_receipt_artifact(artifact_type) and not (
        _is_ticket_artifact(artifact_type) or _is_doc_artifact(artifact_type)
    ):
        return []

    matches: list[ArtifactMatch] = []
    if _is_ticket_artifact(artifact_type):
        matches.extend(await _find_linear_matches(session, candidate))
        matches.extend(await _find_jira_matches(session, candidate))
    if _is_doc_artifact(artifact_type) or _is_ticket_artifact(artifact_type):
        matches.extend(await _find_github_matches(session, candidate))
        matches.extend(await _find_gitlab_matches(session, candidate))
        matches.extend(await _find_notion_matches(session, candidate))
    return sorted(
        matches,
        key=lambda match: 0 if match.match_status == MATCH_STRONG else 1,
    )


def _action_body(candidate: MissedDecisionCandidate, expected_artifact: str) -> str:
    lines = [
        f"Decision: {candidate.inferred_decision}",
        f"Rationale: {candidate.inferred_rationale}",
    ]
    if expected_artifact:
        lines.append(f"Expected artifact: {expected_artifact}")
    lines.extend(
        [
            "",
            f"Source quote: \"{candidate.source_quote}\"",
            f"Source: {candidate.source_link}",
        ]
    )
    return "\n".join(lines)


def _ticket_action(
    candidate: MissedDecisionCandidate,
    artifact_type: str,
) -> NextAction:
    return NextAction(
        kind=ACTION_DRAFT_TICKET,
        write_policy=WRITE_POLICY_DRAFT_EXTERNAL,
        title=f"Track decision: {_trim(candidate.inferred_decision, 84)}",
        body=_action_body(candidate, _expected_artifact(candidate)),
        source_quote=candidate.source_quote,
        source_link=candidate.source_link,
        artifact_type=artifact_type,
        searched_sources=ACTIONABILITY_SEARCHED_SOURCES,
        copyable=True,
    )


def _doc_action(candidate: MissedDecisionCandidate, artifact_type: str) -> NextAction:
    return NextAction(
        kind=ACTION_DRAFT_DOC_UPDATE,
        write_policy=WRITE_POLICY_DRAFT_EXTERNAL,
        title=f"Update docs: {_trim(_affected_object(candidate), 86)}",
        body=_action_body(candidate, _expected_artifact(candidate)),
        source_quote=candidate.source_quote,
        source_link=candidate.source_link,
        artifact_type=artifact_type,
        searched_sources=ACTIONABILITY_SEARCHED_SOURCES,
        copyable=True,
    )


def _receipt_action(
    candidate: MissedDecisionCandidate,
    *,
    write_policy: str,
    artifact_type: str,
) -> NextAction:
    return NextAction(
        kind=ACTION_SAVE_DECISION_RECEIPT,
        write_policy=write_policy,
        title=f"Save Decision Receipt: {_trim(candidate.inferred_decision, 76)}",
        body=_action_body(candidate, _expected_artifact(candidate)),
        source_quote=candidate.source_quote,
        source_link=candidate.source_link,
        artifact_type=artifact_type,
        searched_sources=ACTIONABILITY_SEARCHED_SOURCES,
        copyable=False,
    )


def _hold_action(
    candidate: MissedDecisionCandidate,
    *,
    reason: str,
    artifact_type: str,
) -> NextAction:
    return NextAction(
        kind=ACTION_HOLD_FOR_REPROCESS,
        write_policy=WRITE_POLICY_REVIEW_REQUIRED,
        title="Hold for reprocess",
        body=reason,
        source_quote=candidate.source_quote,
        source_link=candidate.source_link,
        artifact_type=artifact_type,
        searched_sources=ACTIONABILITY_SEARCHED_SOURCES,
    )


def _suppress_action(
    candidate: MissedDecisionCandidate,
    *,
    match: ArtifactMatch | None,
    reason: str,
) -> NextAction:
    return NextAction(
        kind=ACTION_SUPPRESS_ALREADY_BACKED,
        write_policy=WRITE_POLICY_NO_WRITE,
        title="Suppress already-backed decision",
        body=reason,
        source_quote=candidate.source_quote,
        source_link=candidate.source_link,
        artifact_type=_expected_artifact_type(candidate),
        searched_sources=ACTIONABILITY_SEARCHED_SOURCES,
        target_entity_type=match.entity_type if match else None,
        target_entity_id=str(match.entity_id) if match else None,
        target_title=match.title if match else None,
        target_href=match.href if match else None,
    )


def _attach_action(
    candidate: MissedDecisionCandidate,
    match: ArtifactMatch,
) -> NextAction:
    return NextAction(
        kind=ACTION_ATTACH_EVIDENCE,
        write_policy=WRITE_POLICY_REVIEW_REQUIRED,
        title="Attach source evidence to existing decision",
        body=_action_body(candidate, _expected_artifact(candidate)),
        source_quote=candidate.source_quote,
        source_link=candidate.source_link,
        artifact_type=_expected_artifact_type(candidate),
        searched_sources=ACTIONABILITY_SEARCHED_SOURCES,
        target_entity_type=match.entity_type,
        target_entity_id=str(match.entity_id),
        target_title=match.title,
        target_href=match.href,
    )


def _has_source_evidence(candidate: MissedDecisionCandidate) -> bool:
    return all(
        isinstance(value, str) and bool(value.strip())
        for value in (
            candidate.source_quote,
            candidate.source_link,
            candidate.inferred_decision,
            candidate.inferred_rationale,
        )
    ) and is_surfaceable_confidence(candidate.confidence)


def _persist_actionability(
    candidate: MissedDecisionCandidate,
    result: ActionabilityResult,
) -> None:
    evidence = dict(candidate.evidence or {})
    evidence["actionability"] = result.to_payload()

    review_context = dict(evidence.get("review_context") or {})
    review_context["searched_sources"] = result.searched_sources
    review_context["missing_artifact_status"] = result.status
    review_context["missing_artifact_reason"] = result.reason
    evidence["review_context"] = review_context

    quality_gate = dict(evidence.get("quality_gate") or {})
    quality_gate["artifact_search"] = result.status
    quality_gate["searched_sources"] = result.searched_sources
    if result.status != ACTIONABILITY_ACTIONABLE:
        quality_gate["passed"] = False
        quality_gate["suppress_reason"] = result.status
    evidence["quality_gate"] = quality_gate

    candidate.evidence = evidence
    candidate.action_hints = [result.next_action.to_hint()]


def _actionability_result(
    candidate: MissedDecisionCandidate,
    *,
    status: str,
    next_action: NextAction,
    reason: str,
    artifact_matches: list[ArtifactMatch] | None = None,
    stale_providers: list[str] | None = None,
) -> ActionabilityResult:
    result = ActionabilityResult(
        status=status,
        next_action=next_action,
        searched_sources=ACTIONABILITY_SEARCHED_SOURCES,
        artifact_matches=artifact_matches or [],
        stale_providers=stale_providers or [],
        reason=reason,
    )
    _persist_actionability(candidate, result)
    return result


async def verify_candidate_actionability(
    session: AsyncSession,
    candidate: MissedDecisionCandidate,
    classification: DedupeClassification,
) -> ActionabilityResult:
    """Classify whether a candidate has one concrete next action."""
    artifact_type = _expected_artifact_type(candidate)

    if not _has_source_evidence(candidate):
        reason = (
            "Candidate lacks source evidence, a source link, or "
            "reviewable confidence."
        )
        return _actionability_result(
            candidate,
            status=ACTIONABILITY_INSUFFICIENT_EVIDENCE,
            next_action=_hold_action(
                candidate,
                reason=reason,
                artifact_type=artifact_type,
            ),
            reason=reason,
        )

    source_created_at = _source_created_at(candidate)
    provider_syncs = await _connected_provider_syncs(session, candidate.workspace_id)
    stale = _stale_providers(provider_syncs, source_created_at)
    if stale:
        reason = (
            "Connected artifact providers have not synced through the source "
            "timestamp yet."
        )
        return _actionability_result(
            candidate,
            status=ACTIONABILITY_STALE_SEARCH,
            next_action=_hold_action(
                candidate,
                reason=reason,
                artifact_type=artifact_type,
            ),
            reason=reason,
            stale_providers=stale,
        )

    classification_match = _classification_match(classification)
    if classification.match_status == MATCH_STRONG:
        reason = (
            classification.match_reason
            or "A strong matching durable artifact already backs this decision."
        )
        candidate.lifecycle_status = "suppressed"
        candidate.suppression_reason = (
            classification.suppression_reason
            or SUPPRESSION_ALREADY_BACKED_BY_ARTIFACT
        )
        return _actionability_result(
            candidate,
            status=ACTIONABILITY_ALREADY_BACKED,
            next_action=_suppress_action(
                candidate,
                match=classification_match,
                reason=reason,
            ),
            reason=reason,
            artifact_matches=[classification_match] if classification_match else [],
        )

    if classification.match_status == MATCH_WEAK:
        reason = (
            classification.match_reason
            or "A possible existing artifact needs human inspection."
        )
        if classification_match and classification_match.entity_type == "Decision":
            return _actionability_result(
                candidate,
                status=ACTIONABILITY_ACTIONABLE,
                next_action=_attach_action(candidate, classification_match),
                reason=reason,
                artifact_matches=[classification_match],
            )
        return _actionability_result(
            candidate,
            status=ACTIONABILITY_POSSIBLE_MATCH,
            next_action=_hold_action(
                candidate,
                reason=reason,
                artifact_type=artifact_type,
            ),
            reason=reason,
            artifact_matches=[classification_match] if classification_match else [],
        )

    artifact_matches = await _find_artifact_matches(session, candidate, artifact_type)
    strong_matches = [
        match for match in artifact_matches if match.match_status == MATCH_STRONG
    ]
    if strong_matches:
        reason = strong_matches[0].match_reason or (
            "A strong matching durable artifact already backs this decision."
        )
        candidate.lifecycle_status = "suppressed"
        candidate.suppression_reason = SUPPRESSION_ALREADY_BACKED_BY_ARTIFACT
        candidate.matched_entity_type = strong_matches[0].entity_type
        candidate.matched_entity_id = strong_matches[0].entity_id
        return _actionability_result(
            candidate,
            status=ACTIONABILITY_ALREADY_BACKED,
            next_action=_suppress_action(
                candidate,
                match=strong_matches[0],
                reason=reason,
            ),
            reason=reason,
            artifact_matches=artifact_matches,
        )

    weak_matches = [
        match for match in artifact_matches if match.match_status == MATCH_WEAK
    ]
    if weak_matches:
        reason = weak_matches[0].match_reason or (
            "A possible existing artifact needs human inspection."
        )
        return _actionability_result(
            candidate,
            status=ACTIONABILITY_POSSIBLE_MATCH,
            next_action=_hold_action(
                candidate,
                reason=reason,
                artifact_type=artifact_type,
            ),
            reason=reason,
            artifact_matches=artifact_matches,
        )

    if should_auto_save_missed_decision(candidate, classification):
        reason = "Source-backed internal Decision Receipt can be saved safely."
        return _actionability_result(
            candidate,
            status=ACTIONABILITY_ACTIONABLE,
            next_action=_receipt_action(
                candidate,
                write_policy=WRITE_POLICY_AUTO_INTERNAL,
                artifact_type=artifact_type or "decision_receipt",
            ),
            reason=reason,
        )

    if _is_ticket_artifact(artifact_type):
        reason = "No matching fresh ticket was found; draft a ticket for review."
        return _actionability_result(
            candidate,
            status=ACTIONABILITY_ACTIONABLE,
            next_action=_ticket_action(candidate, artifact_type),
            reason=reason,
        )

    if _is_doc_artifact(artifact_type):
        reason = "No matching fresh doc was found; draft a doc update for review."
        return _actionability_result(
            candidate,
            status=ACTIONABILITY_ACTIONABLE,
            next_action=_doc_action(candidate, artifact_type),
            reason=reason,
        )

    if _is_receipt_artifact(artifact_type) or not artifact_type:
        reason = "Candidate needs human review before becoming Decision memory."
        return _actionability_result(
            candidate,
            status=ACTIONABILITY_ACTIONABLE,
            next_action=_receipt_action(
                candidate,
                write_policy=WRITE_POLICY_REVIEW_REQUIRED,
                artifact_type=artifact_type or "decision_receipt",
            ),
            reason=reason,
        )

    reason = f"Unsupported expected artifact type: {artifact_type}"
    return _actionability_result(
        candidate,
        status=ACTIONABILITY_UNSUPPORTED_ARTIFACT,
        next_action=_hold_action(
            candidate,
            reason=reason,
            artifact_type=artifact_type,
        ),
        reason=reason,
    )
