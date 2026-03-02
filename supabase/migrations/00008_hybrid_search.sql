-- ============================================================
-- Hybrid Search: Vector + Full-Text Search
-- ============================================================
-- Adds search_content column (raw text) and a generated tsvector
-- column to the embeddings table, plus a hybrid_search() function
-- that combines pgvector cosine similarity with PostgreSQL FTS.
-- ============================================================

-- 1. Add raw text column used for embedding generation
ALTER TABLE public.embeddings
  ADD COLUMN IF NOT EXISTS search_content text;

-- 2. Add generated tsvector column for full-text search
ALTER TABLE public.embeddings
  ADD COLUMN IF NOT EXISTS search_vector tsvector
  GENERATED ALWAYS AS (to_tsvector('english', COALESCE(search_content, ''))) STORED;

-- 3. GIN index for FTS on the generated column
CREATE INDEX IF NOT EXISTS idx_embeddings_search_vector
  ON public.embeddings USING gin (search_vector);

-- 4. Hybrid search function: vector similarity + full-text search
CREATE OR REPLACE FUNCTION public.hybrid_search(
  query_embedding vector(768),
  query_text text,
  match_workspace_id uuid,
  match_source_type text DEFAULT NULL,
  semantic_weight float DEFAULT 0.7,
  keyword_weight float DEFAULT 0.3,
  match_threshold float DEFAULT 0.5,
  match_count int DEFAULT 20
)
RETURNS TABLE (
  id uuid,
  source_type text,
  source_id uuid,
  similarity float,
  keyword_rank float,
  combined_score float,
  metadata jsonb
) AS $$
DECLARE
  query_tsquery tsquery := plainto_tsquery('english', query_text);
BEGIN
  RETURN QUERY
  SELECT
    e.id,
    e.source_type,
    e.source_id,
    (1 - (e.embedding <=> query_embedding))::float AS similarity,
    ts_rank_cd(e.search_vector, query_tsquery)::float AS keyword_rank,
    (
      semantic_weight * (1 - (e.embedding <=> query_embedding))
      + keyword_weight * ts_rank_cd(e.search_vector, query_tsquery)
    )::float AS combined_score,
    e.metadata
  FROM public.embeddings e
  WHERE e.workspace_id = match_workspace_id
    AND (match_source_type IS NULL OR e.source_type = match_source_type)
    AND e.deleted_at IS NULL
    AND (
      -- Include items found by EITHER signal
      (1 - (e.embedding <=> query_embedding)) > match_threshold
      OR e.search_vector @@ query_tsquery
    )
  ORDER BY combined_score DESC
  LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
