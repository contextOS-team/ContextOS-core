"""One-shot script to purge legacy per-workspace Telegram bot tokens from Vault.

Phase 40 cutover: Phase-26 stored each workspace's bot token in Vault under
the key `oauth_telegram_<workspace_id>_bot_token` (via vault.token_name).
Migration 00039 deletes the corresponding `oauth_tokens` and
`workspace_integrations` rows, but Vault entries are not regular DB rows --
they live in `vault.secrets` and must be cleaned up explicitly.

Run AFTER deploying the Plan 01 migration (so the oauth_tokens rows are
already gone) and AFTER the new global webhook is registered (so no
Phase-26 connect attempts can fire).

Usage:
    cd backend
    uv run python scripts/purge_legacy_telegram_vault.py --dry-run   # inspect
    uv run python scripts/purge_legacy_telegram_vault.py             # apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
from pathlib import Path

# Allow `python scripts/purge_legacy_telegram_vault.py` from the backend root
# without requiring `python -m`. Mirrors the import style used by Alembic
# scripts in other backends in this repo.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text as sa_text  # noqa: E402

from src.db import async_session  # noqa: E402
from src.services.vault import delete_token  # noqa: E402

logger = logging.getLogger("purge_legacy_telegram_vault")

# Phase-26 Vault key shape -- vault.token_name(provider, workspace_id, kind)
# returns f"oauth_{provider}_{workspace_id}_{kind}". We only care about
# provider='telegram' and kind='bot_token' rows here.
NAME_PATTERN = re.compile(
    r"^oauth_telegram_"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"_bot_token$"
)


async def list_legacy_telegram_secrets(session) -> list[str]:
    """Return Vault secret names matching the Phase-26 telegram pattern.

    Filter SQL-side to keep the result set small even on workspaces with
    many secrets, then re-validate the name shape in Python so we never
    accidentally delete an unrelated secret that happens to start with
    `oauth_telegram_`.
    """
    result = await session.execute(
        sa_text(
            "SELECT name FROM vault.secrets "
            "WHERE name LIKE 'oauth_telegram_%_bot_token'"
        )
    )
    return [row[0] for row in result.all() if NAME_PATTERN.match(row[0])]


async def main(dry_run: bool) -> None:
    async with async_session() as session:
        names = await list_legacy_telegram_secrets(session)
        logger.info("Found %d legacy Telegram Vault entries", len(names))

        if dry_run:
            for name in names:
                logger.info("[DRY-RUN] would delete: %s", name)
            return

        deleted = 0
        for name in names:
            try:
                await delete_token(session, name)
                logger.info("deleted: %s", name)
                deleted += 1
            except Exception:
                logger.exception("failed to delete %s -- continuing", name)

        await session.commit()
        logger.info("Purge complete: %d/%d entries removed", deleted, len(names))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Purge Phase-26 per-workspace Telegram bot tokens from Vault."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List entries without deleting.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
