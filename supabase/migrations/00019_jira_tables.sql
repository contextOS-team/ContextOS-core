-- ============================================================
-- Jira Integration Tables
-- Phase 25: Jira Integration (Plan 01)
-- ============================================================

-- ============================================================
-- ADD 'jira' TO PROVIDER CHECK CONSTRAINTS
-- ============================================================

-- oauth_tokens: add 'jira' to provider check
alter table public.oauth_tokens drop constraint if exists oauth_tokens_provider_check;
alter table public.oauth_tokens add constraint oauth_tokens_provider_check
  check (provider in ('linear', 'slack', 'notion', 'google', 'fathom', 'github', 'gitlab', 'telegram', 'jira'));

-- workspace_integrations: add 'jira' to provider check
alter table public.workspace_integrations drop constraint if exists workspace_integrations_provider_check;
alter table public.workspace_integrations add constraint workspace_integrations_provider_check
  check (provider in ('linear', 'slack', 'fathom', 'notion', 'github', 'gitlab', 'telegram', 'jira'));

-- sync_cursors: add 'jira' to provider check
alter table public.sync_cursors drop constraint if exists sync_cursors_provider_check;
alter table public.sync_cursors add constraint sync_cursors_provider_check
  check (provider in ('linear', 'slack', 'github', 'notion', 'fathom', 'gitlab', 'telegram', 'jira'));

-- webhook_deliveries: add 'jira' to provider check
alter table public.webhook_deliveries drop constraint if exists webhook_deliveries_provider_check;
alter table public.webhook_deliveries add constraint webhook_deliveries_provider_check
  check (provider in ('linear', 'slack', 'github', 'gitlab', 'telegram', 'jira'));

-- ============================================================
-- JIRA ISSUES
-- ============================================================
create table public.jira_issues (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  jira_id text not null,
  jira_key text not null,
  summary text not null,
  description text,
  status text,
  priority text,
  issue_type text,
  assignee_name text,
  reporter_name text,
  project_key text,
  project_name text,
  labels text[],
  jira_created_at timestamptz,
  jira_updated_at timestamptz,
  raw_data jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz,
  unique (workspace_id, jira_id)
);

-- ============================================================
-- JIRA COMMENTS
-- ============================================================
create table public.jira_comments (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  issue_id uuid not null references public.jira_issues(id) on delete cascade,
  jira_id text not null,
  author_name text,
  body text,
  jira_created_at timestamptz,
  jira_updated_at timestamptz,
  raw_data jsonb not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, jira_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

-- jira_issues indexes
create index on public.jira_issues (workspace_id);
create index on public.jira_issues using gin (summary extensions.gin_trgm_ops);
create index on public.jira_issues (workspace_id, jira_key);

-- jira_comments indexes
create index on public.jira_comments (workspace_id, issue_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table public.jira_issues enable row level security;
alter table public.jira_comments enable row level security;

create policy "workspace_data" on public.jira_issues
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.jira_comments
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

-- ============================================================
-- TRIGGERS (auto-update updated_at via moddatetime)
-- ============================================================

create trigger set_updated_at before update on public.jira_issues
  for each row execute function moddatetime(updated_at);

create trigger set_updated_at before update on public.jira_comments
  for each row execute function moddatetime(updated_at);

-- ============================================================
-- CONTEXT PAGES: Add jira_issue_id FK
-- ============================================================

alter table public.context_pages add column jira_issue_id uuid references public.jira_issues(id) on delete set null;
create index on public.context_pages (jira_issue_id);
