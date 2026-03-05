-- ============================================================
-- Add 'error' Status to Context Pages & Enable Realtime
-- Phase 19: Context Feed + Dashboard Home
-- ============================================================
-- 1. Adds 'error' to the context_pages.status CHECK constraint
--    so failed generations can be tracked and surfaced in the feed.
-- 2. Adds context_pages to the supabase_realtime publication so
--    postgres_changes subscriptions receive live row updates.
-- ============================================================

-- ====== Update status CHECK constraint ======
ALTER TABLE public.context_pages
  DROP CONSTRAINT IF EXISTS context_pages_status_check;

ALTER TABLE public.context_pages
  ADD CONSTRAINT context_pages_status_check
  CHECK (status IN ('draft', 'generating', 'ready', 'stale', 'error'));

-- ====== Enable Realtime publication ======
DO $$
BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE public.context_pages;
EXCEPTION
  WHEN duplicate_object THEN
    -- Table already in publication; safe to ignore.
    NULL;
END;
$$;
