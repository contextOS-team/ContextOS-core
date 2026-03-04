-- ============================================================
-- Enable Realtime for Activity Events
-- Phase 18: Activity Timeline
-- ============================================================
-- Without this, postgres_changes subscriptions on activity_events
-- will silently receive no events. The table must be added to the
-- supabase_realtime publication for Realtime to capture changes.
-- ============================================================

ALTER PUBLICATION supabase_realtime ADD TABLE public.activity_events;
