"""One-shot script to backfill NULL slack_messages.user_name values.

Slack messages ingested before the bot had the `users:read` scope (or
during a transient users.info failure / before a token was repaired) were
stored with `user_name = NULL`. linking.py renders these as
"Slack message by Unknown ...", and the NULL persists forever because
ingestion only touches a row once.

This script re-resolves the display name for every row that still has a
`user_id` but no `user_name`, reusing the same cached, fail-silent
`_resolve_user_name` resolver the live ingestion path uses (so it honours
the per-(workspace,user) cache and never raises).

Rows with no `user_id` cannot be resolved (Slack didn't tell us who the
author was) and are skipped — they will keep showing "Unknown".

Run AFTER confirming the Slack bot token carries `users:read`
(SLACK_BOT_SCOPES in src/services/slack_oauth.py). If the scope is still
missing, users.info returns ok:false and nothing is backfilled — check
logs for the "users.info failed" warning.

Usage:
    cd backend
    uv run python scripts/backfill_slack_user_names.py --dry-run   # inspect
    uv run python scripts/backfill_slack_user_names.py             # apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Allow `python scripts/backfill_slack_user_names.py` from the backend root
# without requiring `python -m`. Mirrors purge_legacy_telegram_vault.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import select  # noqa: E402

from src.db import async_session  # noqa: E402
from src.models.slack import SlackMessage  # noqa: E402
from src.services.slack_events import _resolve_user_name  # noqa: E402

logger = logging.getLogger("backfill_slack_user_names")


async def main(dry_run: bool) -> None:
    async with async_session() as session:
        # Only rows we can actually fix: missing display name but we still
        # know the Slack user ID. deleted_at filter keeps us off tombstones.
        stmt = select(SlackMessage).where(
            SlackMessage.user_name.is_(None),  # type: ignore[union-attr]
            SlackMessage.user_id.is_not(None),  # type: ignore[union-attr]
            SlackMessage.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        rows = (await session.execute(stmt)).scalars().all()
        logger.info(
            "Found %d Slack messages with NULL user_name and a user_id",
            len(rows),
        )

        resolved = 0
        unresolved = 0
        for msg in rows:
            # _resolve_user_name is cached per (workspace, user_id), so the
            # N-th message from the same author is a dict hit, not an API call.
            name = await _resolve_user_name(
                session, msg.workspace_id, msg.user_id  # type: ignore[arg-type]
            )
            if not name:
                unresolved += 1
                continue

            if dry_run:
                logger.info(
                    "[DRY-RUN] %s -> %r (user_id=%s, channel=%s)",
                    msg.id, name, msg.user_id, msg.channel_id,
                )
            else:
                msg.user_name = name
                session.add(msg)
            resolved += 1

        if dry_run:
            logger.info(
                "[DRY-RUN] would backfill %d rows; %d still unresolvable "
                "(users.info returned no name / failed)",
                resolved, unresolved,
            )
            return

        await session.commit()
        logger.info(
            "Backfill complete: %d/%d rows updated; %d unresolvable",
            resolved, len(rows), unresolved,
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Backfill NULL slack_messages.user_name via users.info."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
