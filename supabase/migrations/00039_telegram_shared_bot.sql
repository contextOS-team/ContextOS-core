-- ============================================================
-- Phase 40: Telegram Shared-Bot Migration (Plan 01)
-- chat→workspace mapping + pairing codes + Phase-26 cleanup
-- ============================================================
--
-- Replaces the per-workspace BotFather flow with a single shared
-- @ContextOSBot. Group/supergroup chats are bound to a workspace via a
-- single-use ~15-min TTL pairing code; the global webhook resolves
-- workspace_id from `chat_id` (no more URL path param).
--
-- chat_id is BIGINT (Pitfall 9: supergroup IDs overflow signed INT32).
-- chat_id is the PRIMARY KEY on telegram_chat_workspace -- enforces
-- "first claim wins" via INSERT ... ON CONFLICT (chat_id) DO NOTHING.
--
-- Both tables are workspace-scoped via RLS; only service_role writes
-- (mirrors the established workspace_member_select pattern from
-- 00030_telegram_messages.sql).
-- ============================================================

-- ============================================================
-- TELEGRAM CHAT → WORKSPACE MAPPING (sticky, PK chat_id)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.telegram_chat_workspace (
    chat_id      BIGINT PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    chat_title   TEXT,
    chat_type    TEXT,
    paired_by    UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    paired_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tg_cw_workspace
    ON public.telegram_chat_workspace(workspace_id);

-- ============================================================
-- TELEGRAM PAIRING CODES (single-use, ~15min TTL)
-- ============================================================
CREATE TABLE IF NOT EXISTS public.telegram_pairing_codes (
    code         TEXT PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    created_by   UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tg_pc_workspace
    ON public.telegram_pairing_codes(workspace_id);
CREATE INDEX IF NOT EXISTS idx_tg_pc_expires
    ON public.telegram_pairing_codes(expires_at);

-- ============================================================
-- ROW LEVEL SECURITY -- workspace-scoped reads, service-role writes
-- ============================================================
ALTER TABLE public.telegram_chat_workspace ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "workspace_member_select" ON public.telegram_chat_workspace;
CREATE POLICY "workspace_member_select" ON public.telegram_chat_workspace
    FOR SELECT USING (
        workspace_id IN (
            SELECT ws.id FROM public.workspaces ws
            JOIN public.workspace_members wm ON ws.id = wm.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );

ALTER TABLE public.telegram_pairing_codes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "workspace_member_select" ON public.telegram_pairing_codes;
CREATE POLICY "workspace_member_select" ON public.telegram_pairing_codes
    FOR SELECT USING (
        workspace_id IN (
            SELECT ws.id FROM public.workspaces ws
            JOIN public.workspace_members wm ON ws.id = wm.workspace_id
            WHERE wm.user_id = auth.uid()
        )
    );

-- ============================================================
-- Realtime publication -- frontend pairing UI subscribes to
-- INSERTs (fresh claim) and UPDATEs (re-pair after kick) on
-- telegram_chat_workspace to flip 'connected' state.
--
-- REPLICA IDENTITY FULL is required so the WAL records the full
-- row on UPDATE, otherwise Realtime can't apply the workspace_id
-- filter against UPDATE events and silently drops them.
-- ============================================================
ALTER TABLE public.telegram_chat_workspace REPLICA IDENTITY FULL;

DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE public.telegram_chat_workspace;
EXCEPTION
  WHEN duplicate_object THEN
    NULL;
END;
$$;

-- ============================================================
-- Phase-26 cleanup -- drop legacy per-workspace bot tokens.
-- Vault entries (`telegram_<workspace_id>_bot_token`) are purged via
-- a one-shot deploy script in Plan 03 (Vault is not a regular table).
-- ============================================================
DELETE FROM public.oauth_tokens WHERE provider = 'telegram';
DELETE FROM public.workspace_integrations WHERE provider = 'telegram';
