-- ============================================================
-- Telegram Messages Table
-- Phase 26: Telegram Chat Integration (Plan 01)
-- ============================================================

-- ============================================================
-- TELEGRAM MESSAGES
-- ============================================================
CREATE TABLE IF NOT EXISTS public.telegram_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    message_id BIGINT NOT NULL,
    chat_id BIGINT NOT NULL,
    chat_title TEXT,
    chat_type TEXT,
    from_user_id BIGINT,
    from_username TEXT,
    from_first_name TEXT,
    text TEXT NOT NULL,
    reply_to_message_id BIGINT,
    is_reply BOOLEAN DEFAULT false,
    telegram_date TIMESTAMPTZ,
    raw_data JSONB NOT NULL DEFAULT '{}',
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Unique constraint for upsert on conflict (edited messages)
ALTER TABLE public.telegram_messages
    DROP CONSTRAINT IF EXISTS uq_tg_msg;
ALTER TABLE public.telegram_messages
    ADD CONSTRAINT uq_tg_msg UNIQUE (workspace_id, chat_id, message_id);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_tg_msg_workspace_date
    ON public.telegram_messages(workspace_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tg_msg_workspace_chat
    ON public.telegram_messages(workspace_id, chat_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE public.telegram_messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_member_select" ON public.telegram_messages
    FOR SELECT USING (
        workspace_id IN (
            SELECT ws.id FROM public.workspaces ws
            JOIN public.workspace_members wm ON ws.id = wm.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );

CREATE POLICY "workspace_member_insert" ON public.telegram_messages
    FOR INSERT WITH CHECK (
        workspace_id IN (
            SELECT ws.id FROM public.workspaces ws
            JOIN public.workspace_members wm ON ws.id = wm.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );

-- ============================================================
-- ADD 'telegram' TO PROVIDER CHECK CONSTRAINTS
-- ============================================================

-- oauth_tokens: add 'telegram'
ALTER TABLE public.oauth_tokens DROP CONSTRAINT IF EXISTS oauth_tokens_provider_check;
ALTER TABLE public.oauth_tokens ADD CONSTRAINT oauth_tokens_provider_check
    CHECK (provider IN ('linear', 'slack', 'notion', 'google', 'fathom', 'github', 'gitlab', 'telegram'));

-- workspace_integrations: add 'telegram'
ALTER TABLE public.workspace_integrations DROP CONSTRAINT IF EXISTS workspace_integrations_provider_check;
ALTER TABLE public.workspace_integrations ADD CONSTRAINT workspace_integrations_provider_check
    CHECK (provider IN ('linear', 'slack', 'fathom', 'notion', 'github', 'gitlab', 'telegram'));

-- webhook_deliveries: add 'telegram'
ALTER TABLE public.webhook_deliveries DROP CONSTRAINT IF EXISTS webhook_deliveries_provider_check;
ALTER TABLE public.webhook_deliveries ADD CONSTRAINT webhook_deliveries_provider_check
    CHECK (provider IN ('linear', 'slack', 'github', 'gitlab', 'telegram'));

-- sync_cursors: add 'telegram'
ALTER TABLE public.sync_cursors DROP CONSTRAINT IF EXISTS sync_cursors_provider_check;
ALTER TABLE public.sync_cursors ADD CONSTRAINT sync_cursors_provider_check
    CHECK (provider IN ('linear', 'slack', 'github', 'notion', 'fathom', 'gitlab', 'telegram'));

-- Note: embeddings source_type CHECK was removed in 00017_embeddings_code_chunk_type.sql.
-- Valid source types are enforced by SOURCE_TYPE_MAP in embedding.py.
-- 'telegram_message' will be handled at the application layer.
