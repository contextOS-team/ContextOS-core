"""Tests for GitLab router status helpers."""

from src.routers.gitlab import _normalize_project_sync_status


def test_normalize_project_sync_status_uses_complete_cursor():
    status = {
        "123": {"status": "syncing", "synced": 10, "total": 10},
        "456": {"status": "syncing", "synced": 2, "total": 8},
    }

    normalized = _normalize_project_sync_status(
        status,
        {"123": "complete", "456": "syncing"},
    )

    assert normalized["123"]["status"] == "synced"
    assert normalized["456"]["status"] == "syncing"
    assert status["123"]["status"] == "syncing"


def test_normalize_project_sync_status_treats_complete_progress_as_synced():
    status = {
        "123": {"status": "syncing", "synced": 10, "total": 10},
        "456": {"status": "syncing", "synced": 0, "total": 0},
    }

    normalized = _normalize_project_sync_status(status, {})

    assert normalized["123"]["status"] == "synced"
    assert normalized["456"]["status"] == "syncing"


def test_normalize_project_sync_status_uses_error_cursor():
    status = {
        "123": {"status": "syncing", "synced": 0, "total": 0},
        "456": {"status": "syncing", "synced": 3, "total": 3},
    }

    normalized = _normalize_project_sync_status(
        status,
        {"123": "error", "456": "timeout"},
    )

    assert normalized["123"]["status"] == "error"
    assert normalized["456"]["status"] == "timeout"


def test_normalize_project_sync_status_copies_cursor_error_message():
    status = {
        "123": {"status": "syncing", "synced": 0, "total": 0},
    }

    normalized = _normalize_project_sync_status(
        status,
        {"123": "error"},
        {"123": "No refresh token found -- reconnect GitLab"},
    )

    assert normalized["123"] == {
        "status": "error",
        "synced": 0,
        "total": 0,
        "error_message": "No refresh token found -- reconnect GitLab",
    }
