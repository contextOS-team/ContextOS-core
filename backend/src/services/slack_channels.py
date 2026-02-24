"""Slack channel listing and selection management.

Provides functions to:
- List available channels from Slack API (with cursor pagination)
- Cache channel lists in workspace_integrations.config JSONB
- Save/retrieve channel selections for message filtering
- Check if a specific channel is monitored

Uses the Slack Web API conversations.list endpoint with proper
rate limit handling (Retry-After on 429 responses).
"""

import asyncio
import logging
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.integration import WorkspaceIntegration
from src.services.slack_oauth import SlackOAuthError, get_bot_token

logger = logging.getLogger(__name__)

# Slack Web API base URL
SLACK_API_BASE = "https://slack.com/api"


async def list_channels(
    session: AsyncSession,
    workspace_id: UUID,
) -> list[dict]:
    """Fetch available channels from Slack API and cache in DB.

    Calls Slack conversations.list with cursor pagination to retrieve
    all public channels and private channels where the bot is invited.
    Caches the result in workspace_integrations.config JSONB under
    the key 'available_channels'.

    Args:
        session: Async database session.
        workspace_id: Workspace whose Slack integration to query.

    Returns:
        List of channel dicts with keys: id, name, is_private, num_members.

    Raises:
        SlackOAuthError: If no bot token is found or Slack API returns an error.
    """
    bot_token = await get_bot_token(session, workspace_id)

    all_channels: list[dict] = []
    cursor: str | None = None

    async with httpx.AsyncClient() as client:
        while True:
            params: dict = {
                "types": "public_channel,private_channel",
                "exclude_archived": "true",
                "limit": "1000",
            }
            if cursor:
                params["cursor"] = cursor

            response = await client.get(
                f"{SLACK_API_BASE}/conversations.list",
                params=params,
                headers={"Authorization": f"Bearer {bot_token}"},
            )

            # Handle rate limiting with Retry-After header
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "1"))
                logger.warning(
                    "Slack rate limited, retrying after %d seconds",
                    retry_after,
                )
                await asyncio.sleep(retry_after)
                continue

            if response.status_code != 200:
                raise SlackOAuthError(
                    f"Slack API HTTP error {response.status_code}: {response.text}"
                )

            data = response.json()

            if not data.get("ok"):
                error = data.get("error", "unknown_error")
                raise SlackOAuthError(f"Slack conversations.list failed: {error}")

            channels = data.get("channels", [])
            for ch in channels:
                all_channels.append({
                    "id": ch.get("id", ""),
                    "name": ch.get("name", ""),
                    "is_private": ch.get("is_private", False),
                    "num_members": ch.get("num_members", 0),
                })

            # Check for next page
            next_cursor = (
                data.get("response_metadata", {}).get("next_cursor", "")
            )
            if next_cursor:
                cursor = next_cursor
            else:
                break

    # Cache the channel list in workspace_integrations.config
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "slack",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if integration:
        config = dict(integration.config) if integration.config else {}
        config["available_channels"] = all_channels
        integration.config = config
        await session.commit()

    return all_channels


async def get_cached_channels(
    session: AsyncSession,
    workspace_id: UUID,
) -> list[dict]:
    """Read cached channel list from workspace_integrations.config.

    Returns the cached 'available_channels' list without hitting the
    Slack API. Returns empty list if no cache exists.

    Args:
        session: Async database session.
        workspace_id: Workspace to look up.

    Returns:
        List of cached channel dicts, or empty list if no cache.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "slack",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return []

    return integration.config.get("available_channels", [])


async def get_selected_channels(
    session: AsyncSession,
    workspace_id: UUID,
) -> list[str]:
    """Read selected channel IDs from workspace_integrations.config.

    Returns the list of channel IDs that the user has selected for
    monitoring. Returns empty list if none selected.

    Args:
        session: Async database session.
        workspace_id: Workspace to look up.

    Returns:
        List of selected Slack channel IDs.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "slack",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration or not integration.config:
        return []

    return integration.config.get("selected_channels", [])


async def save_channel_selection(
    session: AsyncSession,
    workspace_id: UUID,
    channel_ids: list[str],
) -> None:
    """Save the user's channel selection to workspace_integrations.config.

    Updates the 'selected_channels' key in the JSONB config column.
    Only messages from selected channels will be ingested by the
    event processor.

    Args:
        session: Async database session.
        workspace_id: Workspace to update.
        channel_ids: List of Slack channel IDs to monitor.
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "slack",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration:
        raise SlackOAuthError("No Slack integration found for this workspace")

    config = dict(integration.config) if integration.config else {}
    config["selected_channels"] = channel_ids
    integration.config = config
    await session.commit()


async def is_channel_monitored(
    session: AsyncSession,
    workspace_id: UUID,
    channel_id: str,
) -> bool:
    """Check if a channel is in the selected channels list.

    Used by the event processor to filter messages from unmonitored
    channels. If no selected_channels is configured, returns True
    (monitor all channels by default).

    Args:
        session: Async database session.
        workspace_id: Workspace to check.
        channel_id: Slack channel ID to check.

    Returns:
        True if the channel is monitored or no filter is configured.
    """
    selected = await get_selected_channels(session, workspace_id)

    if not selected:
        return True  # No filter means all channels monitored

    return channel_id in selected
