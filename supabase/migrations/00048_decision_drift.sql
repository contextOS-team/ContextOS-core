-- Migration 00048: Decision Drift core
-- expected_consequences (impact inference output), artifact_observations
-- (checker results), drifts (verified inconsistencies, with the outcome
-- fields first-class per plan Amendment C: "action is value").
-- See docs/technical-plan-winter-2027.md Phase 2.

CREATE TABLE IF NOT EXISTS public.expected_consequences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  decision_id UUID NOT NULL REFERENCES public.decisions(id) ON DELETE CASCADE,
  target_type TEXT NOT NULL CHECK (target_type IN (
    'linear', 'jira', 'github', 'docs', 'release', 'other'
  )),
  target_query TEXT NOT NULL,
  expected_state TEXT NOT NULL,
  rationale TEXT,
  importance TEXT NOT NULL DEFAULT 'medium' CHECK (importance IN (
    'high', 'medium', 'low'
  )),
  confidence REAL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
    'pending', 'checked', 'invalidated'
  )),
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_expected_consequences_workspace_decision
  ON public.expected_consequences (workspace_id, decision_id)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_expected_consequences_pending
  ON public.expected_consequences (workspace_id, status, created_at)
  WHERE deleted_at IS NULL AND status = 'pending';

CREATE TABLE IF NOT EXISTS public.artifact_observations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  expected_consequence_id UUID NOT NULL
    REFERENCES public.expected_consequences(id) ON DELETE CASCADE,
  checker TEXT NOT NULL,
  observed_state TEXT NOT NULL,
  consistent BOOLEAN,
  evidence JSONB NOT NULL DEFAULT '[]',
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_artifact_observations_consequence
  ON public.artifact_observations (expected_consequence_id, checked_at DESC);

CREATE TABLE IF NOT EXISTS public.drifts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  decision_id UUID NOT NULL REFERENCES public.decisions(id) ON DELETE CASCADE,
  expected_consequence_id UUID
    REFERENCES public.expected_consequences(id) ON DELETE SET NULL,
  summary TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'medium' CHECK (severity IN (
    'high', 'medium', 'low'
  )),
  verifier_verdict JSONB NOT NULL DEFAULT '{}',
  -- lifecycle: detected -> confirmed -> owner_assigned -> resolved -> verified
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  confirmed_at TIMESTAMPTZ,
  owner_user_id UUID REFERENCES public.profiles(id),
  owner_assigned_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  verified_at TIMESTAMPTZ,
  resolution_type TEXT CHECK (resolution_type IN (
    'jira_updated', 'linear_updated', 'doc_updated', 'implementation_changed',
    'work_cancelled', 'timeline_changed', 'intentional_exception', 'other'
  )),
  feedback_verdict TEXT CHECK (feedback_verdict IN (
    'confirmed', 'false_positive', 'intentional_exception',
    'decision_superseded', 'wrong_artifact', 'not_important'
  )),
  suggestion_id UUID REFERENCES public.suggestions(id),
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_drifts_workspace_lifecycle
  ON public.drifts (workspace_id, detected_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_drifts_workspace_decision
  ON public.drifts (workspace_id, decision_id)
  WHERE deleted_at IS NULL;

-- Surface drifts through the suggestions inbox.
ALTER TABLE public.suggestions DROP CONSTRAINT IF EXISTS suggestions_type_check;
ALTER TABLE public.suggestions ADD CONSTRAINT suggestions_type_check CHECK (type IN (
  'missing_source_coverage',
  'missed_decision',
  'action_prompt',
  'decision_relation',
  'decision_drift'
));

-- RLS on all three tables (standard workspace_members policy).
ALTER TABLE public.expected_consequences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artifact_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.drifts ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
  t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'expected_consequences', 'artifact_observations', 'drifts'
  ] LOOP
    EXECUTE format('DROP POLICY IF EXISTS "%s_workspace_data" ON public.%I', t, t);
    EXECUTE format($POLICY$
      CREATE POLICY "%s_workspace_data" ON public.%I
        FOR ALL
        USING (
          workspace_id IN (
            SELECT workspace_id FROM public.workspace_members
            WHERE user_id = auth.uid() AND deleted_at IS NULL
          )
        )
        WITH CHECK (
          workspace_id IN (
            SELECT workspace_id FROM public.workspace_members
            WHERE user_id = auth.uid() AND deleted_at IS NULL
          )
        )
    $POLICY$, t, t);
  END LOOP;
END $$;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.expected_consequences
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);
CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.drifts
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

COMMENT ON TABLE public.expected_consequences IS
  'Impact inference: what should have changed because of a decision.';
COMMENT ON TABLE public.artifact_observations IS
  'Checker results: what the artifacts actually show, with evidence refs.';
COMMENT ON TABLE public.drifts IS
  'Verified decision/execution inconsistencies with full lifecycle + outcome fields; the investor metric is resolved/confirmed.';
