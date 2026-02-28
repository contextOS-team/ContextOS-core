-- 00006: Notion pages schema additions
-- The notion_pages table already exists from 00001_initial_schema.sql.
-- This migration adds columns needed for the Notion integration sync.

-- No new columns needed -- the existing schema covers all requirements:
--   notion_id     -> unique Notion page ID
--   content       -> markdown content (renamed conceptually from text to markdown in app layer)
--   page_type     -> 'page', 'database_entry', 'wiki'
--   parent_id     -> parent page Notion ID
--   url           -> Notion page URL
--   last_edited_by -> last editor
--   notion_created_at, notion_updated_at -> Notion timestamps
--   raw_data      -> raw API response JSON

-- Ensure the provider check constraint on workspace_integrations includes all providers.
-- The original 00001 has: ('linear', 'slack', 'fathom', 'notion')
-- Phase 07 added github but may not have updated the constraint.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_name = 'workspace_integrations_provider_check'
    AND table_name = 'workspace_integrations'
  ) THEN
    ALTER TABLE public.workspace_integrations DROP CONSTRAINT workspace_integrations_provider_check;
    ALTER TABLE public.workspace_integrations ADD CONSTRAINT workspace_integrations_provider_check
      CHECK (provider IN ('linear', 'slack', 'fathom', 'notion', 'github'));
  END IF;
END $$;

-- Notion-specific index for lookup by notion_id (may already exist from 00001 gin index,
-- but add a btree index for exact-match upsert performance)
CREATE INDEX IF NOT EXISTS idx_notion_pages_notion_id ON public.notion_pages(notion_id);
