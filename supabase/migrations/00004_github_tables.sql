-- ============================================================
-- GitHub Integration Tables
-- Phase 7: GitHub Integration (Plan 01)
-- ============================================================

-- ============================================================
-- ADD 'github' TO PROVIDER CHECK CONSTRAINTS
-- ============================================================

-- oauth_tokens: add 'github' to provider check
alter table public.oauth_tokens drop constraint if exists oauth_tokens_provider_check;
alter table public.oauth_tokens add constraint oauth_tokens_provider_check
  check (provider in ('linear', 'slack', 'notion', 'google', 'fathom', 'github'));

-- workspace_integrations: add 'github' to provider check
alter table public.workspace_integrations drop constraint if exists workspace_integrations_provider_check;
alter table public.workspace_integrations add constraint workspace_integrations_provider_check
  check (provider in ('linear', 'slack', 'fathom', 'notion', 'github'));

-- ============================================================
-- GITHUB PULL REQUESTS
-- ============================================================
create table public.github_pull_requests (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  linear_ticket_id uuid references public.linear_tickets(id) on delete set null,
  github_id bigint not null,
  repo_full_name text not null,
  number integer not null,
  title text not null,
  description text,
  state text not null check (state in ('open', 'closed', 'merged')),
  author text not null,
  branch_name text not null,
  base_branch text not null,
  reviewers text[],
  is_draft boolean default false,
  github_created_at timestamptz,
  github_updated_at timestamptz,
  github_merged_at timestamptz,
  raw_data jsonb not null default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, github_id)
);

-- ============================================================
-- GITHUB REVIEWS
-- ============================================================
create table public.github_reviews (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  pull_request_id uuid not null references public.github_pull_requests(id) on delete cascade,
  github_id bigint not null,
  author text not null,
  state text not null check (state in ('approved', 'changes_requested', 'commented', 'dismissed')),
  body text,
  file_path text,
  line_range text,
  github_submitted_at timestamptz,
  raw_data jsonb not null default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, github_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

-- github_pull_requests indexes
create index on public.github_pull_requests (workspace_id);
create index on public.github_pull_requests (workspace_id, repo_full_name);
create index on public.github_pull_requests (workspace_id, linear_ticket_id);

-- github_reviews indexes
create index on public.github_reviews (workspace_id);
create index on public.github_reviews (pull_request_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table public.github_pull_requests enable row level security;
alter table public.github_reviews enable row level security;

create policy "workspace_data" on public.github_pull_requests
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.github_reviews
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

-- ============================================================
-- TRIGGERS (auto-update updated_at via moddatetime)
-- ============================================================

create trigger set_updated_at before update on public.github_pull_requests
  for each row execute function moddatetime(updated_at);

create trigger set_updated_at before update on public.github_reviews
  for each row execute function moddatetime(updated_at);
