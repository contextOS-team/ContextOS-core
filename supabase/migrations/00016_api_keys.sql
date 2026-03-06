-- API keys table for workspace-scoped key management.
-- Keys are stored as SHA-256 hashes; the full key is only shown at creation time.

CREATE TABLE public.api_keys (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid        NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  created_by   uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name         text        NOT NULL,
  key_prefix   text        NOT NULL,
  key_hash     text        NOT NULL,
  revoked_at   timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- Index for listing active keys per workspace
CREATE INDEX idx_api_keys_workspace ON public.api_keys (workspace_id, revoked_at);

-- Partial index for key validation lookups (only active keys)
CREATE INDEX idx_api_keys_hash ON public.api_keys (key_hash) WHERE revoked_at IS NULL;

-- Enable RLS
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

-- Policy: workspace members can manage their workspace's API keys
CREATE POLICY "api_keys_select" ON public.api_keys
  FOR SELECT USING (
    workspace_id IN (SELECT public.get_user_workspace_ids(auth.uid()))
  );

CREATE POLICY "api_keys_insert" ON public.api_keys
  FOR INSERT WITH CHECK (
    workspace_id IN (SELECT public.get_user_workspace_ids(auth.uid()))
  );

CREATE POLICY "api_keys_update" ON public.api_keys
  FOR UPDATE USING (
    workspace_id IN (SELECT public.get_user_workspace_ids(auth.uid()))
  );
