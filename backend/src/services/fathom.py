"""Fathom API client for meeting transcript ingestion.

Provides functions to:
- Connect/disconnect Fathom integration (API key in Vault)
- Poll for new meeting transcripts
- Parse speaker-segmented transcript turns
- Store MeetingTranscript and MeetingSegment records

Fathom authentication uses a user-provided API key (not OAuth).
The key is stored encrypted in Supabase Vault.

The Fathom API base URL defaults to https://api.fathom.ai/external/v1
but is configurable via FATHOM_API_BASE_URL setting.
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.integration import WorkspaceIntegration
from src.models.meeting import MeetingSegment, MeetingTranscript
from src.services import embedding
from src.services.vault import delete_token, read_token, store_token

logger = logging.getLogger(__name__)


class FathomError(Exception):
    """Raised when a Fathom API operation fails."""


def _vault_key(workspace_id: UUID) -> str:
    """Generate the Vault secret name for a Fathom API key.

    Format: fathom_{workspace_id}_api_key
    """
    return f"fathom_{workspace_id}_api_key"


async def connect_fathom(
    session: AsyncSession,
    workspace_id: UUID,
    api_key: str,
) -> dict:
    """Connect Fathom integration by validating and storing API key.

    Validates the API key by making a test call to the Fathom API
    (listing recent calls). If valid, stores the key in Vault and
    creates/updates the WorkspaceIntegration record.

    Args:
        session: Async database session.
        workspace_id: Workspace to connect.
        api_key: Fathom API key provided by the user.

    Returns:
        Dict with connection status info.

    Raises:
        FathomError: If the API key is invalid or API call fails.
    """
    import src.config as config_module

    settings = config_module.get_settings()
    base_url = settings.FATHOM_API_BASE_URL

    # Validate API key by making a test call
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{base_url}/meetings",
            headers={"X-Api-Key": api_key},
            params={"limit": "1"},
        )

    if response.status_code == 401:
        raise FathomError("Invalid Fathom API key")

    if response.status_code == 429:
        raise FathomError("Fathom API rate limited, try again later")

    if response.status_code not in (200, 201):
        raise FathomError(
            f"Fathom API error (HTTP {response.status_code}): {response.text}"
        )

    # Store API key in Vault (encrypted at rest)
    vault_key = _vault_key(workspace_id)
    await store_token(session, vault_key, api_key)

    # Upsert WorkspaceIntegration
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "fathom",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        integration.status = "connected"
        integration.connected_at = datetime.utcnow()
        integration.deleted_at = None
    else:
        integration = WorkspaceIntegration(
            workspace_id=workspace_id,
            provider="fathom",
            status="connected",
            connected_at=datetime.utcnow(),
        )
        session.add(integration)

    await session.commit()

    return {"status": "connected", "provider": "fathom"}


async def disconnect_fathom(
    session: AsyncSession,
    workspace_id: UUID,
) -> None:
    """Disconnect Fathom integration.

    Deletes the Vault secret and marks the WorkspaceIntegration
    as disconnected. Existing transcript data is preserved.

    Args:
        session: Async database session.
        workspace_id: Workspace to disconnect.
    """
    # Delete Vault secret
    vault_key = _vault_key(workspace_id)
    await delete_token(session, vault_key)

    # Mark integration as disconnected
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "fathom",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        integration.status = "disconnected"

    await session.commit()


async def get_fathom_api_key(
    session: AsyncSession,
    workspace_id: UUID,
) -> str:
    """Read the Fathom API key from Vault.

    Args:
        session: Async database session.
        workspace_id: Workspace to get the key for.

    Returns:
        The decrypted API key string.

    Raises:
        FathomError: If no API key is found in Vault.
    """
    vault_key = _vault_key(workspace_id)
    key = await read_token(session, vault_key)

    if not key:
        raise FathomError("No Fathom API key found for this workspace")

    return key


async def get_fathom_status(
    session: AsyncSession,
    workspace_id: UUID,
) -> dict:
    """Get the current Fathom integration status.

    Args:
        session: Async database session.
        workspace_id: Workspace to check.

    Returns:
        Dict with connection status and last poll info.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "fathom",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or integration.status == "disconnected":
        return {
            "connected": False,
            "status": "disconnected",
            "last_poll_at": None,
        }

    last_poll_at = None
    if integration.config:
        last_poll_at = integration.config.get("last_poll_at")

    return {
        "connected": integration.status == "connected",
        "status": integration.status,
        "last_poll_at": last_poll_at,
    }


async def poll_transcripts(
    session: AsyncSession,
    workspace_id: UUID,
) -> dict:
    """Poll Fathom API for new meeting transcripts.

    Fetches recent calls from the Fathom API, checks for already-ingested
    transcripts (via fathom_id in raw_data), and creates new
    MeetingTranscript + MeetingSegment records for new ones.

    Handles:
    - Deduplication via fathom_id stored in raw_data
    - Processing transcripts (no content yet) are skipped
    - Speaker-segmented turns stored as MeetingSegment records
    - Embedding generation queued for new transcripts
    - Rate limit handling via Retry-After header

    Args:
        session: Async database session.
        workspace_id: Workspace to poll for.

    Returns:
        Dict with poll results: ingested count, skipped count, etc.
    """
    import src.config as config_module

    settings = config_module.get_settings()
    base_url = settings.FATHOM_API_BASE_URL

    api_key = await get_fathom_api_key(session, workspace_id)

    ingested_count = 0
    skipped_count = 0
    processing_count = 0

    async with httpx.AsyncClient() as client:
        # Fetch recent calls from Fathom API
        cursor: str | None = None

        while True:
            params: dict = {"limit": "50"}
            if cursor:
                params["cursor"] = cursor

            response = await client.get(
                f"{base_url}/meetings",
                headers={"X-Api-Key": api_key},
                params=params,
            )

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "5"))
                logger.warning(
                    "Fathom rate limited, waiting %d seconds", retry_after
                )
                await asyncio.sleep(retry_after)
                continue

            if response.status_code != 200:
                logger.error(
                    "Fathom API error (HTTP %d): %s",
                    response.status_code,
                    response.text,
                )
                break

            data = response.json()
            calls = data.get("items", data.get("calls", []))

            if not calls:
                break

            for call in calls:
                fathom_id = call.get("id", "")

                if not fathom_id:
                    continue

                # Check if already ingested (dedup by fathom_id in raw_data)
                existing_stmt = select(MeetingTranscript).where(
                    MeetingTranscript.workspace_id == workspace_id,
                    MeetingTranscript.source == "fathom",
                    MeetingTranscript.raw_data["fathom_id"].as_string() == fathom_id,
                )
                existing_result = await session.execute(existing_stmt)
                existing = existing_result.scalar_one_or_none()

                if existing:
                    skipped_count += 1
                    continue

                # Check if transcript content is available
                transcript_content = call.get("transcript")
                if not transcript_content:
                    # Transcript still processing, skip for now
                    processing_count += 1
                    logger.info(
                        "Fathom call %s transcript still processing, skipping",
                        fathom_id,
                    )
                    continue

                # Extract metadata
                title = call.get("title", "Untitled Meeting")
                participants = call.get("participants", [])
                if isinstance(participants, list) and participants:
                    if isinstance(participants[0], dict):
                        participant_names = [
                            p.get("name", p.get("email", "Unknown"))
                            for p in participants
                        ]
                    else:
                        participant_names = participants
                else:
                    participant_names = []

                meeting_date = None
                date_str = call.get("created_at") or call.get("date")
                if date_str:
                    try:
                        meeting_date = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        pass

                duration = call.get("duration_minutes") or call.get("duration")
                duration_minutes = None
                if duration is not None:
                    try:
                        duration_minutes = int(duration)
                    except (ValueError, TypeError):
                        pass

                # Build full transcript text from segments if available
                segments = call.get("segments", [])
                if segments:
                    full_text = "\n".join(
                        f"{seg.get('speaker', 'Unknown')}: {seg.get('text', '')}"
                        for seg in segments
                    )
                elif isinstance(transcript_content, str):
                    full_text = transcript_content
                else:
                    full_text = str(transcript_content)

                summary = call.get("summary")

                # Create MeetingTranscript record
                meeting = MeetingTranscript(
                    workspace_id=workspace_id,
                    source="fathom",
                    title=title,
                    transcript=full_text,
                    summary=summary,
                    participants=participant_names if participant_names else None,
                    meeting_date=meeting_date,
                    duration_minutes=duration_minutes,
                    raw_data={"fathom_id": fathom_id, **call},
                )
                session.add(meeting)
                await session.flush()  # Get the generated ID

                # Create MeetingSegment records for speaker turns
                for seg in segments:
                    segment = MeetingSegment(
                        workspace_id=workspace_id,
                        transcript_id=meeting.id,
                        speaker_name=seg.get("speaker"),
                        text=seg.get("text", ""),
                        start_time_seconds=seg.get("start_time"),
                        end_time_seconds=seg.get("end_time"),
                    )
                    session.add(segment)

                await session.commit()

                # Queue embedding generation
                await embedding.queue_embedding_generation(
                    session, workspace_id, "meeting_transcript", [meeting.id]
                )

                ingested_count += 1
                logger.info(
                    "Ingested Fathom transcript: %s (%s)", fathom_id, title
                )

            # Check for next page
            next_cursor = data.get("next_cursor") or data.get(
                "pagination", {}
            ).get("next_cursor", "")
            if next_cursor:
                cursor = next_cursor
            else:
                break

    # Update last_poll_at in workspace_integrations.config
    int_stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "fathom",
    )
    int_result = await session.execute(int_stmt)
    integration = int_result.scalar_one_or_none()

    if integration:
        config = dict(integration.config) if integration.config else {}
        config["last_poll_at"] = datetime.utcnow().isoformat()
        integration.config = config
        await session.commit()

    return {
        "ingested": ingested_count,
        "skipped": skipped_count,
        "processing": processing_count,
    }
