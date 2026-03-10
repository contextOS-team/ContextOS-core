"""Unified integration status endpoint.

Provides a single endpoint to fetch the connection status of all
integration providers (Linear, Slack, Fathom) for the current workspace.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.db import get_session
from src.dependencies import UserContext, get_current_user
from src.models.integration import Provider, WorkspaceIntegration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

PROVIDERS = [Provider.LINEAR, Provider.SLACK, Provider.FATHOM, Provider.GITHUB, Provider.NOTION, Provider.TELEGRAM]


def _disconnected_status() -> dict:
    """Return the default disconnected status shape."""
    return {
        "status": "disconnected",
        "external_name": None,
        "connected_at": None,
    }


def _build_provider_status(integration: WorkspaceIntegration) -> dict:
    """Build the status dict for a single provider from its WorkspaceIntegration record."""
    config = integration.config or {}
    result: dict = {
        "status": integration.status,
        "external_name": config.get("external_name") or integration.external_id,
        "connected_at": integration.connected_at.isoformat() if integration.connected_at else None,
    }

    # For Slack, include selected_channels_count from config
    if integration.provider == Provider.SLACK:
        config = integration.config or {}
        selected = config.get("selected_channels", [])
        result["selected_channels_count"] = len(selected) if isinstance(selected, list) else 0

    # For GitHub, include selected_repos_count from config
    if integration.provider == Provider.GITHUB:
        config = integration.config or {}
        selected = config.get("selected_repos", [])
        result["selected_repos_count"] = len(selected) if isinstance(selected, list) else 0

    # For Notion, include pages_synced count and last_sync_at from config
    if integration.provider == Provider.NOTION:
        config = integration.config or {}
        result["pages_synced"] = config.get("pages_synced", 0)
        result["last_sync_at"] = config.get("last_sync_at")

    # For Telegram, include bot_username from config
    if integration.provider == Provider.TELEGRAM:
        result["bot_username"] = config.get("bot_username")

    return result


@router.get("/status")
async def get_integration_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the combined status of all integration providers.

    Returns a dict keyed by provider name with status info:
    {
        "linear": {"status": "connected", "external_name": "My Org", "connected_at": "..."},
        "slack": {"status": "disconnected", ...},
        "fathom": {"status": "disconnected", ...}
    }
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == user.workspace_id,
    )
    result = await session.execute(stmt)
    integrations = result.scalars().all()

    # Index by provider
    by_provider: dict[str, WorkspaceIntegration] = {}
    for integration in integrations:
        by_provider[integration.provider] = integration

    # Build response for all providers
    statuses: dict = {}
    for provider in PROVIDERS:
        if provider in by_provider:
            statuses[provider] = _build_provider_status(by_provider[provider])
        else:
            statuses[provider] = _disconnected_status()

    return statuses
