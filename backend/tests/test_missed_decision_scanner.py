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
        sources_total=42,
        review_candidates=3,
        auto_saved=2,
        suppressed=1,
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
    assert run.sources_total == 42
    assert run.review_candidates == 3
    assert run.auto_saved == 2
    assert run.suppressed == 1
    assert candidate.lifecycle_status == "detected"
    assert candidate.evidence["source"] == "slack"
    assert candidate.people == ["Daulet"]
    assert candidate.affected_systems == ["dashboard"]


def test_missed_decision_scan_timestamps_use_timezone_aware_columns() -> None:
    timestamp_columns = [
        MissedDecisionScanState.__table__.c.last_missed_decision_scan_at,
        MissedDecisionScanRun.__table__.c.source_window_start,
        MissedDecisionScanRun.__table__.c.source_window_end,
        MissedDecisionScanRun.__table__.c.started_at,
        MissedDecisionScanRun.__table__.c.completed_at,
        MissedDecisionCandidate.__table__.c.detected_at,
        MissedDecisionCandidate.__table__.c.surfaced_at,
        MissedDecisionCandidate.__table__.c.resolved_at,
    ]

    assert all(column.type.timezone for column in timestamp_columns)


def test_missed_decision_scan_run_tracks_source_totals() -> None:
    column = MissedDecisionScanRun.__table__.c.sources_total

    assert column.nullable
    assert "sources_total" in MissedDecisionScanRun.model_fields
    assert "review_candidates" in MissedDecisionScanRun.model_fields
    assert "auto_saved" in MissedDecisionScanRun.model_fields
    assert "suppressed" in MissedDecisionScanRun.model_fields


def test_missed_decision_migration_defines_workspace_rls_and_lifecycles() -> None:
    migration = Path("../supabase/migrations/00042_missed_decisions.sql")
    sql = migration.read_text()

    assert "missed_decision_scan_state" in sql
    assert "missed_decision_scan_runs" in sql
    assert "missed_decision_candidates" in sql
    assert "last_missed_decision_scan_at" in sql
    assert "sources_total" in sql
    assert "review_candidates" in sql
    assert "auto_saved" in sql
    assert "suppressed" in sql
    assert "workspace_members" in sql
    assert "status IN ('queued', 'running', 'succeeded', 'failed')" in sql
    assert (
        "lifecycle_status IN ('detected', 'surfaced', 'suppressed', 'linked', "
        "'confirmed', 'rejected', 'deferred')"
    ) in sql


def test_reliability_counts_migration_dedupes_before_unique_index() -> None:
    migration = Path(
        "../supabase/migrations/00045_missed_decision_reliability_counts.sql"
    )
    sql = migration.read_text()
    dedupe_index = sql.index("duplicate_live_candidates")
    unique_index = sql.index("CREATE UNIQUE INDEX")

    assert dedupe_index < unique_index
    assert "ROW_NUMBER() OVER" in sql
    assert "deleted_at = now()" in sql
    assert "duplicate_existing_decision" in sql


@pytest.mark.asyncio
async def test_first_scan_window_uses_full_14_day_default_lookback() -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_one(None))
    session.add = MagicMock()
    session.flush = AsyncMock()
    workspace_id = uuid4()
    now = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)

    window = await scanner.get_scan_window(
        session,
        workspace_id,
        "slack_message",
        sync_completed_at=now,
    )

    assert window.start == now - timedelta(days=14)
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
async def test_enqueue_skips_when_source_scan_is_already_active() -> None:
    class Savepoint:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    session = AsyncMock()
    session.begin_nested = MagicMock(return_value=Savepoint())
    session.execute = AsyncMock(return_value=_result_one(uuid4()))
    session.add = MagicMock()

    result = await scanner.enqueue_missed_decision_scan(
        session,
        uuid4(),
        "telegram_message",
    )

    assert result is None
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_active_scan_scope_includes_source_resource() -> None:
    from sqlalchemy.dialects import postgresql

    captured_sql = ""

    class Savepoint:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return False

    async def fake_execute(stmt):
        nonlocal captured_sql
        captured_sql = str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        return _result_one(uuid4())

    session = AsyncMock()
    session.begin_nested = MagicMock(return_value=Savepoint())
    session.execute = AsyncMock(side_effect=fake_execute)
    session.add = MagicMock()

    result = await scanner.enqueue_missed_decision_scan(
        session,
        uuid4(),
        "slack_message",
        source_resource_id="C123",
    )

    assert result is None
    assert "source_resource_id = 'C123'" in captured_sql
    session.add.assert_not_called()


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
async def test_drain_supersedes_duplicate_active_runs_for_same_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    latest = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="telegram_message",
        status="running",
        created_at=datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
    )
    older = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="telegram_message",
        status="running",
        created_at=datetime(2026, 5, 25, 9, 0, tzinfo=UTC),
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_all([latest, older]))
    session.flush = AsyncMock()

    processed: list[MissedDecisionScanRun] = []

    async def fake_run_once(_session, scan_run):
        processed.append(scan_run)
        scan_run.status = "succeeded"

    monkeypatch.setattr(scanner, "run_missed_decision_scan_once", fake_run_once)

    count = await scanner.drain_queued_missed_decision_scans(session, limit=5)

    assert count == 1
    assert processed == [latest]
    assert older.status == "failed"
    assert older.error_message == "Superseded by a newer active scan for this source."
    assert older.completed_at is not None


@pytest.mark.asyncio
async def test_drain_allows_parallel_runs_for_different_source_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    first = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="slack_message",
        source_resource_id="C123",
        status="queued",
        created_at=datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
    )
    second = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="slack_message",
        source_resource_id="C456",
        status="queued",
        created_at=datetime(2026, 5, 25, 9, 0, tzinfo=UTC),
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_all([first, second]))
    session.flush = AsyncMock()
    processed: list[MissedDecisionScanRun] = []

    async def fake_run_once(_session, scan_run):
        processed.append(scan_run)
        scan_run.status = "succeeded"

    monkeypatch.setattr(scanner, "run_missed_decision_scan_once", fake_run_once)

    count = await scanner.drain_queued_missed_decision_scans(session, limit=5)

    assert count == 2
    assert processed == [first, second]


@pytest.mark.asyncio
async def test_drain_reclaims_running_runs_only_after_stale_heartbeat() -> None:
    from sqlalchemy.dialects import postgresql

    session = AsyncMock()
    session.flush = AsyncMock()
    captured_sql = ""

    async def fake_execute(stmt):
        nonlocal captured_sql
        captured_sql = str(
            stmt.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        return _result_all([])

    session.execute = AsyncMock(side_effect=fake_execute)

    count = await scanner.drain_queued_missed_decision_scans(session, limit=5)

    assert count == 0
    assert "missed_decision_scan_runs.started_at <" in captured_sql
    assert "missed_decision_scan_runs.updated_at <" in captured_sql
    assert "created_at DESC" in captured_sql


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
        return {
            "candidates_created": 1,
            "review_candidates": 1,
            "auto_saved": 0,
            "suppressed": 0,
        }

    monkeypatch.setattr(scanner, "load_source_window", fake_load_window)
    monkeypatch.setattr(scanner, "process_missed_decision_source_window", fake_process)

    await scanner.run_missed_decision_scan_once(session, run)

    assert run.status == "succeeded"
    assert run.sources_scanned == 1
    assert run.candidates_created == 1
    assert run.review_candidates == 1
    assert run.auto_saved == 0
    assert run.suppressed == 0
    assert run.error_message is None
    assert run.completed_at is not None
    state = session.add.call_args.args[0]
    assert state.last_missed_decision_scan_at == source_time


@pytest.mark.asyncio
async def test_run_sets_sources_total_once_at_scan_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    source_window_start = datetime(2026, 5, 24, 9, 0, tzinfo=UTC)
    source_window_end = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    run = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="slack_message",
        source_resource_id="C123",
        status="running",
        source_window_start=source_window_start,
        source_window_end=source_window_end,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_one(None))
    session.add = MagicMock()
    session.flush = AsyncMock()
    count_calls = []

    async def fake_count_source_window(*args, **kwargs):
        count_calls.append((args, kwargs))
        return 17

    async def fake_load_window(*_args, **_kwargs):
        return []

    monkeypatch.setattr(
        scanner,
        "count_source_window",
        fake_count_source_window,
        raising=False,
    )
    monkeypatch.setattr(scanner, "load_source_window", fake_load_window)

    await scanner.run_missed_decision_scan_once(session, run)

    assert run.sources_total == 17
    assert len(count_calls) == 1
    args, kwargs = count_calls[0]
    assert args[1] == workspace_id
    assert args[2] == "slack_message"
    assert args[3] == source_window_start
    assert args[4] == source_window_end
    assert kwargs["source_resource_id"] == "C123"


@pytest.mark.asyncio
async def test_run_processes_source_window_in_cursor_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    source_window_end = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    run = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="slack_message",
        status="running",
        source_window_end=source_window_end,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_one(None))
    session.add = MagicMock()
    session.flush = AsyncMock()
    records = [
        MissedDecisionSourceRecord(
            workspace_id=workspace_id,
            source_type="slack_message",
            source_id=uuid4(),
            text=f"We decided to preserve evidence batch {i}.",
            source_link=build_internal_source_reference(
                "slack_message",
                workspace_id,
                uuid4(),
                source_window_end + timedelta(minutes=i),
            ),
            source_created_at=source_window_end + timedelta(minutes=i),
            metadata={},
        )
        for i in range(3)
    ]
    load_calls = []
    processed_batches = []

    async def fake_load_window(
        _session,
        _workspace_id,
        _source_type,
        _start,
        _end,
        *,
        limit,
        after_source_created_at=None,
        after_source_id=None,
        source_resource_id=None,
    ):
        load_calls.append((limit, after_source_created_at, after_source_id))
        if after_source_created_at is None:
            start_index = 0
        else:
            start_index = next(
                i + 1
                for i, record in enumerate(records)
                if record.source_created_at == after_source_created_at
                and record.source_id == after_source_id
            )
        return records[start_index : start_index + limit]

    async def fake_process(_session, _scan_run, batch):
        processed_batches.append([record.source_id for record in batch])
        return {
            "candidates_created": len(batch),
            "review_candidates": len(batch),
            "auto_saved": 0,
            "suppressed": 0,
        }

    monkeypatch.setattr(scanner, "SOURCE_WINDOW_BATCH_SIZE", 2)
    monkeypatch.setattr(scanner, "load_source_window", fake_load_window)
    monkeypatch.setattr(scanner, "process_missed_decision_source_window", fake_process)

    await scanner.run_missed_decision_scan_once(session, run)

    assert [call[0] for call in load_calls] == [2, 2]
    assert load_calls[1][1] == records[1].source_created_at
    assert load_calls[1][2] == records[1].source_id
    assert processed_batches == [
        [records[0].source_id, records[1].source_id],
        [records[2].source_id],
    ]
    assert run.sources_scanned == 3
    assert run.candidates_created == 3
    assert run.review_candidates == 3
    state = session.add.call_args.args[0]
    assert state.last_missed_decision_scan_at == source_window_end


@pytest.mark.asyncio
async def test_run_commits_progress_every_five_sources_within_large_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    source_window_end = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    run = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="slack_message",
        status="running",
        source_window_end=source_window_end,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_one(None))
    session.add = MagicMock()
    session.flush = AsyncMock()
    commit_snapshots: list[int] = []

    async def fake_commit():
        commit_snapshots.append(run.sources_scanned)

    session.commit = AsyncMock(side_effect=fake_commit)
    records = [
        MissedDecisionSourceRecord(
            workspace_id=workspace_id,
            source_type="slack_message",
            source_id=uuid4(),
            text=f"We decided to preserve evidence item {index}.",
            source_link=build_internal_source_reference(
                "slack_message",
                workspace_id,
                uuid4(),
                source_window_end + timedelta(minutes=index),
            ),
            source_created_at=source_window_end + timedelta(minutes=index),
            metadata={},
        )
        for index in range(12)
    ]
    load_calls = 0
    processed_sizes: list[int] = []

    async def fake_count_source_window(*_args, **_kwargs):
        return len(records)

    async def fake_load_window(*_args, **_kwargs):
        nonlocal load_calls
        load_calls += 1
        return records if load_calls == 1 else []

    async def fake_process(_session, _scan_run, batch):
        processed_sizes.append(len(batch))
        return {
            "candidates_created": len(batch),
            "review_candidates": len(batch),
            "auto_saved": 0,
            "suppressed": 0,
        }

    monkeypatch.setattr(scanner, "SOURCE_WINDOW_BATCH_SIZE", 12)
    monkeypatch.setattr(
        scanner,
        "count_source_window",
        fake_count_source_window,
        raising=False,
    )
    monkeypatch.setattr(scanner, "load_source_window", fake_load_window)
    monkeypatch.setattr(scanner, "process_missed_decision_source_window", fake_process)

    await scanner.run_missed_decision_scan_once(session, run)

    assert processed_sizes == [5, 5, 2]
    assert 5 in commit_snapshots
    assert 10 in commit_snapshots
    assert 12 in commit_snapshots
    assert run.sources_scanned == 12
    assert run.candidates_created == 12


@pytest.mark.asyncio
async def test_run_uses_newer_checkpoint_when_queued_scan_window_is_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_id = uuid4()
    queued_start = datetime(2026, 5, 13, 9, 0, tzinfo=UTC)
    checkpoint = datetime(2026, 5, 25, 9, 0, tzinfo=UTC)
    source_window_end = datetime(2026, 5, 25, 10, 0, tzinfo=UTC)
    state = MissedDecisionScanState(
        workspace_id=workspace_id,
        source_type="telegram_message",
        last_missed_decision_scan_at=checkpoint,
    )
    run = MissedDecisionScanRun(
        workspace_id=workspace_id,
        source_type="telegram_message",
        status="running",
        source_window_start=queued_start,
        source_window_end=source_window_end,
    )
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_result_one(state))
    session.flush = AsyncMock()
    load_args = None

    async def fake_load_window(*args, **_kwargs):
        nonlocal load_args
        load_args = args
        return []

    monkeypatch.setattr(scanner, "load_source_window", fake_load_window)

    await scanner.run_missed_decision_scan_once(session, run)

    assert run.status == "succeeded"
    assert run.source_window_start == checkpoint
    assert load_args is not None
    assert load_args[3] == checkpoint
    assert state.last_missed_decision_scan_at == source_window_end


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
    record = MissedDecisionSourceRecord(
        workspace_id=workspace_id,
        source_type="slack_message",
        source_id=uuid4(),
        text="We decided to keep source-backed review.",
        source_link=build_internal_source_reference(
            "slack_message",
            workspace_id,
            uuid4(),
            checkpoint,
        ),
        source_created_at=checkpoint,
        metadata={},
    )

    async def fake_load_window(*_args, **_kwargs):
        return [record]

    async def failing_process(*_args, **_kwargs):
        raise RuntimeError("extractor unavailable")

    monkeypatch.setattr(scanner, "load_source_window", fake_load_window)
    monkeypatch.setattr(
        scanner,
        "process_missed_decision_source_window",
        failing_process,
    )

    await scanner.run_missed_decision_scan_once(session, run)

    assert run.status == "failed"
    assert "extractor unavailable" in (run.error_message or "")
    assert state.last_missed_decision_scan_at == checkpoint
