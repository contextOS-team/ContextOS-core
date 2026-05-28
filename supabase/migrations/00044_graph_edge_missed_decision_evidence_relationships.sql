-- Allow missed-decision review actions to store source evidence edges.
ALTER TABLE public.graph_edges
  DROP CONSTRAINT IF EXISTS graph_edges_relationship_type_check;

ALTER TABLE public.graph_edges
  ADD CONSTRAINT graph_edges_relationship_type_check
  CHECK (relationship_type IN (
    'mentions', 'references', 'authored_by', 'assigned_to', 'discussed_in',
    'implements', 'reviews', 'decided_in', 'blocks', 'same_as', 'parent_of',
    'has_evidence', 'evidenced_by'
  ));
