-- Migration 00042: missed_decisions
-- Phase 45: post-sync missed-decision scan state, runs, and candidates.

CREATE TABLE IF NOT EXISTS public.missed_decision_scan_state (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  source_resource_id TEXT,
  last_missed_decision_scan_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.missed_decision_scan_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  source_resource_id TEXT,
  status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
  source_window_start TIMESTAMPTZ,
  source_window_end TIMESTAMPTZ,
  sources_scanned INTEGER NOT NULL DEFAULT 0,
  sources_total INTEGER,
  candidates_created INTEGER NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0,
  error_message TEXT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.missed_decision_candidates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  scan_run_id UUID REFERENCES public.missed_decision_scan_runs(id) ON DELETE SET NULL,
  suggestion_id UUID REFERENCES public.suggestions(id) ON DELETE SET NULL,
  source_type TEXT NOT NULL,
  source_id UUID NOT NULL,
  source_resource_id TEXT,
  source_quote TEXT NOT NULL,
  inferred_decision TEXT NOT NULL,
  inferred_rationale TEXT NOT NULL,
  source_link TEXT NOT NULL,
  confidence TEXT NOT NULL CHECK (confidence IN ('needs_review', 'high', 'very_high')),
  lifecycle_status TEXT NOT NULL DEFAULT 'detected' CHECK (lifecycle_status IN ('detected', 'surfaced', 'suppressed', 'linked', 'confirmed', 'rejected', 'deferred')),
  quote_fingerprint TEXT NOT NULL,
  decision_fingerprint TEXT NOT NULL,
  match_status TEXT,
  matched_entity_type TEXT,
  matched_entity_id UUID,
  suppression_reason TEXT,
  evidence JSONB NOT NULL DEFAULT '{}',
  people JSONB NOT NULL DEFAULT '[]',
  affected_systems JSONB NOT NULL DEFAULT '[]',
  action_hints JSONB NOT NULL DEFAULT '[]',
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  surfaced_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_missed_decision_scan_state_workspace_source
  ON public.missed_decision_scan_state (workspace_id, source_type, source_resource_id)
  WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_missed_decision_scan_state_workspace_source_global
  ON public.missed_decision_scan_state (workspace_id, source_type)
  WHERE source_resource_id IS NULL AND deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_missed_decision_scan_state_workspace_source_resource
  ON public.missed_decision_scan_state (workspace_id, source_type, source_resource_id)
  WHERE source_resource_id IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_missed_decision_scan_runs_workspace_status
  ON public.missed_decision_scan_runs (workspace_id, status, created_at)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_missed_decision_candidates_workspace_lifecycle
  ON public.missed_decision_candidates (workspace_id, lifecycle_status, confidence, created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_missed_decision_candidates_quote_fingerprint
  ON public.missed_decision_candidates (workspace_id, quote_fingerprint)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_missed_decision_candidates_decision_fingerprint
  ON public.missed_decision_candidates (workspace_id, decision_fingerprint)
  WHERE deleted_at IS NULL;

ALTER TABLE public.missed_decision_scan_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.missed_decision_scan_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.missed_decision_candidates ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "missed_decision_scan_state_workspace_data" ON public.missed_decision_scan_state;
CREATE POLICY "missed_decision_scan_state_workspace_data" ON public.missed_decision_scan_state
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

DROP POLICY IF EXISTS "missed_decision_scan_runs_workspace_data" ON public.missed_decision_scan_runs;
CREATE POLICY "missed_decision_scan_runs_workspace_data" ON public.missed_decision_scan_runs
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

DROP POLICY IF EXISTS "missed_decision_candidates_workspace_data" ON public.missed_decision_candidates;
CREATE POLICY "missed_decision_candidates_workspace_data" ON public.missed_decision_candidates
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

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.missed_decision_scan_state
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.missed_decision_scan_runs
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.missed_decision_candidates
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

COMMENT ON TABLE public.missed_decision_scan_state IS
  'Phase 45: per-workspace/source checkpoint for successful missed-decision scans.';

COMMENT ON TABLE public.missed_decision_scan_runs IS
  'Phase 45: queued/running/succeeded/failed missed-decision scan attempts.';

COMMENT ON TABLE public.missed_decision_candidates IS
  'Phase 45: source-backed missed-decision candidates before and after suggestion review.';
