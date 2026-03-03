-- ============================================================
-- Code Chunks Table
-- Phase 12: Org-wide Code Intelligence (Plan 01)
-- ============================================================

-- Stores parsed code symbols (functions, classes, methods, types, etc.)
-- extracted by tree-sitter from repos selected for GitHub PR monitoring.
-- Content-hash deduplication prevents redundant storage on re-index.

create table public.code_chunks (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  repo_full_name text not null,
  file_path text not null,
  symbol_name text not null,
  symbol_type text not null check (symbol_type in ('function', 'class', 'method', 'type', 'interface', 'decorator', 'module')),
  language text not null,
  content text not null,
  content_hash text not null,
  start_line integer not null,
  end_line integer not null,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Deduplication: one symbol per (repo, file, name, type)
create unique index idx_code_chunks_dedup
  on public.code_chunks (repo_full_name, file_path, symbol_name, symbol_type);

-- Tenant queries
create index idx_code_chunks_workspace on public.code_chunks (workspace_id);

-- Per-repo queries filtered by language
create index idx_code_chunks_repo_lang on public.code_chunks (repo_full_name, language);

-- Soft-delete filtering
create index idx_code_chunks_deleted_at on public.code_chunks (deleted_at);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table public.code_chunks enable row level security;

create policy "workspace_data" on public.code_chunks
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

-- ============================================================
-- TRIGGERS (auto-update updated_at via moddatetime)
-- ============================================================

create trigger set_updated_at before update on public.code_chunks
  for each row execute function moddatetime(updated_at);
