-- ============================================================
-- Fix: Add workspace_id to code_chunks dedup unique index
-- Prevents cross-workspace data bleed when two workspaces
-- monitor the same public repo.
-- ============================================================

-- Drop the old unique index (4-column, missing workspace_id)
drop index if exists idx_code_chunks_dedup;

-- Create the corrected unique index with workspace_id
create unique index idx_code_chunks_dedup
  on public.code_chunks (workspace_id, repo_full_name, file_path, symbol_name, symbol_type);
