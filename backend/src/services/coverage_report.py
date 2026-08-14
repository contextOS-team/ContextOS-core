"""Decision Coverage Audit: the sales artifact.

Aggregates the current decision state + drift outcomes for a workspace over a
lookback window into the headline the audit sells:

    "27 consequential decisions reconstructed — 21 aligned, 4 uncertain,
     2 drifts (1 already resolved)."

Pure SELECTs over decisions / expected_consequences / drifts — no new tables.

Definitions:
- reconstructed: active decisions above the consequentiality gate (score >= 0.6
  or not-yet-scored) with valid_from in the window
- aligned: reconstructed decisions whose checked consequences are all consistent
  and that have no open drift
- drifted: reconstructed decisions with an open (unresolved) drift
- uncertain: the rest — consequences still pending, or none inferred yet
"""

from uuid import UUID

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

CONSEQUENTIALITY_GATE = 0.6


async def _scalar(session: AsyncSession, sql: str, params: dict) -> int:
    result = await session.execute(sa_text(sql), params)
    return int(result.scalar() or 0)


async def compute_coverage(
    session: AsyncSession, workspace_id: UUID, window_days: int = 90
) -> dict:
    p = {"ws": str(workspace_id), "gate": CONSEQUENTIALITY_GATE, "days": window_days}

    # Base: reconstructed decisions (active, consequential, in window).
    in_window = (
        "d.workspace_id = :ws AND d.deleted_at IS NULL AND d.status = 'active'"
        " AND (d.consequentiality_score IS NULL OR d.consequentiality_score >= :gate)"
        " AND d.valid_from >= now() - make_interval(days => :days)"
    )

    reconstructed = await _scalar(
        session, f"SELECT count(*) FROM decisions d WHERE {in_window}", p
    )

    # Drifted: reconstructed decisions with at least one open drift.
    drifted = await _scalar(
        session,
        f"""
        SELECT count(DISTINCT d.id) FROM decisions d
        JOIN drifts dr ON dr.decision_id = d.id
          AND dr.deleted_at IS NULL
          AND dr.resolved_at IS NULL
        WHERE {in_window}
        """,
        p,
    )

    # Aligned: reconstructed, >=1 checked consequence, all consistent, no drift.
    aligned = await _scalar(
        session,
        f"""
        SELECT count(*) FROM decisions d
        WHERE {in_window}
          AND EXISTS (
            SELECT 1 FROM expected_consequences ec
            WHERE ec.decision_id = d.id AND ec.deleted_at IS NULL
              AND ec.status = 'checked'
          )
          AND NOT EXISTS (
            SELECT 1 FROM expected_consequences ec2
            JOIN artifact_observations ao ON ao.expected_consequence_id = ec2.id
            WHERE ec2.decision_id = d.id AND ao.consistent IS FALSE
          )
          AND NOT EXISTS (
            SELECT 1 FROM drifts dr WHERE dr.decision_id = d.id
              AND dr.deleted_at IS NULL AND dr.resolved_at IS NULL
          )
        """,
        p,
    )

    uncertain = max(0, reconstructed - aligned - drifted)

    # Drift outcomes over the window.
    drift_window = (
        "dr.workspace_id = :ws AND dr.deleted_at IS NULL"
        " AND dr.detected_at >= now() - make_interval(days => :days)"
    )
    drifts_total = await _scalar(
        session, f"SELECT count(*) FROM drifts dr WHERE {drift_window}", p
    )
    drifts_confirmed = await _scalar(
        session,
        f"SELECT count(*) FROM drifts dr WHERE {drift_window}"
        " AND dr.confirmed_at IS NOT NULL",
        p,
    )
    drifts_resolved = await _scalar(
        session,
        f"SELECT count(*) FROM drifts dr WHERE {drift_window}"
        " AND dr.resolved_at IS NOT NULL",
        p,
    )
    # The killer metric: drifts that caused a real change.
    drifts_actioned = await _scalar(
        session,
        f"""
        SELECT count(*) FROM drifts dr WHERE {drift_window}
          AND dr.resolution_type IS NOT NULL
          AND dr.resolution_type <> 'intentional_exception'
        """,
        p,
    )

    # Resolution-type breakdown for the report body.
    breakdown_rows = await session.execute(
        sa_text(
            f"""
            SELECT dr.resolution_type, count(*) FROM drifts dr
            WHERE {drift_window} AND dr.resolution_type IS NOT NULL
            GROUP BY dr.resolution_type ORDER BY count(*) DESC
            """
        ),
        p,
    )
    resolution_breakdown = {row[0]: int(row[1]) for row in breakdown_rows.fetchall()}

    return {
        "window_days": window_days,
        "decisions": {
            "reconstructed": reconstructed,
            "aligned": aligned,
            "uncertain": uncertain,
            "drifted": drifted,
        },
        "drifts": {
            "total": drifts_total,
            "confirmed": drifts_confirmed,
            "resolved": drifts_resolved,
            "actioned": drifts_actioned,
            "resolution_breakdown": resolution_breakdown,
        },
    }
