-- Migration 00046: decision state
-- Decision State v1: decisions become a first-class, temporal, versioned entity.
-- graph_nodes keeps a mirror node per decision as the linking layer; this table
-- is the source of truth. See docs/technical-plan-winter-2027.md Phase 1.

CREATE TABLE IF NOT EXISTS public.decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  statement TEXT NOT NULL,
  rationale TEXT,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN (
    'active',
    'superseded',
    'tentative',
    'reversed',
    'unknown'
  )),
  valid_from TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_until TIMESTAMPTZ,
  owner_node_id UUID REFERENCES public.graph_nodes(id),
  confidence REAL,
  consequentiality_score REAL,
  producer TEXT NOT NULL CHECK (producer IN (
    'missed_decision',
    'llm_extractor',
    'digest',
    'manual',
    'import'
  )),
  created_from_candidate_id UUID REFERENCES public.missed_decision_candidates(id),
  graph_node_id UUID REFERENCES public.graph_nodes(id),
  deleted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_decisions_workspace_status
  ON public.decisions (workspace_id, status, valid_from DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_decisions_workspace_candidate
  ON public.decisions (workspace_id, created_from_candidate_id)
  WHERE deleted_at IS NULL;

-- Trigram index backing write-time duplicate retrieval in decision_writer.
CREATE INDEX IF NOT EXISTS idx_decisions_statement_trgm
  ON public.decisions USING gin (statement gin_trgm_ops);

-- Append-only version history: one row per state change, snapshot BEFORE-write
-- semantics are enforced by the writer service (decision_writer.py), which is
-- the only code path allowed to touch these tables.
CREATE TABLE IF NOT EXISTS public.decision_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id UUID NOT NULL REFERENCES public.decisions(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,
  snapshot JSONB NOT NULL,
  change_type TEXT NOT NULL CHECK (change_type IN (
    'created',
    'status_changed',
    'evidence_added',
    'statement_edited',
    'superseded',
    'imported'
  )),
  change_reason TEXT,
  actor TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT decision_versions_decision_version_key UNIQUE (decision_id, version)
);

CREATE INDEX IF NOT EXISTS idx_decision_versions_decision
  ON public.decision_versions (decision_id, version DESC);

-- Evidence rows: quote is FROZEN at captured_at. Never re-read from the source
-- row (sources are mutably upserted; edits must not rewrite decision evidence).
CREATE TABLE IF NOT EXISTS public.decision_evidence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id UUID NOT NULL REFERENCES public.decisions(id) ON DELETE CASCADE,
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  source_id UUID NOT NULL,
  quote TEXT NOT NULL,
  source_link TEXT,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  added_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_decision_evidence_decision
  ON public.decision_evidence (decision_id);

CREATE INDEX IF NOT EXISTS idx_decision_evidence_workspace_source
  ON public.decision_evidence (workspace_id, source_type, source_id);

-- Decision-to-decision relationships (supersession chains, contradictions).
CREATE TABLE IF NOT EXISTS public.decision_edges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  from_decision UUID NOT NULL REFERENCES public.decisions(id) ON DELETE CASCADE,
  to_decision UUID NOT NULL REFERENCES public.decisions(id) ON DELETE CASCADE,
  edge_type TEXT NOT NULL CHECK (edge_type IN (
    'supersedes',
    'contradicts',
    'refines',
    'relates_to'
  )),
  rationale TEXT,
  actor TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT decision_edges_unique_key UNIQUE (workspace_id, from_decision, to_decision, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_decision_edges_from
  ON public.decision_edges (workspace_id, from_decision);

CREATE INDEX IF NOT EXISTS idx_decision_edges_to
  ON public.decision_edges (workspace_id, to_decision);

-- Append-only human feedback with enum reason codes: the learning-loop input.
CREATE TABLE IF NOT EXISTS public.decision_feedback (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  decision_id UUID NOT NULL REFERENCES public.decisions(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id),
  verdict TEXT NOT NULL CHECK (verdict IN (
    'correct',
    'wrong',
    'superseded',
    'minor',
    'missing_evidence',
    'duplicate',
    'not_important'
  )),
  note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_decision_feedback_workspace_decision
  ON public.decision_feedback (workspace_id, decision_id, created_at DESC);

-- RLS: standard workspace_members policy on all five tables.
ALTER TABLE public.decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.decision_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.decision_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.decision_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.decision_feedback ENABLE ROW LEVEL SECURITY;

DO $$
DECLARE
  t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'decisions', 'decision_versions', 'decision_evidence',
    'decision_edges', 'decision_feedback'
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

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.decisions
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

COMMENT ON TABLE public.decisions IS
  'Decision State v1: first-class temporal decisions. Source of truth; graph_nodes holds a mirror node for linking. Writes only via decision_writer service.';
COMMENT ON TABLE public.decision_versions IS
  'Append-only snapshots of decision rows, one per change. Never UPDATEd.';
COMMENT ON TABLE public.decision_evidence IS
  'Evidence links with quotes frozen at captured_at; source rows are mutable, these are not.';
COMMENT ON TABLE public.decision_feedback IS
  'Append-only human verdicts with enum reasons; harvested into eval gold sets.';
