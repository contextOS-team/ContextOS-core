-- Migration 00041: suggestions
-- Phase 44: reusable workspace-scoped suggestion contract and lifecycle state.

CREATE TABLE IF NOT EXISTS public.suggestions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN (
    'missing_source_coverage',
    'missed_decision',
    'action_prompt'
  )),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
    'open',
    'snoozed',
    'dismissed',
    'resolved'
  )),
  priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN (
    'high',
    'medium',
    'low'
  )),
  fingerprint TEXT NOT NULL,
  entity_type TEXT,
  entity_id UUID,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  primary_action TEXT,
  action_href TEXT,
  evidence JSONB NOT NULL DEFAULT '{}',
  details JSONB NOT NULL DEFAULT '{}',
  provenance JSONB NOT NULL DEFAULT '{}',
  snoozed_until TIMESTAMPTZ,
  dismissed_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  reopened_at TIMESTAMPTZ,
  last_seen_at TIMESTAMPTZ,
  created_by_user_id UUID REFERENCES public.profiles(id),
  updated_by_user_id UUID REFERENCES public.profiles(id),
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT suggestions_workspace_fingerprint_key UNIQUE (workspace_id, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_suggestions_workspace_status_priority
  ON public.suggestions (workspace_id, status, priority, created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_suggestions_workspace_type_status
  ON public.suggestions (workspace_id, type, status)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_suggestions_workspace_entity
  ON public.suggestions (workspace_id, entity_type, entity_id)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_suggestions_snoozed_until
  ON public.suggestions (workspace_id, snoozed_until)
  WHERE deleted_at IS NULL AND status = 'snoozed';

ALTER TABLE public.suggestions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "suggestions_workspace_data" ON public.suggestions;
CREATE POLICY "suggestions_workspace_data" ON public.suggestions
  FOR ALL
  USING (
    workspace_id IN (
      SELECT workspace_id
      FROM public.workspace_members
      WHERE user_id = auth.uid()
        AND deleted_at IS NULL
    )
  )
  WITH CHECK (
    workspace_id IN (
      SELECT workspace_id
      FROM public.workspace_members
      WHERE user_id = auth.uid()
        AND deleted_at IS NULL
    )
  );

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.suggestions
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

COMMENT ON TABLE public.suggestions IS
  'Phase 44: reusable workspace-scoped suggestion contract with dismiss/snooze/resolve/reopen lifecycle state.';
