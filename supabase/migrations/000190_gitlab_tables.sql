-- ============================================================
-- GitLab Integration Tables
-- Phase 24: GitLab Integration (Plan 01)
-- ============================================================

-- ============================================================
-- ADD 'gitlab' TO PROVIDER CHECK CONSTRAINTS
-- ============================================================

-- oauth_tokens: add 'gitlab' to provider check
alter table public.oauth_tokens drop constraint if exists oauth_tokens_provider_check;
alter table public.oauth_tokens add constraint oauth_tokens_provider_check
  check (provider in ('linear', 'slack', 'notion', 'google', 'fathom', 'github', 'gitlab'));

-- workspace_integrations: add 'gitlab' to provider check
alter table public.workspace_integrations drop constraint if exists workspace_integrations_provider_check;
alter table public.workspace_integrations add constraint workspace_integrations_provider_check
  check (provider in ('linear', 'slack', 'fathom', 'notion', 'github', 'gitlab'));

-- ============================================================
-- GITLAB MERGE REQUESTS
-- ============================================================
create table public.gitlab_merge_requests (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  linear_ticket_id uuid references public.linear_tickets(id) on delete set null,
  gitlab_id bigint not null,
  project_id bigint not null,
  project_path text not null,
  iid integer not null,
  title text not null,
  description text,
  state text not null check (state in ('open', 'closed', 'merged')),
  author text not null,
  source_branch text not null,
  target_branch text not null,
  reviewers text[],
  is_draft boolean default false,
  gitlab_created_at timestamptz,
  gitlab_updated_at timestamptz,
  gitlab_merged_at timestamptz,
  raw_data jsonb not null default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, gitlab_id)
);

-- ============================================================
-- GITLAB REVIEWS
-- ============================================================
create table public.gitlab_reviews (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  merge_request_id uuid not null references public.gitlab_merge_requests(id) on delete cascade,
  gitlab_id bigint not null,
  author text not null,
  state text not null check (state in ('approved', 'commented', 'note')),
  body text,
  file_path text,
  line_range text,
  gitlab_submitted_at timestamptz,
  raw_data jsonb not null default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, gitlab_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

-- gitlab_merge_requests indexes
create index on public.gitlab_merge_requests (workspace_id);
create index on public.gitlab_merge_requests (workspace_id, project_path);
create index on public.gitlab_merge_requests (workspace_id, linear_ticket_id);

-- gitlab_reviews indexes
create index on public.gitlab_reviews (workspace_id);
create index on public.gitlab_reviews (merge_request_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table public.gitlab_merge_requests enable row level security;
alter table public.gitlab_reviews enable row level security;

create policy "workspace_data" on public.gitlab_merge_requests
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.gitlab_reviews
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

-- ============================================================
-- TRIGGERS (auto-update updated_at via moddatetime)
-- ============================================================

create trigger set_updated_at before update on public.gitlab_merge_requests
  for each row execute function moddatetime(updated_at);

create trigger set_updated_at before update on public.gitlab_reviews
  for each row execute function moddatetime(updated_at);
