-- ============================================================
-- Graph Communities: Louvain partition snapshots + LLM summaries
-- Phase: GraphRAG communities v1
-- ============================================================
-- Adds community_id label to graph_nodes for fast membership lookup
-- and a graph_communities table holding per-workspace, per-snapshot
-- cluster metadata (label, summary, sizes, top members).
-- ============================================================

-- Add community_id label to graph_nodes.
-- Nullable: nodes outside Person/Ticket types or in workspaces never rebuilt are NULL.
ALTER TABLE public.graph_nodes
  ADD COLUMN community_id integer;

CREATE INDEX idx_graph_nodes_workspace_community
  ON public.graph_nodes (workspace_id, community_id)
  WHERE community_id IS NOT NULL;

-- One row per (workspace, community) per rebuild snapshot.
CREATE TABLE public.graph_communities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  community_id integer NOT NULL,
  label text,
  summary text,
  member_count integer NOT NULL,
  person_count integer NOT NULL,
  ticket_count integer NOT NULL,
  top_member_names text[],
  computed_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT graph_communities_workspace_id_key UNIQUE (workspace_id, community_id)
);

CREATE INDEX idx_graph_communities_workspace
  ON public.graph_communities (workspace_id);

ALTER TABLE public.graph_communities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_data" ON public.graph_communities
  FOR ALL USING (
    workspace_id IN (
      SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
    )
  );

-- ============================================================
-- TRIGGERS (auto-update updated_at via moddatetime)
-- ============================================================

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.graph_communities
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);
