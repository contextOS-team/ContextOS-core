-- ============================================================
-- Identity Mappings: Cross-Platform Person Unification
-- Phase 23: Identity Resolution
-- ============================================================
-- Maps platform-specific user identities to canonical Person
-- graph nodes. One row per (workspace, platform, platform_user_id).
-- Email-based deterministic matching groups rows to canonical nodes.
-- ============================================================

-- ============================================================
-- IDENTITY MAPPINGS TABLE
-- ============================================================
CREATE TABLE public.identity_mappings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  email text,  -- nullable: GitHub users may not have public email
  platform text NOT NULL CHECK (platform IN ('linear', 'slack', 'github', 'fathom')),
  platform_user_id text NOT NULL,
  display_name text,
  canonical_person_id uuid REFERENCES public.graph_nodes(id) ON DELETE SET NULL,
  deleted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT identity_mappings_workspace_platform_user_key
    UNIQUE (workspace_id, platform, platform_user_id)
);

-- ============================================================
-- INDEXES
-- ============================================================

-- Lookup by platform identity (used by lookup_mapping)
CREATE INDEX idx_identity_mappings_workspace_platform_user
  ON public.identity_mappings (workspace_id, platform, platform_user_id);

-- Cross-platform email matching (used by resolve_by_email)
CREATE INDEX idx_identity_mappings_workspace_email
  ON public.identity_mappings (workspace_id, email)
  WHERE email IS NOT NULL;

-- Reverse lookup: find all mappings for a canonical person
CREATE INDEX idx_identity_mappings_canonical_person
  ON public.identity_mappings (canonical_person_id)
  WHERE canonical_person_id IS NOT NULL;

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE public.identity_mappings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_data" ON public.identity_mappings
  FOR ALL USING (
    workspace_id IN (
      SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
    )
  );

-- ============================================================
-- TRIGGERS (auto-update updated_at via moddatetime)
-- ============================================================

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.identity_mappings
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);
