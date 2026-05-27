"""Tests for GitLab Redis Stream sync worker recovery."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest


class _FakeRedisWithPending:
    def __init__(self) -> None:
        self.acked: list[tuple[str, str, str]] = []
        self.closed = False
        self._claimed = False

    async def xgroup_create(self, *_args, **_kwargs):
        return None

    async def xautoclaim(self, *_args, **_kwargs):
        if self._claimed:
            return ("0-0", [], [])
        self._claimed = True
        return (
            "0-0",
            [
                (
                    "1779890172644-0",
                    {
                        "data": json.dumps(
                            {
                                "workspace_id": "22222222-2222-2222-2222-222222222222",
                                "project_ids": [25911339],
                                "state_filter": "all",
                            }
                        )
                    },
                )
            ],
            [],
        )

    async def xreadgroup(self, *_args, **_kwargs):
        raise asyncio.CancelledError

    async def xack(self, stream_key: str, group_name: str, msg_id: str):
        self.acked.append((stream_key, group_name, msg_id))

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_worker_reclaims_and_acks_stale_pending_jobs():
    """A restarted worker should process old pending jobs before new messages."""
    from src.services import gitlab_sync_worker

    fake_redis = _FakeRedisWithPending()

    with (
        patch("src.services.gitlab_sync_worker._get_redis", return_value=fake_redis),
        patch(
            "src.services.gitlab_sync_worker._process_sync_message",
            new_callable=AsyncMock,
        ) as process_message,
    ):
        with pytest.raises(asyncio.CancelledError):
            await gitlab_sync_worker.run_gitlab_sync_worker()

    process_message.assert_awaited_once()
    assert fake_redis.acked == [
        (
            gitlab_sync_worker.STREAM_KEY,
            gitlab_sync_worker.GROUP_NAME,
            "1779890172644-0",
        )
    ]
    assert fake_redis.closed is True
