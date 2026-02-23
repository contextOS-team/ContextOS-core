"""Vector embedding storage and retrieval operations."""

from src.embeddings.store import embed_text, search_similar, upsert_embedding

__all__ = ["embed_text", "search_similar", "upsert_embedding"]
