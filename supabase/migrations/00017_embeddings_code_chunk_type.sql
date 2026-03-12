-- Remove embeddings.source_type CHECK constraint entirely.
-- Valid source types are enforced by SOURCE_TYPE_MAP in embedding.py.
-- The DB constraint created a maintenance burden where adding a new
-- source type required a migration, and forgetting it caused silent
-- worker crashes (code_chunk was missing, breaking all code embeddings).

ALTER TABLE public.embeddings
  DROP CONSTRAINT IF EXISTS embeddings_source_type_check;
