-- Migration 00050: Decision Guard (advisory)
-- decision_exceptions: sanctioned deviations so a legitimate exception stops
-- reading as a conflict/drift. guard_verdicts: every check_action result, which
-- is the Guard eval set accumulating for free. Advisory only — no enforcement.
-- See docs/technical-plan-winter-2027.md Phase 5.

CREATE TABLE IF NOT EXISTS public.decision_exceptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  decision_id UUID NOT NULL REFERENCES public.decisions(id) ON DELETE CASCADE,
  scope TEXT NOT NULL,
  reason TEXT,
  approved_by UUID REFERENCES public.profiles(id),
  valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ,
  evidence JSONB NOT NULL DEFAULT '{}',
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_decision_exceptions_workspace_decision
  ON public.decision_exceptions (workspace_id, decision_id)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_decision_exceptions_active
  ON public.decision_exceptions (workspace_id)
  WHERE deleted_at IS NULL AND (expires_at IS NULL OR expires_at > now());

-- Every advisory verdict, persisted as the offline eval set input.
CREATE TABLE IF NOT EXISTS public.guard_verdicts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  proposed_action TEXT NOT NULL,
  scope JSONB NOT NULL DEFAULT '{}',
  status TEXT NOT NULL CHECK (status IN (
    'no_known_conflict', 'potential_conflict', 'requires_review'
  )),
  rationale TEXT,
  confidence REAL,
  considered_decision_ids UUID[] NOT NULL DEFAULT ARRAY[]::UUID[],
  actor TEXT NOT NULL,
  latency_ms INTEGER,
  -- optional human label for the eval set (was the verdict right?)
  feedback_correct BOOLEAN,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_guard_verdicts_workspace
  ON public.guard_verdicts (workspace_id, created_at DESC);

ALTER TABLE public.decision_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.guard_verdicts ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
  t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['decision_exceptions', 'guard_verdicts'] LOOP
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

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.decision_exceptions
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

COMMENT ON TABLE public.decision_exceptions IS
  'Sanctioned deviations from a decision; consulted by Guard and drift so a legitimate exception is not flagged.';
COMMENT ON TABLE public.guard_verdicts IS
  'Every advisory check_action verdict — the Guard eval set accumulating from real usage.';
