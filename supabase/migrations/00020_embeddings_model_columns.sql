-- Add model tracking columns to embeddings table
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS model_name text NOT NULL DEFAULT 'text-embedding-3-small';
ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS model_version text NOT NULL DEFAULT 'v1';
