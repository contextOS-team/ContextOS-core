"""Slack user-token polling service (DMs + group-DMs + channels).

Phase 39 originally scoped this to DM-only. Phase 39.1 expanded coverage
to channels (public + private) because bot /invite permissions were
blocked for rollout, and the user token can already read every channel
the installer is a member of -- no workspace admin required.

Duplicate ingestion vs. the bot Events API webhook path is safe: both
paths upsert on (workspace_id, channel_id, ts) with identical SET-clause
parity (see SLACK-USR-04 + Test K source-inspection guard).

User scopes required (see slack_oauth.SLACK_USER_SCOPES):
im:read, im:history, mpim:read, mpim:history,
channels:read, channels:history, groups:read, groups:history.

Mirrors slack_huddles polling conventions (429 handling, cursor
pagination, sequential conversation iteration).

Public entry point:
    poll_user_messages(session, workspace_id) -> dict

Return shape:
    {
        "ingested": int,   # newly upserted messages
        "skipped":  int,   # filtered or already-present (dedup updates)
        "reason":   str | None,  # "dms_disabled" | "needs_reauth" |
                                 # "not_connected" | None on success
    }

The `include_dms` config gate controls ALL user-token polling (DMs and
channels). The key name is retained for backwards compatibility; treat
it semantically as "poll everything via user token". A rename to
e.g. `include_user_token_polling` would require a data migration and
breaks roundtrip with Plan 39-01's config keys, so we keep the
historical name -- see Phase 39.1 gap-closure decision log.

The function never raises for expected states (disabled, missing token,
empty conversation list). Programmer errors and unexpected HTTP failures
still surface as exceptions.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.models.integration import Provider, WorkspaceIntegration
from src.models.slack import SlackMessage
from src.services import embedding
from src.services.graph_extractor import extract_and_populate_graph
from src.services.slack_events import _should_filter, _ts_to_datetime
from src.services.slack_oauth import SlackOAuthError, get_user_token

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"
BACKFILL_DAYS = 7
BACKFILL_MESSAGES_PER_CONVERSATION_CAP = 100
# Conservative page size: RESEARCH.md flags a 1-rpm cap with limit=15 for
# non-Marketplace apps. Start at 100 and let 429 handling absorb bursts.
DEFAULT_PAGE_SIZE = 100
# User-token polling covers every conversation kind the installer can read:
# DMs (im), group DMs (mpim), public channels, and private channels. This
# expanded from DM-only ("im,mpim") in Phase 39.1 -- see module docstring
# and SLACK_USER_SCOPES for the rationale (bot /invite permissions blocked).
USER_CONVERSATION_TYPES = "im,mpim,public_channel,private_channel"

# Slack error codes that indicate the user token is no longer valid --
# treat as needs_reauth and short-circuit the current poll cycle.
_REAUTH_ERRORS = frozenset({"invalid_auth", "token_revoked", "not_authed"})
# Slack error codes for a single conversation failure that should NOT abort
# the whole poll (the loop just skips the offending DM).
_SKIP_CONVERSATION_ERRORS = frozenset(
    {"not_in_channel", "channel_not_found", "missing_scope"}
)


class _NeedsReauth(Exception):
    """Internal sentinel raised when Slack reports an auth failure."""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def poll_user_messages(
    session: AsyncSession,
    workspace_id: UUID,
) -> dict[str, Any]:
    """Poll the user's Slack conversations (DMs, group-DMs, channels).

    Contract documented at module level. See 39-02-PLAN.md for the full
    behavioral spec (tests A-J); Phase 39.1 adds channel coverage + test K.
    """
    integration = await _get_integration(session, workspace_id)
    if integration is None or integration.status != "connected":
        return {"ingested": 0, "skipped": 0, "reason": "not_connected"}

    config = integration.config or {}

    if not config.get("include_dms"):
        return {"ingested": 0, "skipped": 0, "reason": "dms_disabled"}

    try:
        user_token = await get_user_token(session, workspace_id)
    except SlackOAuthError:
        logger.warning(
            "Slack user token missing for workspace %s -- needs_reauth",
            workspace_id,
        )
        return {"ingested": 0, "skipped": 0, "reason": "needs_reauth"}

    is_backfill = bool(config.get("dms_first_enabled_at")) and not config.get(
        "dms_backfill_done"
    )
    oldest = _compute_oldest(config, is_backfill)

    ingested = 0
    skipped = 0
    needs_reauth_hit = False

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            dm_ids = await _enumerate_dms(client, user_token)
        except _NeedsReauth:
            return {"ingested": 0, "skipped": 0, "reason": "needs_reauth"}

        for conv_id in dm_ids:
            try:
                messages = await _fetch_history(
                    client,
                    user_token,
                    conv_id,
                    oldest,
                    cap=(
                        BACKFILL_MESSAGES_PER_CONVERSATION_CAP
                        if is_backfill
                        else None
                    ),
                )
            except _NeedsReauth:
                logger.warning(
                    "Slack invalid_auth during conversations.history for ws %s"
                    " -- short-circuiting remaining conversations",
                    workspace_id,
                )
                needs_reauth_hit = True
                break

            ins, skp = await _upsert_messages(
                session, workspace_id, conv_id, messages
            )
            ingested += ins
            skipped += skp

    if needs_reauth_hit:
        return {
            "ingested": ingested,
            "skipped": skipped,
            "reason": "needs_reauth",
        }

    # Persist poll bookkeeping (preserve other keys).
    updated = dict(integration.config) if integration.config else {}
    updated["last_user_poll_at"] = (
        datetime.now(UTC).replace(tzinfo=None).isoformat()
    )
    if is_backfill:
        updated["dms_backfill_done"] = True
    integration.config = updated
    await session.commit()

    return {"ingested": ingested, "skipped": skipped, "reason": None}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_integration(
    session: AsyncSession,
    workspace_id: UUID,
) -> WorkspaceIntegration | None:
    """Load the Slack integration row for a workspace, or None."""
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == Provider.SLACK,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _compute_oldest(config: dict[str, Any], is_backfill: bool) -> str | None:
    """Compute the Slack ``oldest`` parameter (a Slack ts float-string).

    - Backfill path (first DM opt-in): ``now - BACKFILL_DAYS``.
    - Steady state: convert ``config.last_user_poll_at`` (ISO naive UTC) to a
      Slack ts float-string.
    - Neither set: return None so Slack uses its default window.
    """
    if is_backfill:
        epoch = (
            datetime.now(UTC) - timedelta(days=BACKFILL_DAYS)
        ).timestamp()
        return f"{epoch:.6f}"

    last_poll = config.get("last_user_poll_at")
    if not last_poll:
        return None

    try:
        # Values are stored as naive UTC ISO strings by this module; tolerate
        # tz-aware strings too via fromisoformat.
        dt = datetime.fromisoformat(last_poll)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return f"{dt.timestamp():.6f}"
    except (TypeError, ValueError):
        logger.warning(
            "Invalid last_user_poll_at value %r; falling back to no oldest",
            last_poll,
        )
        return None


async def _enumerate_dms(
    client: httpx.AsyncClient,
    user_token: str,
) -> list[str]:
    """Enumerate every conversation the user token can read.

    Calls ``users.conversations`` with
    ``types=im,mpim,public_channel,private_channel`` (Phase 39.1 gap closure:
    expanded from DM-only to cover channels the installer is a member of).
    Paginates via ``response_metadata.next_cursor``. 429 responses sleep for
    ``Retry-After`` seconds and retry once.

    Function name is retained for git-history continuity; semantically it now
    returns IDs for DMs, mpims, public channels, and private channels.
    """
    headers = {"Authorization": f"Bearer {user_token}"}
    ids: list[str] = []
    cursor: str | None = None

    while True:
        params: dict[str, str] = {
            "types": USER_CONVERSATION_TYPES,
            "exclude_archived": "true",
            "limit": "200",
        }
        if cursor:
            params["cursor"] = cursor

        data = await _slack_get(
            client,
            f"{SLACK_API_BASE}/users.conversations",
            params=params,
            headers=headers,
        )

        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            if error in _REAUTH_ERRORS:
                raise _NeedsReauth(error)
            logger.error("users.conversations failed: %s", error)
            break

        for ch in data.get("channels", []):
            cid = ch.get("id")
            if cid:
                ids.append(cid)

        next_cursor = (
            data.get("response_metadata", {}).get("next_cursor") or ""
        )
        if data.get("has_more") and next_cursor:
            cursor = next_cursor
            continue
        break

    return ids


async def _fetch_history(
    client: httpx.AsyncClient,
    user_token: str,
    conv_id: str,
    oldest: str | None,
    cap: int | None,
) -> list[dict[str, Any]]:
    """Fetch conversations.history for a conversation (DM, mpim, or channel).

    - Respects ``oldest`` for incremental polling.
    - Honors 429 Retry-After (single retry per page, handled in _slack_get).
    - If ``cap`` is set (backfill mode), truncates to ``cap`` and stops paging.
    - Per-conversation errors (missing_scope, not_in_channel, channel_not_found)
      are logged and return ``[]`` so one bad conversation does not abort the
      poll cycle.
    - 401/invalid_auth raises _NeedsReauth so the caller aborts the cycle.
    """
    headers = {"Authorization": f"Bearer {user_token}"}
    messages: list[dict[str, Any]] = []
    cursor: str | None = None

    while True:
        params: dict[str, str] = {
            "channel": conv_id,
            "limit": str(DEFAULT_PAGE_SIZE),
        }
        if oldest:
            params["oldest"] = oldest
        if cursor:
            params["cursor"] = cursor

        data = await _slack_get(
            client,
            f"{SLACK_API_BASE}/conversations.history",
            params=params,
            headers=headers,
        )

        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            if error in _REAUTH_ERRORS:
                raise _NeedsReauth(error)
            if error in _SKIP_CONVERSATION_ERRORS:
                logger.warning(
                    "Skipping conversation %s due to Slack error: %s",
                    conv_id,
                    error,
                )
                return []
            logger.error(
                "conversations.history failed for %s: %s", conv_id, error
            )
            return messages

        for msg in data.get("messages", []):
            messages.append(msg)
            if cap is not None and len(messages) >= cap:
                return messages[:cap]

        next_cursor = (
            data.get("response_metadata", {}).get("next_cursor") or ""
        )
        if data.get("has_more") and next_cursor:
            cursor = next_cursor
            continue
        break

    return messages


async def _slack_get(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str],
    headers: dict[str, str],
) -> dict[str, Any]:
    """GET a Slack endpoint with a single 429 retry honoring Retry-After."""
    for attempt in range(2):
        response = await client.get(url, params=params, headers=headers)

        if response.status_code == 429:
            retry_after = _parse_retry_after(response.headers)
            logger.warning(
                "Slack rate limit on %s, sleeping %ds (attempt %d)",
                url,
                retry_after,
                attempt + 1,
            )
            await asyncio.sleep(retry_after)
            continue

        if response.status_code != 200:
            logger.error(
                "Slack HTTP %d on %s: %s",
                response.status_code,
                url,
                response.text,
            )
            # Return an ok=false-style shape so callers can bail gracefully.
            return {"ok": False, "error": f"http_{response.status_code}"}

        data: dict[str, Any] = response.json()
        return data

    # Two 429s in a row -- give up for this call. Caller treats as empty.
    logger.error("Slack rate limit persisted after retry on %s", url)
    return {"ok": False, "error": "rate_limited"}


def _parse_retry_after(headers: Any) -> int:
    """Parse the Retry-After header as seconds, defaulting to 1."""
    try:
        return int(headers.get("Retry-After", "1"))
    except (TypeError, ValueError):
        return 1


async def _upsert_messages(
    session: AsyncSession,
    workspace_id: UUID,
    conv_id: str,
    messages: list[dict[str, Any]],
) -> tuple[int, int]:
    """Upsert polled messages into SlackMessage with webhook-path parity.

    Returns (ingested, skipped) where:
      - ingested = newly inserted rows (ts was NOT in the table before)
      - skipped  = filter-drops + dedup-updates (ts was already in the table,
                   so on_conflict_do_update updated the fields in place)

    SET clause parity: the ``on_conflict_do_update.set_`` dict MUST match
    ``slack_events._handle_message`` exactly. Fields: text, user_id,
    thread_ts, parent_ts, is_thread_reply, raw_data. Any mismatch causes
    silent data corruption under dual-path ingestion (webhook + poll).
    See SLACK-USR-04 and the Test F source-inspection guard.
    """
    if not messages:
        return (0, 0)

    # --- 1) Filter out bot/system messages first -----------------------------
    filtered: list[dict[str, Any]] = []
    skipped_filter = 0
    for msg in messages:
        if _should_filter(msg):
            skipped_filter += 1
            continue
        filtered.append(msg)

    if not filtered:
        return (0, skipped_filter)

    # --- 2) Pre-count existing rows for dedup bookkeeping (Test J) -----------
    ts_list = [m["ts"] for m in filtered]
    existing_stmt = select(SlackMessage.slack_ts).where(
        SlackMessage.workspace_id == workspace_id,
        SlackMessage.channel_id == conv_id,
        SlackMessage.slack_ts.in_(ts_list),  # type: ignore[attr-defined]
    )
    existing_rows = (await session.execute(existing_stmt)).all()
    existing_ts = {row[0] for row in existing_rows}

    # --- 3) Upsert each message via pg_insert on uq_slack_msg ----------------
    # Mirrors slack_events._handle_message: pg_insert + on_conflict_do_update,
    # commit, then fetch the id back by (workspace_id, channel_id, slack_ts).
    # SLACK-USR-04 parity: SET-clause fields MUST match slack_events exactly.
    inserted_ids: list[UUID] = []
    for msg in filtered:
        thread_ts = msg.get("thread_ts")
        is_thread_reply = bool(thread_ts and thread_ts != msg["ts"])
        parent_ts = thread_ts if is_thread_reply else None

        values = {
            "workspace_id": workspace_id,
            "slack_ts": msg["ts"],
            "channel_id": conv_id,
            "channel_name": None,
            "user_id": msg.get("user"),
            "user_name": None,
            "text": msg.get("text", ""),
            "thread_ts": thread_ts,
            "parent_ts": parent_ts,
            "is_thread_reply": is_thread_reply,
            "slack_created_at": _ts_to_datetime(msg["ts"]),
            "raw_data": msg,
        }

        stmt = pg_insert(SlackMessage).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["workspace_id", "channel_id", "slack_ts"],
            set_={
                "text": stmt.excluded.text,
                "user_id": stmt.excluded.user_id,
                "thread_ts": stmt.excluded.thread_ts,
                "parent_ts": stmt.excluded.parent_ts,
                "is_thread_reply": stmt.excluded.is_thread_reply,
                "raw_data": stmt.excluded.raw_data,
            },
        )
        await session.execute(stmt)

        # Fetch the row id back (same pattern as slack_events._handle_message).
        id_stmt = select(SlackMessage.id).where(
            SlackMessage.workspace_id == workspace_id,
            SlackMessage.channel_id == conv_id,
            SlackMessage.slack_ts == msg["ts"],
        )
        id_result = await session.execute(id_stmt)
        row_id = id_result.scalar_one()
        inserted_ids.append(row_id)

    await session.commit()

    # --- 4) Embedding + graph extraction parity with slack_events ------------
    # Parity with slack_events._handle_message: one queue_embedding_generation
    # call per message, followed by a (non-fatal) graph extraction call.
    for msg, row_id in zip(filtered, inserted_ids, strict=True):
        await embedding.queue_embedding_generation(
            session, workspace_id, "slack_message", [row_id]
        )
        try:
            await extract_and_populate_graph(
                session=session,
                workspace_id=workspace_id,
                content=msg.get("text", ""),
                source_type="slack_message",
                source_id=row_id,
                source_name=f"Slack message in {conv_id}",
                source_external_id=msg["ts"],
            )
        except Exception:  # noqa: BLE001 -- graph extraction is best-effort
            logger.warning(
                "graph extraction failed for slack_message %s (non-fatal)",
                row_id,
                exc_info=True,
            )

    ingested = sum(1 for m in filtered if m["ts"] not in existing_ts)
    skipped = skipped_filter + sum(1 for m in filtered if m["ts"] in existing_ts)
    return (ingested, skipped)
