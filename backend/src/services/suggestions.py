"""Suggestion lifecycle and generation services."""

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import case, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import get_settings
from src.models.graph_node import GraphNode
from src.models.integration import WorkspaceIntegration
from src.models.suggestion import Suggestion
from src.services.audit import log_audit_event
from src.services.llm_client import LLMClient, get_llm_client

logger = logging.getLogger(__name__)

SUGGESTION_TYPE_MISSING_SOURCE = "missing_source_coverage"
SUGGESTION_TYPE_MISSED_DECISION = "missed_decision"
SUGGESTION_TYPE_ACTION_PROMPT = "action_prompt"

SUGGESTION_STATUS_OPEN = "open"
SUGGESTION_STATUS_SNOOZED = "snoozed"
SUGGESTION_STATUS_DISMISSED = "dismissed"
SUGGESTION_STATUS_RESOLVED = "resolved"

MISSING_DESIGN_EVIDENCE = "design_review"
MISSING_SOURCE_PRIMARY_ACTION = "Review"
SUGGESTIONS_QUEUE_HREF = "/dashboard/suggestions"
DESIGN_REVIEW_CONFIDENCE_THRESHOLD = 0.75
MISSING_SOURCE_COVERAGE_GENERATOR = "missing_source_coverage:v2"
DESIGN_EVIDENCE_PROVIDERS = ("figma",)


class DesignReviewGapAssessment(BaseModel):
    """Structured relevance verdict for design-review coverage suggestions."""

    should_suggest: bool = Field(
        description=(
            "True only when this is a user-facing product/interface decision where "
            "missing design review evidence is materially relevant."
        )
    )
    reason: str = Field(
        description="Short source-grounded reason for the verdict."
    )
    confidence: float = Field(
        description="Confidence from 0.0 to 1.0. Use lower confidence when unsure."
    )


class SuggestionNotFoundError(Exception):
    """Raised when a suggestion is not found in the requested workspace."""


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _primary_action(suggestion: Suggestion) -> str | None:
    if suggestion.type == SUGGESTION_TYPE_MISSING_SOURCE:
        return MISSING_SOURCE_PRIMARY_ACTION
    return suggestion.primary_action


def _action_href(suggestion: Suggestion) -> str | None:
    if suggestion.type == SUGGESTION_TYPE_MISSING_SOURCE:
        if suggestion.entity_type == "graph_node" and suggestion.entity_id:
            return f"/dashboard/decisions/{suggestion.entity_id}"
        return SUGGESTIONS_QUEUE_HREF
    return suggestion.action_href


def serialize_suggestion(suggestion: Suggestion) -> dict:
    """Serialize a suggestion for API responses."""
    return {
        "id": str(suggestion.id),
        "workspace_id": str(suggestion.workspace_id),
        "type": suggestion.type,
        "status": suggestion.status,
        "priority": suggestion.priority,
        "fingerprint": suggestion.fingerprint,
        "entity_type": suggestion.entity_type,
        "entity_id": str(suggestion.entity_id) if suggestion.entity_id else None,
        "title": suggestion.title,
        "body": suggestion.body,
        "primary_action": _primary_action(suggestion),
        "action_href": _action_href(suggestion),
        "evidence": suggestion.evidence or {},
        "details": suggestion.details or {},
        "provenance": suggestion.provenance or {},
        "snoozed_until": _iso(suggestion.snoozed_until),
        "dismissed_at": _iso(suggestion.dismissed_at),
        "resolved_at": _iso(suggestion.resolved_at),
        "reopened_at": _iso(suggestion.reopened_at),
        "last_seen_at": _iso(suggestion.last_seen_at),
        "created_at": _iso(suggestion.created_at),
        "updated_at": _iso(suggestion.updated_at),
    }


def _priority_order():
    return case(
        (Suggestion.priority == "high", 0),
        (Suggestion.priority == "medium", 1),
        (Suggestion.priority == "low", 2),
        else_=3,
    )


async def list_visible_suggestions(
    session: AsyncSession,
    workspace_id: UUID,
    *,
    limit: int = 3,
) -> list[Suggestion]:
    """List open dashboard suggestions, excluding active snoozes."""
    now = _now()
    stmt = (
        select(Suggestion)
        .where(
            Suggestion.workspace_id == workspace_id,
            Suggestion.deleted_at.is_(None),  # type: ignore[union-attr]
            or_(
                Suggestion.status == SUGGESTION_STATUS_OPEN,
                (Suggestion.status == SUGGESTION_STATUS_SNOOZED)
                & (Suggestion.snoozed_until <= now),  # type: ignore[operator]
            ),
        )
        .order_by(_priority_order(), Suggestion.created_at.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_all_suggestions(
    session: AsyncSession,
    workspace_id: UUID,
    *,
    limit: int = 100,
) -> list[Suggestion]:
    """List all non-deleted suggestions for the full queue."""
    stmt = (
        select(Suggestion)
        .where(
            Suggestion.workspace_id == workspace_id,
            Suggestion.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        .order_by(_priority_order(), Suggestion.created_at.desc())  # type: ignore[union-attr]
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _get_suggestion(
    session: AsyncSession,
    workspace_id: UUID,
    suggestion_id: UUID,
) -> Suggestion:
    stmt = select(Suggestion).where(
        Suggestion.id == suggestion_id,
        Suggestion.workspace_id == workspace_id,
        Suggestion.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise SuggestionNotFoundError(str(suggestion_id))
    return suggestion


async def dismiss_suggestion(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    suggestion_id: UUID,
) -> Suggestion:
    """Dismiss an exact suggestion instance."""
    suggestion = await _get_suggestion(session, workspace_id, suggestion_id)
    now = _now()
    suggestion.status = SUGGESTION_STATUS_DISMISSED
    suggestion.dismissed_at = now
    suggestion.snoozed_until = None
    suggestion.updated_by_user_id = user_id
    await log_audit_event(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        action="suggestion_dismissed",
        resource_type="suggestion",
        resource_id=suggestion.id,
        details={"type": suggestion.type, "fingerprint": suggestion.fingerprint},
    )
    await session.flush()
    return suggestion


async def snooze_suggestion(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    suggestion_id: UUID,
    snoozed_until: datetime | None = None,
) -> Suggestion:
    """Snooze a suggestion until the provided timestamp, defaulting to seven days."""
    suggestion = await _get_suggestion(session, workspace_id, suggestion_id)
    suggestion.status = SUGGESTION_STATUS_SNOOZED
    suggestion.snoozed_until = snoozed_until or (_now() + timedelta(days=7))
    suggestion.dismissed_at = None
    suggestion.resolved_at = None
    suggestion.updated_by_user_id = user_id
    await log_audit_event(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        action="suggestion_snoozed",
        resource_type="suggestion",
        resource_id=suggestion.id,
        details={
            "type": suggestion.type,
            "fingerprint": suggestion.fingerprint,
            "snoozed_until": _iso(suggestion.snoozed_until),
        },
    )
    await session.flush()
    return suggestion


async def resolve_suggestion(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    suggestion_id: UUID,
) -> Suggestion:
    """Mark a suggestion handled without requiring a downstream artifact."""
    suggestion = await _get_suggestion(session, workspace_id, suggestion_id)
    suggestion.status = SUGGESTION_STATUS_RESOLVED
    suggestion.resolved_at = _now()
    suggestion.snoozed_until = None
    suggestion.updated_by_user_id = user_id
    await log_audit_event(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        action="suggestion_resolved",
        resource_type="suggestion",
        resource_id=suggestion.id,
        details={"type": suggestion.type, "fingerprint": suggestion.fingerprint},
    )
    await session.flush()
    return suggestion


async def reopen_suggestion(
    session: AsyncSession,
    workspace_id: UUID,
    user_id: UUID,
    suggestion_id: UUID,
) -> Suggestion:
    """Manually reopen a dismissed, resolved, or snoozed suggestion."""
    suggestion = await _get_suggestion(session, workspace_id, suggestion_id)
    suggestion.status = SUGGESTION_STATUS_OPEN
    suggestion.reopened_at = _now()
    suggestion.dismissed_at = None
    suggestion.resolved_at = None
    suggestion.snoozed_until = None
    suggestion.updated_by_user_id = user_id
    await log_audit_event(
        session,
        workspace_id=workspace_id,
        user_id=user_id,
        action="suggestion_reopened",
        resource_type="suggestion",
        resource_id=suggestion.id,
        details={"type": suggestion.type, "fingerprint": suggestion.fingerprint},
    )
    await session.flush()
    return suggestion


def _flatten_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _skip_design_review_assessment(reason: str) -> DesignReviewGapAssessment:
    return DesignReviewGapAssessment(
        should_suggest=False,
        reason=reason,
        confidence=1.0,
    )


def _has_design_or_meeting_evidence(decision: GraphNode) -> bool:
    source_text = " ".join(
        [
            decision.source_type or "",
            _flatten_text(decision.properties or {}),
        ]
    ).lower()
    return any(
        marker in source_text
        for marker in ("figma", "design review", "design_review", "fathom", "meeting")
    )


DESIGN_REVIEW_GAP_SYSTEM_PROMPT = """\
You are a relevance judge for ContextOS dashboard suggestions.

Decide whether an existing graph Decision should surface a
"missing design review evidence" suggestion.

Rules:
- Return should_suggest=true only for user-facing product, interface,
  visual, content, or UX decisions where a design review source would
  materially improve the decision record.
- Return should_suggest=false for engineering process, branch naming,
  deployment, backend/API, schema, infra, alerting, SMS/notification
  operations, work tracking, salary/payment-routing, or customer-ops
  decisions unless the source explicitly says the decision changes a
  user-facing screen, interaction, visual treatment, or product copy.
- Return should_suggest=false for enable/disable/default/configuration
  decisions on an already-existing UI unless the source says the visual
  design, product copy, UX flow, layout, or interaction itself is new or
  changed.
- Source channel names are weak evidence. A product-design channel alone
  is not enough.
- If the decision is ambiguous, return should_suggest=false. False positives
  are worse than missing a low-confidence suggestion.
- Ground the reason in the provided decision fields. Do not invent missing
  sources.
"""


def _decision_relevance_payload(
    decision: GraphNode,
    present_evidence: list[str],
) -> dict[str, object]:
    props = decision.properties or {}
    compact_props = {
        key: props[key]
        for key in (
            "source",
            "source_channel",
            "rationale",
            "source_quote",
            "participants",
            "date",
            "ticket_refs",
            "affected_systems",
        )
        if key in props and props[key] not in (None, "", [])
    }
    return {
        "decision_title": decision.name,
        "decision_source_type": decision.source_type,
        "present_evidence": present_evidence,
        "decision_properties": compact_props,
    }


async def assess_design_review_gap(
    workspace_id: UUID,
    decision: GraphNode,
    *,
    present_evidence: list[str] | None = None,
    llm_client: LLMClient | None = None,
) -> DesignReviewGapAssessment:
    """Ask the relevance agent if a design-review coverage suggestion should exist."""
    evidence = present_evidence or _present_evidence_labels(decision)
    if not evidence:
        return _skip_design_review_assessment(
            "No concrete source evidence is attached."
        )
    if _has_design_or_meeting_evidence(decision):
        return _skip_design_review_assessment(
            "Design or meeting evidence already exists."
        )

    if llm_client is None and not get_settings().GEMINI_API_KEY:
        return _skip_design_review_assessment(
            "LLM relevance assessment is unavailable."
        )

    payload = _decision_relevance_payload(decision, evidence)
    prompt = (
        "Assess this graph Decision for a missing design-review evidence "
        "suggestion.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )

    try:
        client = llm_client or get_llm_client()
        return await client.generate_json(
            prompt=prompt,
            schema=DesignReviewGapAssessment,
            system_prompt=DESIGN_REVIEW_GAP_SYSTEM_PROMPT,
            workspace_id=workspace_id,
        )
    except Exception:
        logger.warning(
            "Design-review relevance assessment failed for decision %s",
            decision.id,
            exc_info=True,
        )
        return _skip_design_review_assessment("LLM relevance assessment failed.")


def _present_evidence_labels(decision: GraphNode) -> list[str]:
    props = decision.properties or {}
    source = str(props.get("source") or decision.source_type or "").lower()
    labels: list[str] = []
    if "slack" in source or "slack" in str(props.get("source_channel", "")).lower():
        labels.append("Slack")
    if "telegram" in source:
        labels.append("Telegram")
    if "github" in source:
        labels.append("PR evidence")
    if "gitlab" in source:
        labels.append("MR evidence")
    if decision.source_type == "messages_digest" and not labels:
        labels.append("message digest")
    return labels


def _missing_source_fingerprint(
    workspace_id: UUID,
    decision: GraphNode,
    present_evidence: list[str],
) -> str:
    material = "|".join(
        [
            str(workspace_id),
            SUGGESTION_TYPE_MISSING_SOURCE,
            str(decision.id),
            MISSING_DESIGN_EVIDENCE,
            ",".join(sorted(present_evidence)),
            str((decision.properties or {}).get("date") or ""),
            decision.name,
        ]
    )
    digest = hashlib.sha256(material.encode()).hexdigest()
    return f"missing-source:{digest}"


def build_missing_source_suggestion(
    workspace_id: UUID,
    decision: GraphNode,
    *,
    assessment: DesignReviewGapAssessment | None = None,
    present_evidence: list[str] | None = None,
) -> Suggestion | None:
    """Build a concrete missing-source suggestion after a relevance verdict."""
    present_evidence = present_evidence or _present_evidence_labels(decision)
    if (
        not present_evidence
        or assessment is None
        or not assessment.should_suggest
        or assessment.confidence < DESIGN_REVIEW_CONFIDENCE_THRESHOLD
        or _has_design_or_meeting_evidence(decision)
    ):
        return None

    present_label = " and ".join(present_evidence)
    body = f"{present_label} evidence exists, but no design review is linked."
    fingerprint = _missing_source_fingerprint(workspace_id, decision, present_evidence)
    props = decision.properties or {}
    evidence = {
        "source_refs": [
            {
                "type": decision.source_type,
                "id": str(decision.source_id) if decision.source_id else None,
            }
        ],
        "present_evidence": present_evidence,
        "missing_evidence": [MISSING_DESIGN_EVIDENCE],
        "snippets": [
            value
            for value in [
                props.get("source_quote"),
                props.get("rationale"),
            ]
            if isinstance(value, str) and value.strip()
        ],
    }
    details = {
        "decision_title": decision.name,
        "missing_evidence_type": MISSING_DESIGN_EVIDENCE,
        "coverage_assessment": assessment.model_dump(),
    }
    provenance = {
        "generator": MISSING_SOURCE_COVERAGE_GENERATOR,
        "source": "graph_decision",
        "decision_fingerprint": decision.fingerprint,
    }
    return Suggestion(
        workspace_id=workspace_id,
        type=SUGGESTION_TYPE_MISSING_SOURCE,
        status=SUGGESTION_STATUS_OPEN,
        priority="medium",
        fingerprint=fingerprint,
        entity_type="graph_node",
        entity_id=decision.id,
        title=f"Review design evidence for {decision.name}",
        body=body,
        primary_action=MISSING_SOURCE_PRIMARY_ACTION,
        action_href=f"/dashboard/decisions/{decision.id}",
        evidence=evidence,
        details=details,
        provenance=provenance,
        last_seen_at=_now(),
    )


def _is_generated_missing_source_suggestion(suggestion: Suggestion) -> bool:
    generator = str((suggestion.provenance or {}).get("generator") or "")
    return generator.startswith("missing_source_coverage:")


async def _find_generated_candidates_for_decision(
    session: AsyncSession,
    workspace_id: UUID,
    entity_type: str | None,
    entity_id: UUID | None,
) -> list[Suggestion]:
    stmt = select(Suggestion).where(
        Suggestion.workspace_id == workspace_id,
        Suggestion.type == SUGGESTION_TYPE_MISSING_SOURCE,
        Suggestion.entity_type == entity_type,
        Suggestion.entity_id == entity_id,
    )
    result = await session.execute(stmt)
    return [
        suggestion
        for suggestion in result.scalars().all()
        if _is_generated_missing_source_suggestion(suggestion)
    ]


def _retire_superseded_candidates(
    candidates: list[Suggestion],
    built: Suggestion | None = None,
) -> None:
    now = _now()
    for candidate in candidates:
        if built is not None and candidate.fingerprint == built.fingerprint:
            continue
        if candidate.deleted_at is None:
            candidate.deleted_at = now


async def _retire_generated_candidates_for_decision(
    session: AsyncSession,
    workspace_id: UUID,
    decision: GraphNode,
) -> None:
    candidates = await _find_generated_candidates_for_decision(
        session,
        workspace_id,
        "graph_node",
        decision.id,
    )
    _retire_superseded_candidates(candidates)


async def _has_design_evidence_provider(
    session: AsyncSession,
    workspace_id: UUID,
) -> bool:
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider.in_(DESIGN_EVIDENCE_PROVIDERS),  # type: ignore[attr-defined]
        WorkspaceIntegration.status == "connected",
        WorkspaceIntegration.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _retire_generated_missing_source_suggestions(
    session: AsyncSession,
    workspace_id: UUID,
) -> None:
    stmt = select(Suggestion).where(
        Suggestion.workspace_id == workspace_id,
        Suggestion.type == SUGGESTION_TYPE_MISSING_SOURCE,
        Suggestion.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    result = await session.execute(stmt)
    _retire_superseded_candidates(
        [
            suggestion
            for suggestion in result.scalars().all()
            if _is_generated_missing_source_suggestion(suggestion)
        ]
    )


async def refresh_missing_source_coverage_suggestions(
    session: AsyncSession,
    workspace_id: UUID,
    *,
    decision_ids: list[UUID] | None = None,
    limit: int = 50,
    llm_client: LLMClient | None = None,
) -> list[Suggestion]:
    """Create or refresh missing-source suggestions for concrete Decision nodes."""
    if not await _has_design_evidence_provider(session, workspace_id):
        await _retire_generated_missing_source_suggestions(session, workspace_id)
        await session.flush()
        return []

    stmt = select(GraphNode).where(
        GraphNode.workspace_id == workspace_id,
        GraphNode.entity_type == "Decision",
        GraphNode.deleted_at.is_(None),  # type: ignore[union-attr]
    )
    if decision_ids:
        stmt = stmt.where(GraphNode.id.in_(decision_ids))  # type: ignore[attr-defined]
    stmt = stmt.order_by(GraphNode.created_at.desc()).limit(limit)  # type: ignore[union-attr]
    result = await session.execute(stmt)

    suggestions: list[Suggestion] = []
    for decision in result.scalars().all():
        present_evidence = _present_evidence_labels(decision)
        if not present_evidence or _has_design_or_meeting_evidence(decision):
            await _retire_generated_candidates_for_decision(
                session,
                workspace_id,
                decision,
            )
            continue

        assessment = await assess_design_review_gap(
            workspace_id,
            decision,
            present_evidence=present_evidence,
            llm_client=llm_client,
        )
        built = build_missing_source_suggestion(
            workspace_id,
            decision,
            assessment=assessment,
            present_evidence=present_evidence,
        )
        if built is None:
            await _retire_generated_candidates_for_decision(
                session,
                workspace_id,
                decision,
            )
            continue

        candidates = await _find_generated_candidates_for_decision(
            session,
            workspace_id,
            built.entity_type,
            built.entity_id,
        )
        existing = next(
            (
                candidate
                for candidate in candidates
                if candidate.fingerprint == built.fingerprint
            ),
            None,
        )
        _retire_superseded_candidates(candidates, built)

        if existing is None:
            session.add(built)
            suggestions.append(built)
            continue

        was_deleted = existing.deleted_at is not None
        if was_deleted:
            existing.deleted_at = None
            existing.status = SUGGESTION_STATUS_OPEN
            existing.snoozed_until = None
            existing.dismissed_at = None
            existing.resolved_at = None
        existing.last_seen_at = _now()
        if was_deleted or existing.status in {
            SUGGESTION_STATUS_OPEN,
            SUGGESTION_STATUS_SNOOZED,
        }:
            existing.title = built.title
            existing.body = built.body
            existing.priority = built.priority
            existing.primary_action = built.primary_action
            existing.action_href = built.action_href
            existing.evidence = built.evidence
            existing.details = built.details
            existing.provenance = built.provenance
            suggestions.append(existing)

    await session.flush()
    return suggestions
