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
