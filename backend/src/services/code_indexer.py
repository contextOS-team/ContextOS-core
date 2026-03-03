"""Repo clone and code index orchestration service.

Clones repos via GitHub App installation token, walks source files,
parses with tree-sitter, and upserts code chunks into the database
with content-hash deduplication. Handles ephemeral clone cleanup.
"""

import asyncio
import hashlib
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.config import Settings
from src.models.code_chunk import CodeChunk
from src.models.integration import WorkspaceIntegration
from src.services.code_parser import CodeChunkData, detect_language, parse_file
from src.services.github_oauth import get_installation_token
from src.services.github_repos import get_cached_repos, is_repo_monitored

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


def _normalize_for_hash(text_content: str) -> str:
    """Normalize text for content hash comparison.

    Collapses all whitespace into single spaces and strips.
    Same algorithm as embedding service for consistency.
    """
    return re.sub(r'\s+', ' ', text_content).strip()


def _compute_content_hash(text_content: str) -> str:
    """Compute SHA-256 hash of normalized content for change detection."""
    normalized = _normalize_for_hash(text_content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


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


async def index_repo(
    workspace_id: UUID,
    repo_full_name: str,
    session: AsyncSession,
    settings: Settings,
) -> dict:
    """Clone a repo, parse all source files, and upsert code chunks.

    Main entry point for repo code indexing. Uses the GitHub App
    installation token for authenticated clone, tree-sitter for parsing,
    and content-hash deduplication for efficient re-indexing.

    Args:
        workspace_id: Workspace that owns the repo.
        repo_full_name: Full repo name (e.g., "org/repo").
        session: Async database session.
        settings: Application settings.

    Returns:
        Summary dict with repo, files_scanned, chunks_created,
        chunks_updated, chunks_deleted counts.
    """
    tmp_dir = tempfile.mkdtemp(prefix="contextos_clone_")

    try:
        # Get installation token for authenticated clone
        token = await get_installation_token(workspace_id, session, settings)

        # Shallow clone the repo
        clone_url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
        clone_dir = os.path.join(tmp_dir, repo_full_name.replace("/", "_"))

        logger.info("Cloning repo %s for workspace %s", repo_full_name, workspace_id)

        process = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", "--single-branch", clone_url, clone_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.warning(
                "Failed to clone %s: %s",
                repo_full_name, stderr.decode("utf-8", errors="replace"),
            )
            return {
                "repo": repo_full_name,
                "files_scanned": 0,
                "chunks_created": 0,
                "chunks_updated": 0,
                "chunks_deleted": 0,
                "error": stderr.decode("utf-8", errors="replace"),
            }

        logger.info("Cloned %s successfully", repo_full_name)

        # Walk the cloned directory and parse source files
        files_scanned = 0
        all_chunks: list[tuple[str, CodeChunkData]] = []  # (file_path, chunk)

        clone_path = Path(clone_dir)
        for root_dir, dirs, files in os.walk(clone_path):
            # Filter out skipped directories in-place
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for filename in files:
                abs_path = Path(root_dir) / filename
                rel_path = str(abs_path.relative_to(clone_path))

                if _should_skip_path(rel_path):
                    continue

                # Check file size
                try:
                    if abs_path.stat().st_size > MAX_FILE_SIZE:
                        logger.debug("Skipping large file: %s (%d bytes)", rel_path, abs_path.stat().st_size)
                        continue
                except OSError:
                    continue

                # Detect language
                language = detect_language(filename)
                if language is None:
                    continue

                # Check if binary
                if _is_binary_file(abs_path):
                    continue

                # Read and parse file
                try:
                    content = abs_path.read_text(encoding="utf-8", errors="replace")
                except (OSError, PermissionError):
                    continue

                files_scanned += 1
                chunks = parse_file(rel_path, content, language)
                for chunk in chunks:
                    all_chunks.append((rel_path, chunk))

                logger.debug("Parsed %s: %d chunks", rel_path, len(chunks))

        logger.info(
            "Scanned %d files in %s, found %d chunks",
            files_scanned, repo_full_name, len(all_chunks),
        )

        # Upsert chunks with content-hash deduplication
        chunks_created = 0
        chunks_updated = 0
        seen_keys: set[tuple[str, str, str, str]] = set()

        for file_path, chunk_data in all_chunks:
            content_hash = _compute_content_hash(chunk_data.content)
            dedup_key = (repo_full_name, file_path, chunk_data.symbol_name, chunk_data.symbol_type)
            seen_keys.add(dedup_key)

            # Check if chunk already exists with same hash
            existing_stmt = select(CodeChunk.id, CodeChunk.content_hash).where(
                CodeChunk.repo_full_name == repo_full_name,
                CodeChunk.file_path == file_path,
                CodeChunk.symbol_name == chunk_data.symbol_name,
                CodeChunk.symbol_type == chunk_data.symbol_type,
            )
            result = await session.execute(existing_stmt)
            existing = result.first()

            if existing and existing.content_hash == content_hash:
                # Unchanged -- skip
                continue

            # Upsert
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
                insert(CodeChunk)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=[
                        "repo_full_name", "file_path", "symbol_name", "symbol_type",
                    ],
                    set_={
                        "workspace_id": values["workspace_id"],
                        "language": values["language"],
                        "content": values["content"],
                        "content_hash": values["content_hash"],
                        "start_line": values["start_line"],
                        "end_line": values["end_line"],
                        "metadata": values["metadata"],
                        "deleted_at": None,
                    },
                )
            )
            await session.execute(upsert_stmt)

            if existing:
                chunks_updated += 1
            else:
                chunks_created += 1

        # Soft-delete chunks that no longer exist in the repo
        chunks_deleted = 0
        all_existing_stmt = select(CodeChunk).where(
            CodeChunk.repo_full_name == repo_full_name,
            CodeChunk.workspace_id == workspace_id,
            CodeChunk.deleted_at.is_(None),  # type: ignore[union-attr]
        )
        result = await session.execute(all_existing_stmt)
        existing_chunks = result.scalars().all()

        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for existing_chunk in existing_chunks:
            key = (
                existing_chunk.repo_full_name,
                existing_chunk.file_path,
                existing_chunk.symbol_name,
                existing_chunk.symbol_type,
            )
            if key not in seen_keys:
                existing_chunk.deleted_at = now
                session.add(existing_chunk)
                chunks_deleted += 1

        await session.flush()

        summary = {
            "repo": repo_full_name,
            "files_scanned": files_scanned,
            "chunks_created": chunks_created,
            "chunks_updated": chunks_updated,
            "chunks_deleted": chunks_deleted,
        }

        logger.info(
            "Indexed %s: %d files, %d created, %d updated, %d deleted",
            repo_full_name, files_scanned, chunks_created, chunks_updated, chunks_deleted,
        )

        return summary

    finally:
        # Always clean up temp directory
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.debug("Cleaned up temp directory: %s", tmp_dir)


async def _update_index_status(
    workspace_id: UUID,
    session: AsyncSession,
    index_status: str,
    last_at: str | None = None,
) -> None:
    """Write code indexing status to workspace_integrations.config JSONB.

    Follows the same pattern used by sync_status in the sync pipeline.

    Args:
        workspace_id: Workspace to update.
        session: Async database session.
        index_status: Status string ("indexing" or "idle").
        last_at: ISO timestamp of last indexing completion (only set on idle).
    """
    stmt = select(WorkspaceIntegration).where(
        WorkspaceIntegration.workspace_id == workspace_id,
        WorkspaceIntegration.provider == "github",
    )
    result = await session.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration:
        return

    config = dict(integration.config) if integration.config else {}
    config["code_index_status"] = index_status
    if last_at is not None:
        config["code_index_last_at"] = last_at
    integration.config = config
    await session.flush()


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

    # Set status to "indexing" at start
    await _update_index_status(workspace_id, session, "indexing")

    repos = await get_cached_repos(workspace_id, session)
    results: list[dict] = []

    for repo in repos:
        full_name = repo.get("full_name", "")
        if not full_name:
            continue

        # Check if repo is monitored
        monitored = await is_repo_monitored(workspace_id, full_name, session)
        if not monitored:
            continue

        logger.info("Indexing repo %s for workspace %s", full_name, workspace_id)
        try:
            summary = await index_repo(workspace_id, full_name, session, settings)
            results.append(summary)
        except Exception:
            logger.exception("Failed to index repo %s", full_name)
            results.append({
                "repo": full_name,
                "files_scanned": 0,
                "chunks_created": 0,
                "chunks_updated": 0,
                "chunks_deleted": 0,
                "error": "Indexing failed",
            })

    # Set status to "idle" with last_at timestamp on completion
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await _update_index_status(
        workspace_id, session, "idle", last_at=now.isoformat()
    )

    return results
