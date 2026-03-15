-- Expand event_type CHECK constraint to include curated webhook event types.
-- The original constraint was created inline in 00012_onboarding_and_activity.sql.
-- We drop using pg_constraint lookup for safety (name may vary across environments).

DO $$ BEGIN
  EXECUTE (
    SELECT 'ALTER TABLE public.activity_events DROP CONSTRAINT ' || conname
    FROM pg_constraint
    WHERE conrelid = 'public.activity_events'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%event_type%'
  );
EXCEPTION WHEN undefined_object THEN NULL;
          WHEN no_data_found THEN NULL;
END $$;

ALTER TABLE public.activity_events
  ADD CONSTRAINT activity_events_event_type_check CHECK (event_type IN (
    'sync_started',
    'sync_completed',
    'context_generated',
    'integration_connected',
    'integration_disconnected',
    'user_signed_up',
    'ticket_created',
    'pr_merged',
    'meeting_recorded',
    'page_created'
  ));
