"""Tests for post-sync missed-decision scan state and queue orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.models.missed_decision import (
    MissedDecisionCandidate,
    MissedDecisionScanRun,
    MissedDecisionScanState,
)
from src.services import missed_decision_scanner as scanner
from src.services.missed_decision_sources import (
    MissedDecisionSourceRecord,
    build_internal_source_reference,
)


def _result_one(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _result_all(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


def test_missed_decision_models_capture_scan_and_candidate_contracts() -> None:
    workspace_id = uuid4()
    run_id = uuid4()

    state = MissedDecisionScanState(
        workspace_id=workspace_id,
        source_type="slack_message",
        source_resource_id="channel-1",
        last_missed_decision_scan_at=datetime(2026, 5, 24, tzinfo=UTC),
    )
    run = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="slack_message",
        source_resource_id="channel-1",
        status="queued",
        source_window_start=datetime(2026, 5, 24, tzinfo=UTC),
        source_window_end=datetime(2026, 5, 25, tzinfo=UTC),
        attempts=0,
    )
    candidate = MissedDecisionCandidate(
        workspace_id=workspace_id,
        scan_run_id=run_id,
        source_type="slack_message",
        source_id=uuid4(),
        source_quote="We decided to keep the dashboard right rail bounded.",
        inferred_decision="Keep dashboard review bounded",
        inferred_rationale="Avoid displacing confirmed decisions.",
        source_link="https://slack.example/archives/C123/p456",
        confidence="high",
        quote_fingerprint="quote:fingerprint",
        decision_fingerprint="decision:fingerprint",
        evidence={"source": "slack"},
        people=["Daulet"],
        affected_systems=["dashboard"],
    )

    assert state.last_missed_decision_scan_at is not None
    assert run.status == "queued"
    assert candidate.lifecycle_status == "detected"
    assert candidate.evidence["source"] == "slack"
    assert candidate.people == ["Daulet"]
    assert candidate.affected_systems == ["dashboard"]


def test_missed_decision_migration_defines_workspace_rls_and_lifecycles() -> None:
    migration = Path("../supabase/migrations/00042_missed_decisions.sql")
    sql = migration.read_text()

    assert "missed_decision_scan_state" in sql
    assert "missed_decision_scan_runs" in sql
    assert "missed_decision_candidates" in sql
    assert "last_missed_decision_scan_at" in sql
    assert "workspace_members" in sql
    assert "status IN ('queued', 'running', 'succeeded', 'failed')" in sql
    assert (
        "lifecycle_status IN ('detected', 'surfaced', 'suppressed', 'linked', "
        "'confirmed', 'rejected', 'deferred')"
    ) in sql


@pytest.mark.asyncio
async def test_first_scan_window_uses_later_of_connected_at_or_14_days() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_one(None))
    session.add = MagicMock()
    session.flush = AsyncMock()
    workspace_id = uuid4()
    now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
    connected_at = now - timedelta(days=3)

    window = await scanner.get_scan_window(
        session,
        workspace_id,
        "slack_message",
        sync_completed_at=now,
        source_connected_at=connected_at,
    )

    assert window.start == connected_at
    assert window.end == now
    assert window.state.workspace_id == workspace_id
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_existing_scan_window_starts_at_last_successful_checkpoint() -> None:
    workspace_id = uuid4()
    last_checkpoint = datetime(2026, 5, 24, 8, 30, tzinfo=UTC)
    state = MissedDecisionScanState(
        workspace_id=workspace_id,
        source_type="telegram_message",
        last_missed_decision_scan_at=last_checkpoint,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_one(state))
    session.add = MagicMock()

    window = await scanner.get_scan_window(
        session,
        workspace_id,
        "telegram_message",
        sync_completed_at=datetime(2026, 5, 25, 8, 30, tzinfo=UTC),
    )

    assert window.start == last_checkpoint
    assert session.add.call_count == 0


def test_internal_source_reference_is_workspace_scoped_and_timestamped() -> None:
    workspace_id = uuid4()
    source_id = uuid4()
    source_time = datetime(2026, 5, 25, 9, 45, tzinfo=UTC)

    reference = build_internal_source_reference(
        "telegram_message",
        workspace_id,
        source_id,
        source_time,
    )

    assert "telegram_message" in reference
    assert str(workspace_id) in reference
    assert str(source_id) in reference
    assert "2026-05-25T09:45:00" in reference


@pytest.mark.asyncio
async def test_enqueue_failures_are_swallowed() -> None:
    class FailingSavepoint:
        async def __aenter__(self):
            raise RuntimeError("insert failed")

        async def __aexit__(self, *_args):
            return False

    session = AsyncMock()
    session.begin_nested = MagicMock(return_value=FailingSavepoint())

    result = await scanner.enqueue_missed_decision_scan(
        session,
        uuid4(),
        "slack_message",
    )

    assert result is None


@pytest.mark.asyncio
async def test_drain_claims_queued_runs_once(monkeypatch: pytest.MonkeyPatch) -> None:
    run = MissedDecisionScanRun(
        workspace_id=uuid4(),
        source_type="slack_message",
        status="queued",
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_all([run]))
    session.flush = AsyncMock()

    processed: list[MissedDecisionScanRun] = []

    async def fake_run_once(_session, scan_run):
        processed.append(scan_run)
        scan_run.status = "succeeded"

    monkeypatch.setattr(scanner, "run_missed_decision_scan_once", fake_run_once)

    count = await scanner.drain_queued_missed_decision_scans(session, limit=5)

    assert count == 1
    assert processed == [run]
    assert run.attempts == 1


@pytest.mark.asyncio
async def test_run_success_advances_checkpoint_after_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    source_time = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    run = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="fathom_transcript",
        status="running",
        source_window_end=source_time,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_one(None))
    session.add = MagicMock()
    session.flush = AsyncMock()
    record = MissedDecisionSourceRecord(
        workspace_id=workspace_id,
        source_type="fathom_transcript",
        source_id=uuid4(),
        text="We decided to preserve Decision Receipts before actions.",
        source_link=build_internal_source_reference(
            "fathom_transcript",
            workspace_id,
            uuid4(),
            source_time,
        ),
        source_created_at=source_time,
        metadata={},
    )

    async def fake_load_window(*_args, **_kwargs):
        return [record]

    async def fake_process(*_args, **_kwargs):
        return {"candidates_created": 1}

    monkeypatch.setattr(scanner, "load_source_window", fake_load_window)
    monkeypatch.setattr(scanner, "process_missed_decision_source_window", fake_process)

    await scanner.run_missed_decision_scan_once(session, run)

    assert run.status == "succeeded"
    assert run.sources_scanned == 1
    assert run.candidates_created == 1
    assert run.error_message is None
    assert run.completed_at is not None
    state = session.add.call_args.args[0]
    assert state.last_missed_decision_scan_at == source_time


@pytest.mark.asyncio
async def test_run_failure_does_not_advance_checkpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    checkpoint = datetime(2026, 5, 24, 9, 0, tzinfo=UTC)
    state = MissedDecisionScanState(
        workspace_id=workspace_id,
        source_type="slack_message",
        last_missed_decision_scan_at=checkpoint,
    )
    run = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="slack_message",
        status="running",
        source_window_end=datetime(2026, 5, 25, 9, 0, tzinfo=UTC),
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_one(state))
    session.flush = AsyncMock()

    async def fake_load_window(*_args, **_kwargs):
        return []

    async def failing_process(*_args, **_kwargs):
        raise RuntimeError("extractor unavailable")

    monkeypatch.setattr(scanner, "load_source_window", fake_load_window)
    monkeypatch.setattr(scanner, "process_missed_decision_source_window", failing_process)

    await scanner.run_missed_decision_scan_once(session, run)

    assert run.status == "failed"
    assert "extractor unavailable" in (run.error_message or "")
    assert state.last_missed_decision_scan_at == checkpoint
