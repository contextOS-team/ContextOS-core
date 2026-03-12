-- ============================================================
-- Graph Traversal Function: Recursive CTE with Cycle Detection
-- Phase 22: Graph Foundation + Rule-Based Extraction
-- ============================================================
-- SECURITY DEFINER function that validates workspace access once,
-- then performs recursive CTE traversal bypassing per-row RLS
-- overhead. Supports direction control, depth limiting, and
-- optional entity/relationship type filters.
-- ============================================================

CREATE OR REPLACE FUNCTION public.traverse_graph(
  start_node_id uuid,
  match_workspace_id uuid,
  max_depth int DEFAULT 2,
  direction text DEFAULT 'both',
  filter_entity_types text[] DEFAULT NULL,
  filter_relationship_types text[] DEFAULT NULL
)
RETURNS TABLE (
  node_id uuid,
  entity_type text,
  name text,
  properties jsonb,
  edge_relationship_type text,
  depth int,
  path uuid[]
) AS $$
BEGIN
  -- Validate workspace access: caller must be a member OR service role
  IF auth.uid() IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.workspace_members
    WHERE workspace_members.workspace_id = match_workspace_id
      AND workspace_members.user_id = auth.uid()
  ) THEN
    RETURN;  -- empty result if no access
  END IF;

  RETURN QUERY
  WITH RECURSIVE graph_walk AS (
    -- Anchor: start node at depth 0
    SELECT
      n.id AS node_id,
      n.entity_type,
      n.name,
      n.properties,
      NULL::text AS edge_relationship_type,
      0 AS depth,
      ARRAY[n.id] AS path,
      FALSE AS is_cycle
    FROM public.graph_nodes n
    WHERE n.id = start_node_id
      AND n.workspace_id = match_workspace_id
      AND n.deleted_at IS NULL

    UNION ALL

    -- Recursive step: follow edges respecting direction
    SELECT
      next_node.id AS node_id,
      next_node.entity_type,
      next_node.name,
      next_node.properties,
      e.relationship_type AS edge_relationship_type,
      gw.depth + 1 AS depth,
      gw.path || next_node.id AS path,
      next_node.id = ANY(gw.path) AS is_cycle
    FROM graph_walk gw
    JOIN public.graph_edges e ON (
      -- Outbound: current node is source
      (direction IN ('outbound', 'both') AND e.source_node_id = gw.node_id)
      OR
      -- Inbound: current node is target
      (direction IN ('inbound', 'both') AND e.target_node_id = gw.node_id)
    )
    JOIN public.graph_nodes next_node ON (
      next_node.id = CASE
        WHEN e.source_node_id = gw.node_id THEN e.target_node_id
        ELSE e.source_node_id
      END
    )
    WHERE gw.depth < max_depth
      AND NOT gw.is_cycle
      AND e.workspace_id = match_workspace_id
      AND e.deleted_at IS NULL
      AND next_node.workspace_id = match_workspace_id
      AND next_node.deleted_at IS NULL
      -- Optional entity type filter
      AND (filter_entity_types IS NULL OR next_node.entity_type = ANY(filter_entity_types))
      -- Optional relationship type filter
      AND (filter_relationship_types IS NULL OR e.relationship_type = ANY(filter_relationship_types))
  )
  SELECT
    gw.node_id,
    gw.entity_type,
    gw.name,
    gw.properties,
    gw.edge_relationship_type,
    gw.depth,
    gw.path
  FROM graph_walk gw
  WHERE NOT gw.is_cycle;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
