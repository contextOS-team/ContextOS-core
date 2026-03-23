-- Audit log for tracking data access and privacy-sensitive operations.
-- Records who queried what, when, and from where.

CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES workspaces(id),
  user_id UUID REFERENCES auth.users(id),
  action TEXT NOT NULL,           -- 'context_generated', 'search_query', 'data_scrubbed', 'export'
  resource_type TEXT,             -- 'context_page', 'slack_message', etc.
  resource_id UUID,               -- ID of the resource accessed
  details JSONB DEFAULT '{}',     -- Additional context (query text, IP, etc.)
  ip_address INET,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for workspace-scoped queries (most common access pattern)
CREATE INDEX idx_audit_log_workspace ON audit_log(workspace_id, created_at DESC);

-- Index for user-scoped queries
CREATE INDEX idx_audit_log_user ON audit_log(user_id, created_at DESC);

-- RLS: workspace members can view their workspace's audit log
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_log_workspace_read ON audit_log
  FOR SELECT
  USING (
    workspace_id IN (
      SELECT workspace_id FROM workspace_members
      WHERE user_id = auth.uid()
    )
  );

-- Service role can insert (backend writes audit entries)
CREATE POLICY audit_log_service_insert ON audit_log
  FOR INSERT
  WITH CHECK (true);
