"""Repo clone and code index orchestration service.

Clones repos via GitHub App installation token, walks source files,
parses with tree-sitter, and upserts code chunks into the database
with content-hash deduplication. Handles ephemeral clone cleanup.
"""

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.code_chunk import CodeChunk
from src.models.integration import WorkspaceIntegration
from src.services.code_parser import CodeChunkData, detect_language, parse_file
from src.services.github_oauth import GitHubOAuthError, get_installation_token
from src.services.github_repos import get_cached_repos, is_repo_monitored
from src.services.gitlab_common import ensure_valid_token
from src.utils.hashing import compute_content_hash

logger = logging.getLogger(__name__)

# Directories to skip during file walking
SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".next", "dist", "build", ".tox", ".mypy_cache",
    ".pytest_cache", "vendor",
})

# Files to skip
SKIP_FILES = frozenset({
    "package-lock.json", "yarn.lock", "Pipfile.lock",
    "poetry.lock", "pnpm-lock.yaml",
})

# Max file size to parse (500KB)
MAX_FILE_SIZE = 500 * 1024


def _should_skip_path(path: str) -> bool:
    """Check if a file or directory should be skipped during indexing.

    Skips hidden dirs, build artifacts, lockfiles, generated files,
    and files exceeding MAX_FILE_SIZE.

    Args:
        path: Absolute or relative path to check.

    Returns:
        True if the path should be skipped.
    """
    p = Path(path)

    # Check directory components
    for part in p.parts:
        if part in SKIP_DIRS:
            return True

    # Check filename
    if p.name in SKIP_FILES:
        return True

    # Skip minified JS files
    if p.name.endswith(".min.js") or p.name.endswith(".map"):
        return True

    return False


def _is_binary_file(file_path: Path) -> bool:
    """Check if a file is binary by reading the first 512 bytes.

    Args:
        file_path: Path to the file.

    Returns:
        True if the file contains null bytes (likely binary).
    """
    try:
        with open(file_path, "rb") as f:
            chunk = f.read(512)
            return b"\x00" in chunk
    except (OSError, PermissionError):
        return True


CLONE_TIMEOUT_SECONDS = 300  # 5 minutes


async def _get_clone_credentials(
    provider: str,
    workspace_id: UUID,
    session: AsyncSession,
    settings: Settings,
) -> tuple[str, str] | None:
    """Get clone URL prefix and token for the given provider.

    Args:
        provider: "github" or "gitlab".
        workspace_id: Workspace that owns the repo.
        session: Async database session.
        settings: Application settings.

    Returns:
        Tuple of (clone_url_prefix, token) or None on auth failure.
    """
    if provider == "gitlab":
        try:
            token = await ensure_valid_token(session, workspace_id, settings)
        except Exception as exc:
            logger.warning(
                "GitLab token retrieval failed for workspace %s: %s",
                workspace_id, exc,
            )
            return None
        return (f"https://oauth2:{token}@gitlab.com/", token)
    else:
        try:
            token = await get_installation_token(workspace_id, session, settings)
        except GitHubOAuthError as exc:
            logger.warning(
                "GitHub token retrieval failed for workspace %s: %s",
                workspace_id, exc,
            )
            return None
        return (f"https://x-access-token:{token}@github.com/", token)


async def index_repo(
    workspace_id: UUID,
    repo_full_name: str,
    session: AsyncSession,
    settings: Settings,
    provider: str = "github",
) -> dict:
    """Clone a repo, parse all source files, and upsert code chunks.

    Main entry point for repo code indexing. Uses provider-aware
    authentication for cloning, tree-sitter for parsing,
    and content-hash deduplication for efficient re-indexing.

    Args:
        workspace_id: Workspace that owns the repo.
        repo_full_name: Full repo name (e.g., "org/repo").
        session: Async database session.
        settings: Application settings.
        provider: "github" or "gitlab" (default: "github").

    Returns:
        Summary dict with repo, files_scanned, chunks_created,
        chunks_updated, chunks_deleted counts, and changed_chunk_ids
        (list of UUIDs for created/updated chunks).
    """
    from datetime import datetime, timezone

    tmp_dir = tempfile.mkdtemp(prefix="contextos_clone_")
    _empty_result = {
        "repo": repo_full_name,
        "files_scanned": 0,
        "chunks_created": 0,
        "chunks_updated": 0,
        "chunks_deleted": 0,
        "changed_chunk_ids": [],
    }

    try:
        # Get clone credentials for the provider
        credentials = await _get_clone_credentials(provider, workspace_id, session, settings)
        if credentials is None:
            logger.warning(
                "Skipping repo %s for workspace %s: no valid credentials",
                repo_full_name, workspace_id,
            )
            return _empty_result

        clone_url_prefix, _token = credentials

        # Shallow clone the repo (with timeout)
        clone_url = f"{clone_url_prefix}{repo_full_name}.git"
        clone_dir = os.path.join(tmp_dir, repo_full_name.replace("/", "_"))

        logger.info("Cloning repo %s for workspace %s", repo_full_name, workspace_id)

        process = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", "--single-branch", clone_url, clone_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=CLONE_TIMEOUT_SECONDS
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            logger.error("Clone timed out after %ds for %s", CLONE_TIMEOUT_SECONDS, repo_full_name)
            return {**_empty_result, "error": f"Clone timed out after {CLONE_TIMEOUT_SECONDS}s"}

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            logger.warning("Failed to clone %s: %s", repo_full_name, error_msg)
            return {**_empty_result, "error": error_msg}

        logger.info("Cloned %s successfully", repo_full_name)

        # Walk the cloned directory and parse source files
        files_scanned = 0
        all_chunks: list[tuple[str, CodeChunkData]] = []

        clone_path = Path(clone_dir)
        for root_dir, dirs, files in os.walk(clone_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                abs_path = Path(root_dir) / filename
                rel_path = str(abs_path.relative_to(clone_path))

                if _should_skip_path(rel_path):
                    continue

                try:
                    if abs_path.stat().st_size > MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue

                language = detect_language(filename)
                if language is None:
                    continue

                if _is_binary_file(abs_path):
                    continue

                try:
                    content = abs_path.read_text(encoding="utf-8", errors="replace")
                except (OSError, PermissionError):
                    continue

                files_scanned += 1
                chunks = parse_file(rel_path, content, language)
                for chunk in chunks:
                    all_chunks.append((rel_path, chunk))

        logger.info(
            "Scanned %d files in %s, found %d chunks",
            files_scanned, repo_full_name, len(all_chunks),
        )

        # --- Bulk prefetch existing chunk hashes (1 query instead of N) ---
        existing_stmt = select(
            CodeChunk.id,
            CodeChunk.repo_full_name,
            CodeChunk.file_path,
            CodeChunk.symbol_name,
            CodeChunk.symbol_type,
            CodeChunk.content_hash,
        ).where(
            CodeChunk.workspace_id == workspace_id,
            CodeChunk.repo_full_name == repo_full_name,
            CodeChunk.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(existing_stmt)
        # Map (repo, file, name, type) -> (id, hash)
        existing_map: dict[tuple[str, str, str, str], tuple[UUID, str]] = {}
        for row in result.fetchall():
            key = (row[1], row[2], row[3], row[4])
            existing_map[key] = (row[0], row[5])

        # --- Diff and batch upsert ---
        chunks_created = 0
        chunks_updated = 0
        changed_chunk_ids: list[UUID] = []
        seen_keys: set[tuple[str, str, str, str]] = set()

        for file_path, chunk_data in all_chunks:
            content_hash = compute_content_hash(chunk_data.content)
            dedup_key = (repo_full_name, file_path, chunk_data.symbol_name, chunk_data.symbol_type)
            seen_keys.add(dedup_key)

            existing = existing_map.get(dedup_key)
            if existing and existing[1] == content_hash:
                continue  # Unchanged

            # Use table-level insert (not ORM insert) to avoid SQLAlchemy
            # confusing the "metadata" column name with table MetaData object.
            table = CodeChunk.__table__
            values = {
                "workspace_id": workspace_id,
                "repo_full_name": repo_full_name,
                "file_path": file_path,
                "symbol_name": chunk_data.symbol_name,
                "symbol_type": chunk_data.symbol_type,
                "language": chunk_data.language,
                "content": chunk_data.content,
                "content_hash": content_hash,
                "start_line": chunk_data.start_line,
                "end_line": chunk_data.end_line,
                "metadata": chunk_data.metadata,
                "deleted_at": None,
            }

            upsert_stmt = (
                insert(table)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[
                        "workspace_id", "repo_full_name", "file_path", "symbol_name", "symbol_type",
                    ],
                    set_={
                        "language": values["language"],
                        "content": values["content"],
                        "content_hash": values["content_hash"],
                        "start_line": values["start_line"],
                        "end_line": values["end_line"],
                        "metadata": values["metadata"],
                        "deleted_at": None,
                    },
                )
                .returning(table.c.id)
            )
            upsert_result = await session.execute(upsert_stmt)
            row = upsert_result.first()
            if row:
                changed_chunk_ids.append(row[0])

            if existing:
                chunks_updated += 1
            else:
                chunks_created += 1

        # Soft-delete chunks that no longer exist in the repo (bulk)
        stale_ids = [
            chunk_id
            for key, (chunk_id, _hash) in existing_map.items()
            if key not in seen_keys
        ]
        chunks_deleted = len(stale_ids)
        if stale_ids:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            # Chunk the IN clause to avoid oversized queries
            for i in range(0, len(stale_ids), 500):
                batch = stale_ids[i:i + 500]
                await session.execute(
                    update(CodeChunk)
                    .where(CodeChunk.id.in_(batch))  # type: ignore[union-attr]
                    .values(deleted_at=now)
                )

        await session.flush()

        summary = {
            "repo": repo_full_name,
            "files_scanned": files_scanned,
            "chunks_created": chunks_created,
            "chunks_updated": chunks_updated,
            "chunks_deleted": chunks_deleted,
            "changed_chunk_ids": changed_chunk_ids,
        }

        logger.info(
            "Indexed %s: %d files, %d created, %d updated, %d deleted",
            repo_full_name, files_scanned, chunks_created, chunks_updated, chunks_deleted,
        )

        return summary

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _update_index_status(
    workspace_id: UUID,
    index_status: str,
    last_at: str | None = None,
    provider: str = "github",
    progress: int | None = None,
    total: int | None = None,
    current_repo: str | None = None,
) -> None:
    """Write code indexing status to workspace_integrations.config JSONB.

    Uses its own database session to avoid committing (or being blocked by)
    uncommitted work on the caller's data session. This isolation ensures
    progress updates succeed even if the indexing session is in an error
    state, and prevents partial repo data from being committed as a
    side-effect of a progress update.

    Args:
        workspace_id: Workspace to update.
        index_status: Status string ("indexing" or "idle").
        last_at: ISO timestamp of last indexing completion (only set on idle).
        provider: Integration provider ("github" or "gitlab").
        progress: Number of repos indexed so far (only during indexing).
        total: Total number of repos to index (only during indexing).
        current_repo: Repo currently being indexed (only during indexing).
    """
    from src.db import async_session

    async with async_session() as status_session:
        stmt = select(WorkspaceIntegration).where(
            WorkspaceIntegration.workspace_id == workspace_id,
            WorkspaceIntegration.provider == provider,
        )
        result = await status_session.execute(stmt)
        integration = result.scalar_one_or_none()

        if not integration:
            return

        config = dict(integration.config) if integration.config else {}
        config["code_index_status"] = index_status
        if last_at is not None:
            config["code_index_last_at"] = last_at
        if index_status == "indexing":
            config["code_index_progress"] = progress
            config["code_index_total"] = total
            config["code_index_current_repo"] = current_repo
        else:
            # Clear progress fields when idle
            config.pop("code_index_progress", None)
            config.pop("code_index_total", None)
            config.pop("code_index_current_repo", None)
        integration.config = config
        await status_session.commit()


async def index_workspace_repos(
    workspace_id: UUID,
    session: AsyncSession,
    settings: Settings,
) -> list[dict]:
    """Index all selected/monitored repos for a workspace.

    Retrieves the cached repo list, filters to monitored repos,
    and indexes them sequentially to avoid rate limit exhaustion
    (per Phase 7 decision). Tracks indexing status in
    workspace_integrations.config JSONB.

    Args:
        workspace_id: Workspace to index repos for.
        session: Async database session.
        settings: Application settings.

    Returns:
        List of per-repo summary dicts.
    """
    from datetime import datetime, timezone

    # Build list of monitored repos first so we know the total
    repos = await get_cached_repos(workspace_id, session)
    monitored_repos: list[dict] = []
    for repo in repos:
        full_name = repo.get("full_name", "")
        if not full_name:
            continue
        monitored = await is_repo_monitored(workspace_id, full_name, session)
        if monitored:
            monitored_repos.append(repo)

    total = len(monitored_repos)

    # Set status to "indexing" at start with total count
    await _update_index_status(
        workspace_id, "indexing", provider="github",
        progress=0, total=total,
    )

    try:
        results: list[dict] = []

        for idx, repo in enumerate(monitored_repos):
            full_name = repo.get("full_name", "")

            # Update progress: idx = completed count, current_repo = about to start
            await _update_index_status(
                workspace_id, "indexing", provider="github",
                progress=idx, total=total, current_repo=full_name,
            )

            logger.info("Indexing repo %s for workspace %s (%d/%d)", full_name, workspace_id, idx + 1, total)
            try:
                summary = await index_repo(workspace_id, full_name, session, settings, provider="github")
                await session.commit()
                results.append(summary)
            except Exception:
                logger.exception("Failed to index repo %s", full_name)
                await session.rollback()
                results.append({
                    "repo": full_name,
                    "files_scanned": 0,
                    "chunks_created": 0,
                    "chunks_updated": 0,
                    "chunks_deleted": 0,
                    "changed_chunk_ids": [],
                    "error": "Indexing failed",
                })

        # Show completion before transitioning to idle
        if total > 0:
            await _update_index_status(
                workspace_id, "indexing", provider="github",
                progress=total, total=total, current_repo=None,
            )

        return results
    finally:
        # Set status to "idle" even if an exception occurs mid-indexing.
        # Wrap in try/except so a broken session doesn't mask the original error.
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            await _update_index_status(
                workspace_id, "idle", last_at=now.isoformat(), provider="github"
            )
        except Exception:
            logger.warning("Failed to reset index status to idle for github", exc_info=True)


async def index_gitlab_workspace_repos(
    workspace_id: UUID,
    session: AsyncSession,
    settings: Settings,
) -> list[dict]:
    """Index all selected/monitored GitLab projects for a workspace.

    Retrieves the cached project list, filters to monitored projects,
    and indexes them sequentially. Refreshes the OAuth token before each
    repo clone since GitLab tokens expire in 2 hours.

    Args:
        workspace_id: Workspace to index projects for.
        session: Async database session.
        settings: Application settings.

    Returns:
        List of per-repo summary dicts.
    """
    from datetime import datetime, timezone

    from src.services.gitlab_repos import (
        get_cached_repos as get_gitlab_cached_repos,
        is_project_monitored,
    )

    # Build list of monitored repos first so we know the total
    repos = await get_gitlab_cached_repos(workspace_id, session)
    monitored_repos: list[dict] = []
    for repo in repos:
        path_with_namespace = repo.get("path_with_namespace", "")
        project_id = repo.get("id")
        if not path_with_namespace or project_id is None:
            continue
        monitored = await is_project_monitored(workspace_id, project_id, session)
        if monitored:
            monitored_repos.append(repo)

    total = len(monitored_repos)

    # Set status to "indexing" at start with total count
    await _update_index_status(
        workspace_id, "indexing", provider="gitlab",
        progress=0, total=total,
    )

    try:
        results: list[dict] = []

        for idx, repo in enumerate(monitored_repos):
            path_with_namespace = repo.get("path_with_namespace", "")

            # Update progress: idx = completed count, current_repo = about to start
            await _update_index_status(
                workspace_id, "indexing", provider="gitlab",
                progress=idx, total=total, current_repo=path_with_namespace,
            )

            logger.info("Indexing GitLab project %s for workspace %s (%d/%d)", path_with_namespace, workspace_id, idx + 1, total)
            try:
                # Refresh token before each clone -- GitLab tokens expire in 2 hours
                await ensure_valid_token(session, workspace_id, settings)
                summary = await index_repo(
                    workspace_id, path_with_namespace, session, settings, provider="gitlab"
                )
                await session.commit()
                results.append(summary)
            except Exception:
                logger.exception("Failed to index GitLab project %s", path_with_namespace)
                await session.rollback()
                results.append({
                    "repo": path_with_namespace,
                    "files_scanned": 0,
                    "chunks_created": 0,
                    "chunks_updated": 0,
                    "chunks_deleted": 0,
                    "changed_chunk_ids": [],
                    "error": "Indexing failed",
                })

        # Show completion before transitioning to idle
        if total > 0:
            await _update_index_status(
                workspace_id, "indexing", provider="gitlab",
                progress=total, total=total, current_repo=None,
            )

        return results
    finally:
        # Set status to "idle" even if an exception occurs mid-indexing.
        # Wrap in try/except so a broken session doesn't mask the original error.
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            await _update_index_status(
                workspace_id, "idle", last_at=now.isoformat(), provider="gitlab"
            )
        except Exception:
            logger.warning("Failed to reset index status to idle for gitlab", exc_info=True)
