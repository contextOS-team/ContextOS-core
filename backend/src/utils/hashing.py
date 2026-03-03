"""Shared content hashing utilities.

Used by both the code indexer and embedding service for content-hash
deduplication. Keeping the algorithm in one place prevents drift.
"""

import hashlib
import re


def normalize_for_hash(text_content: str) -> str:
    """Normalize text for content hash comparison.

    Collapses all whitespace sequences (spaces, tabs, newlines) into
    single spaces and strips leading/trailing whitespace. This prevents
    trivial formatting changes from triggering re-embedding or re-indexing.
    """
    return re.sub(r'\s+', ' ', text_content).strip()


def compute_content_hash(text_content: str) -> str:
    """Compute SHA-256 hash of normalized content for change detection."""
    normalized = normalize_for_hash(text_content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
