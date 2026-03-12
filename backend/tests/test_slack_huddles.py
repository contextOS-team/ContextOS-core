"""Tests for Slack huddle transcript ingestion service.

Covers:
- _find_huddle_messages filters only ended huddle messages from channel history
- _get_huddle_canvas_content returns canvas content when present
- _get_huddle_canvas_content returns None when no canvas in thread
- poll_huddle_transcripts end-to-end with mocked Slack API
- poll_huddle_transcripts deduplicates by huddle_room_id
- poll_huddle_transcripts creates minimal record for huddles without AI notes
- Duration calculated from room timestamps
- Participants resolved from user IDs to display names
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from tests.conftest import TEST_WORKSPACE_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_huddle_message(
    room_id: str = "R001",
    channel_id: str = "C001",
    has_ended: bool = True,
    date_start: int = 1700000000,
    date_end: int = 1700001800,  # 30 min later
    canvas_thread_ts: str | None = "1700000000.000100",
    participant_history: list[str] | None = None,
) -> dict:
    """Create a mock Slack message with huddle room data."""
    room = {
        "id": room_id,
        "call_family": "huddle",
        "has_ended": has_ended,
        "date_start": date_start,
        "date_end": date_end,
        "participant_history": participant_history or ["U001", "U002"],
    }
    if canvas_thread_ts:
        room["canvas_thread_ts"] = canvas_thread_ts
    return {
        "type": "message",
        "subtype": "huddle_thread",
        "ts": "1700000000.000000",
        "room": room,
    }


def _make_non_huddle_message() -> dict:
    """Create a regular Slack message (not a huddle)."""
    return {
        "type": "message",
        "text": "Hello world",
        "ts": "1700000001.000000",
    }


def _make_call_message() -> dict:
    """Create a Slack call message that is NOT a huddle (e.g., a regular call)."""
    return {
        "type": "message",
        "subtype": "huddle_thread",
        "ts": "1700000002.000000",
        "room": {
            "id": "R999",
            "call_family": "call",
            "has_ended": True,
            "date_start": 1700000000,
            "date_end": 1700001800,
        },
    }


# ---------------------------------------------------------------------------
# _find_huddle_messages
# ---------------------------------------------------------------------------

class TestFindHuddleMessages:
    """Tests for _find_huddle_messages helper."""

    @pytest.mark.asyncio
    async def test_filters_only_ended_huddles(self) -> None:
        """Only messages with room.call_family=='huddle' and has_ended are returned."""
        from src.services.slack_huddles import _find_huddle_messages

        history_response = {
            "ok": True,
            "messages": [
                _make_huddle_message(room_id="R001", has_ended=True),
                _make_non_huddle_message(),
                _make_call_message(),
                _make_huddle_message(room_id="R002", has_ended=False),  # not ended
            ],
            "has_more": False,
        }

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = history_response
        mock_client.get = AsyncMock(return_value=mock_response)

        results = await _find_huddle_messages(mock_client, "xoxb-token", "C001", None)

        assert len(results) == 1
        assert results[0]["room"]["id"] == "R001"

    @pytest.mark.asyncio
    async def test_paginates_channel_history(self) -> None:
        """_find_huddle_messages follows cursor pagination."""
        from src.services.slack_huddles import _find_huddle_messages

        page1 = {
            "ok": True,
            "messages": [_make_huddle_message(room_id="R001")],
            "has_more": True,
            "response_metadata": {"next_cursor": "cursor_page2"},
        }
        page2 = {
            "ok": True,
            "messages": [_make_huddle_message(room_id="R002")],
            "has_more": False,
        }

        mock_client = AsyncMock()
        mock_resp1 = MagicMock()
        mock_resp1.status_code = 200
        mock_resp1.json.return_value = page1
        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = page2
        mock_client.get = AsyncMock(side_effect=[mock_resp1, mock_resp2])

        results = await _find_huddle_messages(mock_client, "xoxb-token", "C001", None)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# _get_huddle_canvas_content
# ---------------------------------------------------------------------------

class TestGetHuddleCanvasContent:
    """Tests for _get_huddle_canvas_content helper."""

    @pytest.mark.asyncio
    async def test_returns_content_when_canvas_found(self) -> None:
        """Returns canvas content when a canvas file is found in thread."""
        from src.services.slack_huddles import _get_huddle_canvas_content

        replies_response = {
            "ok": True,
            "messages": [
                {
                    "ts": "1700000000.000100",
                    "text": "thread parent",
                },
                {
                    "ts": "1700000000.000200",
                    "files": [
                        {
                            "id": "F001",
                            "filetype": "canvas",
                            "url_private": "https://files.slack.com/canvas/F001",
                        }
                    ],
                },
            ],
        }

        file_info_response = {
            "ok": True,
            "content": "## Meeting Notes\n\nDiscussed sprint goals.",
        }

        mock_client = AsyncMock()

        # replies call
        mock_replies_resp = MagicMock()
        mock_replies_resp.status_code = 200
        mock_replies_resp.json.return_value = replies_response

        # files.info call
        mock_file_resp = MagicMock()
        mock_file_resp.status_code = 200
        mock_file_resp.json.return_value = file_info_response

        # download call
        mock_download_resp = MagicMock()
        mock_download_resp.status_code = 200
        mock_download_resp.text = "## Meeting Notes\n\nDiscussed sprint goals."

        mock_client.get = AsyncMock(
            side_effect=[mock_replies_resp, mock_file_resp, mock_download_resp]
        )

        content = await _get_huddle_canvas_content(
            mock_client, "xoxb-token", "C001", "1700000000.000100"
        )

        assert content is not None
        assert "Meeting Notes" in content

    @pytest.mark.asyncio
    async def test_returns_none_when_no_canvas(self) -> None:
        """Returns None when thread has no canvas files."""
        from src.services.slack_huddles import _get_huddle_canvas_content

        replies_response = {
            "ok": True,
            "messages": [
                {"ts": "1700000000.000100", "text": "thread parent"},
                {"ts": "1700000000.000200", "text": "just a text reply"},
            ],
        }

        mock_client = AsyncMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = replies_response
        mock_client.get = AsyncMock(return_value=mock_resp)

        content = await _get_huddle_canvas_content(
            mock_client, "xoxb-token", "C001", "1700000000.000100"
        )

        assert content is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_thread_ts(self) -> None:
        """Returns None when canvas_thread_ts is None."""
        from src.services.slack_huddles import _get_huddle_canvas_content

        mock_client = AsyncMock()

        content = await _get_huddle_canvas_content(
            mock_client, "xoxb-token", "C001", None
        )

        assert content is None
        mock_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# poll_huddle_transcripts (end-to-end)
# ---------------------------------------------------------------------------

class TestPollHuddleTranscripts:
    """Tests for poll_huddle_transcripts main entry point."""

    @pytest.mark.asyncio
    async def test_no_huddles_returns_zero(self) -> None:
        """poll_huddle_transcripts with no huddle messages returns ingested=0."""
        from src.services.slack_huddles import poll_huddle_transcripts

        mock_session = AsyncMock()

        # Mock integration query for selected channels and config
        mock_integration = MagicMock()
        mock_integration.config = {
            "selected_channels": ["C001"],
            "available_channels": [{"id": "C001", "name": "general"}],
        }
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_int_result)
        mock_session.commit = AsyncMock()

        with (
            patch(
                "src.services.slack_huddles.get_bot_token",
                return_value="xoxb-test-token",
            ),
            patch("src.services.slack_huddles.httpx.AsyncClient") as mock_httpx,
        ):
            mock_client = AsyncMock()
            # Empty channel history
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"ok": True, "messages": [], "has_more": False}
            mock_client.get = AsyncMock(return_value=mock_resp)

            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await poll_huddle_transcripts(
                mock_session, UUID(TEST_WORKSPACE_ID)
            )

        assert result["ingested"] == 0
        assert result["skipped"] == 0

    @pytest.mark.asyncio
    async def test_ingests_new_huddle(self) -> None:
        """poll_huddle_transcripts creates MeetingTranscript for a new huddle."""
        from src.services.slack_huddles import poll_huddle_transcripts

        mock_session = AsyncMock()
        added_objects = []
        mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        # First call: integration query (for selected channels)
        mock_integration = MagicMock()
        mock_integration.config = {
            "selected_channels": ["C001"],
            "available_channels": [{"id": "C001", "name": "general"}],
        }
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        # Dedup check: no existing transcript
        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None

        # Final integration update
        mock_int_result2 = MagicMock()
        mock_int_result2.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_int_result, mock_dedup_result, mock_int_result2]
        )

        huddle_msg = _make_huddle_message()

        with (
            patch(
                "src.services.slack_huddles.get_bot_token",
                return_value="xoxb-test-token",
            ),
            patch("src.services.slack_huddles.httpx.AsyncClient") as mock_httpx,
            patch("src.services.slack_huddles.embedding") as mock_embedding,
        ):
            mock_client = AsyncMock()

            # conversations.history -> one huddle
            mock_history_resp = MagicMock()
            mock_history_resp.status_code = 200
            mock_history_resp.json.return_value = {
                "ok": True,
                "messages": [huddle_msg],
                "has_more": False,
            }

            # conversations.replies -> canvas file
            mock_replies_resp = MagicMock()
            mock_replies_resp.status_code = 200
            mock_replies_resp.json.return_value = {
                "ok": True,
                "messages": [
                    {"ts": "1700000000.000100", "text": "parent"},
                    {
                        "ts": "1700000000.000200",
                        "files": [
                            {
                                "id": "F001",
                                "filetype": "canvas",
                                "url_private": "https://files.slack.com/canvas/F001",
                            }
                        ],
                    },
                ],
            }

            # files.info -- content returned directly, no download needed
            mock_file_resp = MagicMock()
            mock_file_resp.status_code = 200
            mock_file_resp.json.return_value = {
                "ok": True,
                "content": "Sprint retrospective notes.",
            }

            # users.info for U001 and U002
            mock_user1_resp = MagicMock()
            mock_user1_resp.status_code = 200
            mock_user1_resp.json.return_value = {
                "ok": True,
                "user": {"real_name": "Alice Smith", "profile": {"display_name": "alice"}},
            }
            mock_user2_resp = MagicMock()
            mock_user2_resp.status_code = 200
            mock_user2_resp.json.return_value = {
                "ok": True,
                "user": {"real_name": "Bob Jones", "profile": {"display_name": "bob"}},
            }

            mock_client.get = AsyncMock(
                side_effect=[
                    mock_history_resp,
                    mock_replies_resp,
                    mock_file_resp,
                    mock_user1_resp,
                    mock_user2_resp,
                ]
            )

            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_embedding.queue_embedding_generation = AsyncMock()

            result = await poll_huddle_transcripts(
                mock_session, UUID(TEST_WORKSPACE_ID)
            )

        assert result["ingested"] == 1
        assert result["skipped"] == 0

        from src.models.meeting import MeetingTranscript

        transcripts = [
            obj for obj in added_objects if isinstance(obj, MeetingTranscript)
        ]
        assert len(transcripts) == 1
        assert transcripts[0].source == "slack_huddle"
        assert transcripts[0].title == "Huddle in #general"
        assert "Sprint retrospective" in transcripts[0].transcript
        assert transcripts[0].raw_data["huddle_room_id"] == "R001"
        assert transcripts[0].duration_minutes == 30
        assert transcripts[0].participants == ["Alice Smith", "Bob Jones"]

        # Embedding was queued
        mock_embedding.queue_embedding_generation.assert_called_once()

    @pytest.mark.asyncio
    async def test_dedup_skips_existing_huddle(self) -> None:
        """poll_huddle_transcripts skips huddle already ingested (same huddle_room_id)."""
        from src.services.slack_huddles import poll_huddle_transcripts

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_integration = MagicMock()
        mock_integration.config = {
            "selected_channels": ["C001"],
            "available_channels": [{"id": "C001", "name": "general"}],
        }
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        # Dedup check: existing transcript found
        mock_existing = MagicMock()
        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = mock_existing

        mock_int_result2 = MagicMock()
        mock_int_result2.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_int_result, mock_dedup_result, mock_int_result2]
        )

        with (
            patch(
                "src.services.slack_huddles.get_bot_token",
                return_value="xoxb-test-token",
            ),
            patch("src.services.slack_huddles.httpx.AsyncClient") as mock_httpx,
            patch("src.services.slack_huddles.embedding") as mock_embedding,
        ):
            mock_client = AsyncMock()
            mock_history_resp = MagicMock()
            mock_history_resp.status_code = 200
            mock_history_resp.json.return_value = {
                "ok": True,
                "messages": [_make_huddle_message()],
                "has_more": False,
            }
            mock_client.get = AsyncMock(return_value=mock_history_resp)

            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_embedding.queue_embedding_generation = AsyncMock()

            result = await poll_huddle_transcripts(
                mock_session, UUID(TEST_WORKSPACE_ID)
            )

        assert result["ingested"] == 0
        assert result["skipped"] == 1
        mock_embedding.queue_embedding_generation.assert_not_called()

    @pytest.mark.asyncio
    async def test_huddle_without_canvas_creates_minimal_record(self) -> None:
        """Huddle without AI notes creates MeetingTranscript with placeholder text."""
        from src.services.slack_huddles import poll_huddle_transcripts

        mock_session = AsyncMock()
        added_objects = []
        mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_integration = MagicMock()
        mock_integration.config = {
            "selected_channels": ["C001"],
            "available_channels": [{"id": "C001", "name": "general"}],
        }
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_dedup_result = MagicMock()
        mock_dedup_result.scalar_one_or_none.return_value = None

        mock_int_result2 = MagicMock()
        mock_int_result2.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_int_result, mock_dedup_result, mock_int_result2]
        )

        # Huddle without canvas_thread_ts
        huddle_msg = _make_huddle_message(canvas_thread_ts=None)

        with (
            patch(
                "src.services.slack_huddles.get_bot_token",
                return_value="xoxb-test-token",
            ),
            patch("src.services.slack_huddles.httpx.AsyncClient") as mock_httpx,
            patch("src.services.slack_huddles.embedding") as mock_embedding,
        ):
            mock_client = AsyncMock()
            mock_history_resp = MagicMock()
            mock_history_resp.status_code = 200
            mock_history_resp.json.return_value = {
                "ok": True,
                "messages": [huddle_msg],
                "has_more": False,
            }

            # users.info
            mock_user_resp = MagicMock()
            mock_user_resp.status_code = 200
            mock_user_resp.json.return_value = {
                "ok": True,
                "user": {"real_name": "Alice Smith", "profile": {"display_name": ""}},
            }

            mock_client.get = AsyncMock(
                side_effect=[mock_history_resp, mock_user_resp, mock_user_resp]
            )

            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_embedding.queue_embedding_generation = AsyncMock()

            result = await poll_huddle_transcripts(
                mock_session, UUID(TEST_WORKSPACE_ID)
            )

        assert result["ingested"] == 1

        from src.models.meeting import MeetingTranscript

        transcripts = [
            obj for obj in added_objects if isinstance(obj, MeetingTranscript)
        ]
        assert len(transcripts) == 1
        assert transcripts[0].transcript == "No AI notes available for this huddle."
        assert transcripts[0].source == "slack_huddle"

        # Embedding NOT queued for no-content huddles
        mock_embedding.queue_embedding_generation.assert_not_called()
