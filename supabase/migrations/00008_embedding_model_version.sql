-- Add model version tracking to embeddings table
-- Enables selective re-embedding when switching models
ALTER TABLE public.embeddings
    ADD COLUMN IF NOT EXISTS model_name TEXT NOT NULL DEFAULT 'text-embedding-3-small',
    ADD COLUMN IF NOT EXISTS model_version TEXT NOT NULL DEFAULT 'v1';
