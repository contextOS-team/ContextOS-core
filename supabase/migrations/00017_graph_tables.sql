-- ============================================================
-- Graph Tables: Knowledge Graph Foundation
-- Phase 22: Graph Foundation + Rule-Based Extraction
-- ============================================================
-- Creates graph_nodes and graph_edges tables with workspace-scoped
-- RLS, fingerprint-based deduplication, composite indexes, and
-- moddatetime triggers for the ContextOS knowledge graph.
-- ============================================================

-- ============================================================
-- GRAPH NODES (entities in the knowledge graph)
-- ============================================================
CREATE TABLE public.graph_nodes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  entity_type text NOT NULL CHECK (entity_type IN (
    'Person', 'Ticket', 'SlackThread', 'PR', 'CodeChunk',
    'NotionPage', 'Meeting', 'Decision', 'Blocker', 'Feature', 'Component'
  )),
  name text NOT NULL,
  fingerprint text NOT NULL,
  source_type text,
  source_id uuid,
  properties jsonb DEFAULT '{}',
  deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT graph_nodes_workspace_fingerprint_key UNIQUE (workspace_id, fingerprint)
);

-- ============================================================
-- GRAPH EDGES (relationships between nodes)
-- ============================================================
CREATE TABLE public.graph_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  source_node_id uuid NOT NULL REFERENCES public.graph_nodes(id) ON DELETE CASCADE,
  target_node_id uuid NOT NULL REFERENCES public.graph_nodes(id) ON DELETE CASCADE,
  relationship_type text NOT NULL CHECK (relationship_type IN (
    'mentions', 'references', 'authored_by', 'assigned_to', 'discussed_in',
    'implements', 'reviews', 'decided_in', 'blocks', 'same_as', 'parent_of'
  )),
  properties jsonb DEFAULT '{}',
  deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT graph_edges_workspace_source_target_type_key
    UNIQUE (workspace_id, source_node_id, target_node_id, relationship_type)
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Composite indexes for filtered queries
CREATE INDEX idx_graph_nodes_workspace_entity_type
  ON public.graph_nodes (workspace_id, entity_type);

CREATE INDEX idx_graph_edges_workspace_relationship_type
  ON public.graph_edges (workspace_id, relationship_type);

-- Traversal indexes for edge lookups
CREATE INDEX idx_graph_edges_source_node
  ON public.graph_edges (source_node_id);

CREATE INDEX idx_graph_edges_target_node
  ON public.graph_edges (target_node_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE public.graph_nodes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_data" ON public.graph_nodes
  FOR ALL USING (
    workspace_id IN (
      SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
    )
  );

ALTER TABLE public.graph_edges ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_data" ON public.graph_edges
  FOR ALL USING (
    workspace_id IN (
      SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
    )
  );

-- ============================================================
-- TRIGGERS (auto-update updated_at via moddatetime)
-- ============================================================

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.graph_nodes
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.graph_edges
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);
