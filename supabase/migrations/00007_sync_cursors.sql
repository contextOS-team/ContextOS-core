-- Dedicated sync state tracking table
-- Replaces ad-hoc JSONB in workspace_integrations.config
CREATE TABLE IF NOT EXISTS public.sync_cursors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id),
    provider TEXT NOT NULL CHECK (provider IN ('linear', 'slack', 'github', 'notion', 'fathom')),
    resource_type TEXT NOT NULL DEFAULT 'default',
    cursor_type TEXT NOT NULL DEFAULT 'pagination',
    cursor_value TEXT,
    records_synced INTEGER NOT NULL DEFAULT 0,
    sync_status TEXT NOT NULL DEFAULT 'idle' CHECK (sync_status IN ('idle', 'syncing', 'complete', 'error')),
    last_sync_at TIMESTAMP WITHOUT TIME ZONE,
    error_message TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),

    UNIQUE (workspace_id, provider, resource_type)
);

-- Trigger for updated_at
CREATE TRIGGER sync_cursors_updated_at
    BEFORE UPDATE ON public.sync_cursors
    FOR EACH ROW
    EXECUTE FUNCTION moddatetime(updated_at);

-- RLS
ALTER TABLE public.sync_cursors ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage their workspace sync cursors"
    ON public.sync_cursors
    FOR ALL
    USING (workspace_id IN (SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid() AND deleted_at IS NULL));
