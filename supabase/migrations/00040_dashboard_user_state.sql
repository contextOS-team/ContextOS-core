-- Migration 00040: dashboard_user_state
-- Per-user, per-workspace 'last visited at' timestamp for the pulse dashboard.
-- Used by the headline 'since last visit' delta + new-item markers.

CREATE TABLE IF NOT EXISTS public.dashboard_user_state (
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  last_visited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, workspace_id)
);

ALTER TABLE public.dashboard_user_state ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "own_dashboard_state" ON public.dashboard_user_state;
CREATE POLICY "own_dashboard_state" ON public.dashboard_user_state
  FOR ALL USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

COMMENT ON TABLE public.dashboard_user_state IS
  'Phase 41: per-(user, workspace) last_visited_at for the pulse dashboard headline + new-item markers. Composite PK; cascades on user/workspace delete.';
