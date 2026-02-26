"""Tests for Fathom API client, meeting models, and transcript ingestion.

Covers:
- connect_fathom validates API key via Fathom API call
- connect_fathom stores key in Vault
- connect endpoint requires auth
- disconnect removes Vault secret
- poll fetches transcripts from Fathom API
- poll skips already-ingested transcripts (dedup by fathom_id)
- poll skips processing transcripts (no content yet)
- poll creates MeetingSegment records for speaker turns
- status returns integration info
- poll queues embedding generation
"""

import time
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.config import Settings, get_settings
from tests.conftest import (
    TEST_EMAIL,
    TEST_JWT_SECRET,
    TEST_USER_ID,
    TEST_WORKSPACE_ID,
    _make_test_settings,
)


@pytest.fixture()
def fathom_settings() -> Settings:
    """Create test settings with Fathom config and patch everywhere."""
    settings = _make_test_settings(
        FATHOM_API_KEY="test-fathom-api-key",
        FATHOM_API_BASE_URL="https://api.fathom.video/v1",
    )
    get_settings.cache_clear()

    import src.auth
    import src.config

    old_config = src.config.get_settings
    old_auth = src.auth.get_settings

    _override = lambda: settings  # noqa: E731
    src.config.get_settings = _override  # type: ignore[assignment]
    src.auth.get_settings = _override  # type: ignore[assignment]

    yield settings

    src.config.get_settings = old_config  # type: ignore[assignment]
    src.auth.get_settings = old_auth  # type: ignore[assignment]
    get_settings.cache_clear()


@pytest.fixture()
def fathom_app(fathom_settings: Settings, mock_session: AsyncMock):
    """Create a FastAPI app with Fathom settings and mocked session."""
    from src.db import get_session as get_session_dep
    from src.main import app as fastapi_app

    async def _mock_get_session() -> AsyncGenerator[AsyncMock, None]:
        yield mock_session

    fastapi_app.dependency_overrides[get_session_dep] = _mock_get_session
    fastapi_app.dependency_overrides[get_settings] = lambda: fathom_settings

    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def fathom_client(fathom_app) -> Generator[TestClient, None, None]:
    """Provide a TestClient for the app with Fathom config."""
    with TestClient(fathom_app) as c:
        yield c


def _make_auth_header() -> dict[str, str]:
    """Create a valid auth header for tests."""
    import jwt as pyjwt

    payload = {
        "sub": TEST_USER_ID,
        "email": TEST_EMAIL,
        "role": "authenticated",
        "exp": int(time.time()) + 3600,
        "aud": "authenticated",
        "iss": "http://localhost:54321/auth/v1",
    }
    token = pyjwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _make_fathom_call(
    call_id: str = "call_001",
    title: str = "Sprint Planning",
    has_transcript: bool = True,
) -> dict:
    """Create a mock Fathom API call record."""
    call: dict = {
        "id": call_id,
        "title": title,
        "scheduled_start_time": "2026-02-24T10:00:00Z",
        "recording_start_time": "2026-02-24T10:02:00Z",
        "recording_end_time": "2026-02-24T10:47:00Z",
        "calendar_invitees": [
            {"name": "Alice Smith", "email": "alice@example.com"},
            {"name": "Bob Jones", "email": "bob@example.com"},
        ],
        "default_summary": "Discussed sprint goals and priorities.",
    }
    if has_transcript:
        call["transcript"] = [
            {
                "speaker": "Alice Smith",
                "text": "Let's review the sprint.",
                "start_time": 0,
                "end_time": 5,
            },
            {
                "speaker": "Bob Jones",
                "text": "Sounds good.",
                "start_time": 5,
                "end_time": 8,
            },
        ]
    else:
        call["transcript"] = None
    return call


# ===========================================================================
# Endpoint auth tests
# ===========================================================================


class TestFathomEndpointAuth:
    """Tests that Fathom endpoints require authentication."""

    def test_connect_requires_auth(self, fathom_client: TestClient) -> None:
        """POST /api/fathom/connect without token returns 401/403."""
        response = fathom_client.post(
            "/api/fathom/connect",
            json={"api_key": "test-key"},
        )
        assert response.status_code in (401, 403)

    def test_disconnect_requires_auth(self, fathom_client: TestClient) -> None:
        """POST /api/fathom/disconnect without token returns 401/403."""
        response = fathom_client.post("/api/fathom/disconnect")
        assert response.status_code in (401, 403)

    def test_status_requires_auth(self, fathom_client: TestClient) -> None:
        """GET /api/fathom/status without token returns 401/403."""
        response = fathom_client.get("/api/fathom/status")
        assert response.status_code in (401, 403)

    def test_poll_requires_auth(self, fathom_client: TestClient) -> None:
        """POST /api/fathom/poll without token returns 401/403."""
        response = fathom_client.post("/api/fathom/poll")
        assert response.status_code in (401, 403)


# ===========================================================================
# Service-level tests
# ===========================================================================


class TestConnectFathom:
    """Tests for fathom.connect_fathom service function."""

    @pytest.mark.asyncio
    async def test_connect_validates_api_key(
        self, fathom_settings: Settings
    ) -> None:
        """connect_fathom calls Fathom API to validate the key."""
        from src.services.fathom import connect_fathom

        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        # Mock Fathom API validation response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}

        # Mock DB query -- no existing integration
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        api_call_made = []

        async def mock_get(url, **kwargs):
            api_call_made.append(url)
            return mock_response

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=mock_get)

        with (
            patch("src.services.fathom.store_token", return_value="secret-uuid"),
            patch("src.services.fathom.httpx.AsyncClient") as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await connect_fathom(
                mock_session, UUID(TEST_WORKSPACE_ID), "test-api-key"
            )

        assert result["status"] == "connected"
        # Verify Fathom API was called for validation
        assert len(api_call_made) == 1
        assert "meetings" in api_call_made[0]

    @pytest.mark.asyncio
    async def test_connect_stores_key_in_vault(
        self, fathom_settings: Settings
    ) -> None:
        """connect_fathom stores the API key in Vault."""
        from src.services.fathom import connect_fathom

        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        vault_calls = []

        async def mock_store(session, name, value):
            vault_calls.append({"name": name, "value": value})
            return "secret-uuid"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch("src.services.fathom.store_token", side_effect=mock_store),
            patch("src.services.fathom.httpx.AsyncClient") as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            await connect_fathom(
                mock_session, UUID(TEST_WORKSPACE_ID), "fathom-secret-key"
            )

        # Verify key was stored in Vault
        assert len(vault_calls) == 1
        assert "fathom" in vault_calls[0]["name"]
        assert vault_calls[0]["value"] == "fathom-secret-key"

    @pytest.mark.asyncio
    async def test_connect_rejects_invalid_key(
        self, fathom_settings: Settings
    ) -> None:
        """connect_fathom raises FathomError for invalid API key."""
        from src.services.fathom import FathomError, connect_fathom

        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch("src.services.fathom.httpx.AsyncClient") as mock_httpx,
            pytest.raises(FathomError, match="Invalid Fathom API key"),
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            await connect_fathom(
                mock_session, UUID(TEST_WORKSPACE_ID), "bad-key"
            )


class TestDisconnectFathom:
    """Tests for fathom.disconnect_fathom service function."""

    @pytest.mark.asyncio
    async def test_disconnect_removes_vault_secret(
        self, fathom_settings: Settings
    ) -> None:
        """disconnect_fathom deletes the API key from Vault."""
        from src.services.fathom import disconnect_fathom

        mock_session = AsyncMock()
        mock_session.add = MagicMock()

        mock_integration = MagicMock()
        mock_integration.status = "connected"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        vault_deletes = []

        async def mock_delete(session, name):
            vault_deletes.append(name)

        with patch("src.services.fathom.delete_token", side_effect=mock_delete):
            await disconnect_fathom(mock_session, UUID(TEST_WORKSPACE_ID))

        # Verify Vault secret was deleted
        assert len(vault_deletes) == 1
        assert "fathom" in vault_deletes[0]

        # Verify integration marked as disconnected
        assert mock_integration.status == "disconnected"
        mock_session.commit.assert_called_once()


class TestPollTranscripts:
    """Tests for fathom.poll_transcripts service function."""

    @pytest.mark.asyncio
    async def test_poll_fetches_transcripts(
        self, fathom_settings: Settings
    ) -> None:
        """poll_transcripts fetches calls from Fathom API and stores them."""
        from src.services.fathom import poll_transcripts

        mock_session = AsyncMock()

        # Mock Fathom API response with one call
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "items": [_make_fathom_call()],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_api_response)

        # Track session.add calls
        added_objects = []
        original_add = mock_session.add

        def track_add(obj):
            added_objects.append(obj)

        mock_session.add = MagicMock(side_effect=track_add)
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        # Mock dedup check -- no existing transcript
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        # Mock integration for last_poll_at
        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_existing_result, mock_int_result]
        )

        with (
            patch(
                "src.services.fathom.get_fathom_api_key",
                return_value="test-api-key",
            ),
            patch("src.services.fathom.httpx.AsyncClient") as mock_httpx,
            patch("src.services.fathom.embedding") as mock_embedding,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_embedding.queue_embedding_generation = AsyncMock()

            result = await poll_transcripts(mock_session, UUID(TEST_WORKSPACE_ID))

        assert result["ingested"] == 1
        assert result["skipped"] == 0
        assert result["processing"] == 0

        # Verify MeetingTranscript was created
        from src.models.meeting import MeetingSegment, MeetingTranscript

        transcripts = [
            obj for obj in added_objects if isinstance(obj, MeetingTranscript)
        ]
        segments = [
            obj for obj in added_objects if isinstance(obj, MeetingSegment)
        ]

        assert len(transcripts) == 1
        assert transcripts[0].source == "fathom"
        assert transcripts[0].title == "Sprint Planning"
        assert transcripts[0].raw_data["fathom_id"] == "call_001"

        # Verify segments were created
        assert len(segments) == 2
        assert segments[0].speaker_name == "Alice Smith"
        assert segments[1].speaker_name == "Bob Jones"

    @pytest.mark.asyncio
    async def test_poll_skips_already_ingested(
        self, fathom_settings: Settings
    ) -> None:
        """poll_transcripts skips calls that have already been ingested."""
        from src.services.fathom import poll_transcripts

        mock_session = AsyncMock()

        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "items": [_make_fathom_call()],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_api_response)

        # Mock dedup check -- existing transcript found
        mock_existing = MagicMock()
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = mock_existing

        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_existing_result, mock_int_result]
        )
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        with (
            patch(
                "src.services.fathom.get_fathom_api_key",
                return_value="test-api-key",
            ),
            patch("src.services.fathom.httpx.AsyncClient") as mock_httpx,
            patch("src.services.fathom.embedding") as mock_embedding,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_embedding.queue_embedding_generation = AsyncMock()

            result = await poll_transcripts(mock_session, UUID(TEST_WORKSPACE_ID))

        assert result["ingested"] == 0
        assert result["skipped"] == 1

        # No new objects should have been added
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_skips_processing_transcript(
        self, fathom_settings: Settings
    ) -> None:
        """poll_transcripts skips calls where transcript is still processing."""
        from src.services.fathom import poll_transcripts

        mock_session = AsyncMock()

        # Call with no transcript content (still processing)
        processing_call = _make_fathom_call(has_transcript=False)

        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "items": [processing_call],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_api_response)

        # No existing record
        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_existing_result, mock_int_result]
        )
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        with (
            patch(
                "src.services.fathom.get_fathom_api_key",
                return_value="test-api-key",
            ),
            patch("src.services.fathom.httpx.AsyncClient") as mock_httpx,
            patch("src.services.fathom.embedding") as mock_embedding,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_embedding.queue_embedding_generation = AsyncMock()

            result = await poll_transcripts(mock_session, UUID(TEST_WORKSPACE_ID))

        assert result["ingested"] == 0
        assert result["processing"] == 1

        # No new objects should have been added
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_creates_segments(
        self, fathom_settings: Settings
    ) -> None:
        """poll_transcripts creates MeetingSegment records for speaker turns."""
        from src.services.fathom import poll_transcripts

        mock_session = AsyncMock()

        call = _make_fathom_call()
        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {"items": [call]}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_api_response)

        added_objects = []
        mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_existing_result, mock_int_result]
        )

        with (
            patch(
                "src.services.fathom.get_fathom_api_key",
                return_value="test-api-key",
            ),
            patch("src.services.fathom.httpx.AsyncClient") as mock_httpx,
            patch("src.services.fathom.embedding") as mock_embedding,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_embedding.queue_embedding_generation = AsyncMock()

            await poll_transcripts(mock_session, UUID(TEST_WORKSPACE_ID))

        from src.models.meeting import MeetingSegment

        segments = [
            obj for obj in added_objects if isinstance(obj, MeetingSegment)
        ]
        assert len(segments) == 2
        assert segments[0].speaker_name == "Alice Smith"
        assert segments[0].text == "Let's review the sprint."
        assert segments[0].start_time_seconds == 0
        assert segments[0].end_time_seconds == 5
        assert segments[1].speaker_name == "Bob Jones"
        assert segments[1].text == "Sounds good."
        assert segments[1].start_time_seconds == 5
        assert segments[1].end_time_seconds == 8

    @pytest.mark.asyncio
    async def test_poll_queues_embedding(
        self, fathom_settings: Settings
    ) -> None:
        """poll_transcripts queues embedding generation for ingested transcripts."""
        from src.services.fathom import poll_transcripts

        mock_session = AsyncMock()

        mock_api_response = MagicMock()
        mock_api_response.status_code = 200
        mock_api_response.json.return_value = {
            "items": [_make_fathom_call()],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_api_response)

        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        mock_existing_result = MagicMock()
        mock_existing_result.scalar_one_or_none.return_value = None

        mock_integration = MagicMock()
        mock_integration.config = {}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_existing_result, mock_int_result]
        )

        with (
            patch(
                "src.services.fathom.get_fathom_api_key",
                return_value="test-api-key",
            ),
            patch("src.services.fathom.httpx.AsyncClient") as mock_httpx,
            patch("src.services.fathom.embedding") as mock_embedding,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_embedding.queue_embedding_generation = AsyncMock()

            await poll_transcripts(mock_session, UUID(TEST_WORKSPACE_ID))

            # Verify embedding was queued
            mock_embedding.queue_embedding_generation.assert_called_once()
            call_args = mock_embedding.queue_embedding_generation.call_args
            assert call_args[0][2] == "meeting_transcript"  # source_type


class TestFathomStatus:
    """Tests for fathom.get_fathom_status service function."""

    @pytest.mark.asyncio
    async def test_status_returns_integration_info(
        self, fathom_settings: Settings
    ) -> None:
        """get_fathom_status returns status and last_poll_at."""
        from src.services.fathom import get_fathom_status

        mock_session = AsyncMock()

        mock_integration = MagicMock()
        mock_integration.status = "connected"
        mock_integration.config = {"last_poll_at": "2026-02-24T10:00:00+00:00"}
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_integration
        mock_session.execute = AsyncMock(return_value=mock_result)

        status = await get_fathom_status(mock_session, UUID(TEST_WORKSPACE_ID))

        assert status["connected"] is True
        assert status["status"] == "connected"
        assert status["last_poll_at"] == "2026-02-24T10:00:00+00:00"

    @pytest.mark.asyncio
    async def test_status_disconnected(
        self, fathom_settings: Settings
    ) -> None:
        """get_fathom_status returns disconnected when no integration."""
        from src.services.fathom import get_fathom_status

        mock_session = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        status = await get_fathom_status(mock_session, UUID(TEST_WORKSPACE_ID))

        assert status["connected"] is False
        assert status["status"] == "disconnected"
        assert status["last_poll_at"] is None


# ===========================================================================
# Endpoint integration tests
# ===========================================================================


class TestFathomConnectEndpoint:
    """Tests for POST /api/fathom/connect endpoint."""

    def test_connect_endpoint_validates_key(
        self, fathom_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """POST /api/fathom/connect calls Fathom API to validate key."""
        # Mock workspace membership lookup for auth
        mock_ws_result = MagicMock()
        mock_ws_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        # Mock integration check -- no existing
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = None

        mock_session.execute = AsyncMock(
            side_effect=[mock_ws_result, mock_int_result]
        )
        mock_session.commit = AsyncMock()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with (
            patch("src.services.fathom.store_token", return_value="secret-uuid"),
            patch("src.services.fathom.httpx.AsyncClient") as mock_httpx,
        ):
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock(return_value=None)

            response = fathom_client.post(
                "/api/fathom/connect",
                json={"api_key": "test-fathom-key"},
                headers=_make_auth_header(),
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"


class TestFathomStatusEndpoint:
    """Tests for GET /api/fathom/status endpoint."""

    def test_status_endpoint_returns_info(
        self, fathom_client: TestClient, mock_session: AsyncMock
    ) -> None:
        """GET /api/fathom/status returns integration status."""
        # Mock workspace membership lookup for auth
        mock_ws_result = MagicMock()
        mock_ws_result.scalar_one_or_none.return_value = UUID(TEST_WORKSPACE_ID)

        # Mock integration
        mock_integration = MagicMock()
        mock_integration.status = "connected"
        mock_integration.config = {"last_poll_at": "2026-02-24T10:00:00+00:00"}
        mock_int_result = MagicMock()
        mock_int_result.scalar_one_or_none.return_value = mock_integration

        mock_session.execute = AsyncMock(
            side_effect=[mock_ws_result, mock_int_result]
        )

        response = fathom_client.get(
            "/api/fathom/status",
            headers=_make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is True
        assert data["last_poll_at"] == "2026-02-24T10:00:00+00:00"


# ===========================================================================
# Model import tests
# ===========================================================================


class TestMeetingModels:
    """Tests that meeting models import correctly."""

    def test_meeting_models_import(self) -> None:
        """MeetingTranscript and MeetingSegment import from models."""
        from src.models.meeting import MeetingSegment, MeetingTranscript

        assert MeetingTranscript.__tablename__ == "meeting_transcripts"
        assert MeetingSegment.__tablename__ == "meeting_segments"

    def test_meeting_models_reexport(self) -> None:
        """MeetingTranscript and MeetingSegment are exported from models/__init__."""
        from src.models import MeetingSegment, MeetingTranscript

        assert MeetingTranscript is not None
        assert MeetingSegment is not None
