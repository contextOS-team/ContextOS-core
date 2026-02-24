-- ============================================================
-- ContextOS Initial Schema
-- Phase 1: Foundation
-- ============================================================

-- Enable extensions
create extension if not exists vector with schema extensions;
create extension if not exists pg_trgm with schema extensions;
create extension if not exists moddatetime with schema extensions;

-- ============================================================
-- AUTO-UPDATE TIMESTAMP FUNCTION (fallback for moddatetime)
-- ============================================================
create or replace function public.handle_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- ============================================================
-- WORKSPACES (multi-tenant root)
-- ============================================================
create table public.workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text unique not null,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================================
-- USERS & WORKSPACE MEMBERSHIP
-- ============================================================
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text,
  avatar_url text,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.workspace_members (
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  role text not null default 'member' check (role in ('owner', 'admin', 'member')),
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  primary key (workspace_id, user_id)
);

-- ============================================================
-- OAUTH TOKENS (per-user integration tokens)
-- ============================================================
create table public.oauth_tokens (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  provider text not null check (provider in ('linear', 'slack', 'notion', 'google', 'fathom')),
  access_token text not null,
  refresh_token text,
  token_expires_at timestamptz,
  scopes text[],
  metadata jsonb default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, user_id, provider)
);

-- ============================================================
-- WORKSPACE INTEGRATIONS (scalable integration tracking)
-- ============================================================
create table public.workspace_integrations (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  provider text not null check (provider in ('linear', 'slack', 'fathom', 'notion')),
  external_id text,
  status text not null default 'disconnected' check (status in ('connected', 'disconnected', 'error')),
  config jsonb default '{}',
  connected_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, provider)
);

-- ============================================================
-- LINEAR TICKETS
-- ============================================================
create table public.linear_tickets (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  linear_id text not null,
  identifier text not null,  -- e.g. "ENG-123"
  title text not null,
  description text,
  status text,
  priority integer,
  assignee_name text,
  team_name text,
  project_name text,
  labels text[],
  linear_created_at timestamptz,
  linear_updated_at timestamptz,
  raw_data jsonb default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, linear_id)
);

-- ============================================================
-- LINEAR COMMENTS (normalized, FK to ticket)
-- ============================================================
create table public.linear_comments (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  ticket_id uuid not null references public.linear_tickets(id) on delete cascade,
  linear_id text not null,
  body text not null,
  author_name text,
  linear_created_at timestamptz,
  linear_updated_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, linear_id)
);

-- ============================================================
-- SLACK MESSAGES
-- ============================================================
create table public.slack_messages (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  slack_ts text not null,
  channel_id text not null,
  channel_name text,
  user_id text,
  user_name text,
  text text not null,
  thread_ts text,        -- self-referencing thread timestamp (Slack's data model)
  parent_ts text,        -- parent message timestamp for thread replies
  is_thread_reply boolean default false,
  reactions jsonb default '[]',
  slack_created_at timestamptz,
  raw_data jsonb default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  unique (workspace_id, channel_id, slack_ts)
);

-- ============================================================
-- NOTION PAGES
-- ============================================================
create table public.notion_pages (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  notion_id text not null,
  title text not null,
  content text,
  page_type text,  -- 'page', 'database_entry', 'wiki'
  parent_id text,
  url text,
  last_edited_by text,
  notion_created_at timestamptz,
  notion_updated_at timestamptz,
  raw_data jsonb default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, notion_id)
);

-- ============================================================
-- MEETING TRANSCRIPTS
-- ============================================================
create table public.meeting_transcripts (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  source text not null check (source in ('google_meet', 'zoom', 'teams', 'fathom', 'manual')),
  title text,
  transcript text not null,
  summary text,
  participants text[],
  meeting_date timestamptz,
  duration_minutes integer,
  raw_data jsonb default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now()
);

-- ============================================================
-- MEETING SEGMENTS (speaker turns, FK to meeting_transcripts)
-- ============================================================
create table public.meeting_segments (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  transcript_id uuid not null references public.meeting_transcripts(id) on delete cascade,
  speaker_name text,
  text text not null,
  start_time_seconds integer,
  end_time_seconds integer,
  deleted_at timestamptz,
  created_at timestamptz not null default now()
);

-- ============================================================
-- CONTEXT PAGES (the core output)
-- ============================================================
create table public.context_pages (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  ticket_id uuid references public.linear_tickets(id) on delete set null,
  ticket_identifier text,  -- denormalized "ENG-123"
  title text not null,
  content text not null,  -- markdown content
  summary text,
  status text not null default 'draft' check (status in ('draft', 'generating', 'ready', 'stale')),
  sources jsonb not null default '[]',  -- array of {type, id, title, relevance_score}
  generated_at timestamptz,
  generation_model text,
  generation_tokens_used integer,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ============================================================
-- EMBEDDINGS (for semantic search via pgvector)
-- ============================================================
create table public.embeddings (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  source_type text not null check (source_type in ('slack_message', 'linear_ticket', 'linear_comment', 'notion_page', 'meeting_transcript', 'meeting_segment', 'context_page')),
  source_id uuid not null,
  content_hash text not null,  -- to detect changes
  embedding vector(768) not null,
  metadata jsonb default '{}',
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  unique (source_type, source_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Vector similarity search (HNSW works on empty tables, unlike IVFFlat)
create index on public.embeddings using hnsw (embedding vector_cosine_ops);

-- Text search
create index on public.slack_messages using gin (text gin_trgm_ops);
create index on public.linear_tickets using gin (title gin_trgm_ops);
create index on public.notion_pages using gin (title gin_trgm_ops);

-- Foreign key lookups
create index on public.linear_tickets (workspace_id);
create index on public.linear_comments (workspace_id, ticket_id);
create index on public.slack_messages (workspace_id);
create index on public.notion_pages (workspace_id);
create index on public.meeting_transcripts (workspace_id);
create index on public.meeting_segments (workspace_id, transcript_id);
create index on public.context_pages (workspace_id);
create index on public.context_pages (ticket_id);
create index on public.embeddings (workspace_id, source_type);
create index on public.oauth_tokens (workspace_id, provider);
create index on public.workspace_integrations (workspace_id);

-- Slack thread grouping
create index on public.slack_messages (workspace_id, channel_id, thread_ts);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table public.workspaces enable row level security;
alter table public.profiles enable row level security;
alter table public.workspace_members enable row level security;
alter table public.oauth_tokens enable row level security;
alter table public.workspace_integrations enable row level security;
alter table public.linear_tickets enable row level security;
alter table public.linear_comments enable row level security;
alter table public.slack_messages enable row level security;
alter table public.notion_pages enable row level security;
alter table public.meeting_transcripts enable row level security;
alter table public.meeting_segments enable row level security;
alter table public.context_pages enable row level security;
alter table public.embeddings enable row level security;

-- Workspace members can access their workspace data
create policy "workspace_access" on public.workspaces
  for all using (
    id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

-- Users can see members of workspaces they belong to
create policy "members_select" on public.workspace_members
  for select using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

-- Users can only manage their own membership row
create policy "members_modify" on public.workspace_members
  for all using (user_id = auth.uid())
  with check (user_id = auth.uid());

create policy "own_profile" on public.profiles
  for all using (id = auth.uid());

-- Generic workspace-scoped policies
create policy "workspace_data" on public.oauth_tokens
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.workspace_integrations
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.linear_tickets
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.linear_comments
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.slack_messages
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.notion_pages
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.meeting_transcripts
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.meeting_segments
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.context_pages
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

create policy "workspace_data" on public.embeddings
  for all using (
    workspace_id in (select workspace_id from public.workspace_members where user_id = auth.uid())
  );

-- ============================================================
-- TRIGGERS (auto-update updated_at via moddatetime)
-- ============================================================

create trigger set_updated_at before update on public.workspaces
  for each row execute function moddatetime(updated_at);

create trigger set_updated_at before update on public.profiles
  for each row execute function moddatetime(updated_at);

create trigger set_updated_at before update on public.oauth_tokens
  for each row execute function moddatetime(updated_at);

create trigger set_updated_at before update on public.workspace_integrations
  for each row execute function moddatetime(updated_at);

create trigger set_updated_at before update on public.linear_tickets
  for each row execute function moddatetime(updated_at);

create trigger set_updated_at before update on public.linear_comments
  for each row execute function moddatetime(updated_at);

create trigger set_updated_at before update on public.notion_pages
  for each row execute function moddatetime(updated_at);

create trigger set_updated_at before update on public.context_pages
  for each row execute function moddatetime(updated_at);

-- ============================================================
-- FUNCTIONS
-- ============================================================

-- Similarity search function (768-dim embeddings)
create or replace function public.match_embeddings(
  query_embedding vector(768),
  match_workspace_id uuid,
  match_source_type text default null,
  match_threshold float default 0.7,
  match_count int default 10
)
returns table (
  id uuid,
  source_type text,
  source_id uuid,
  similarity float,
  metadata jsonb
) as $$
begin
  return query
  select
    e.id,
    e.source_type,
    e.source_id,
    1 - (e.embedding <=> query_embedding) as similarity,
    e.metadata
  from public.embeddings e
  where e.workspace_id = match_workspace_id
    and (match_source_type is null or e.source_type = match_source_type)
    and e.deleted_at is null
    and 1 - (e.embedding <=> query_embedding) > match_threshold
  order by e.embedding <=> query_embedding
  limit match_count;
end;
$$ language plpgsql;
