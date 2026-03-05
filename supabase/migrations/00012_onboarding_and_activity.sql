-- ============================================================
-- Onboarding State & Activity Events
-- Phase 16: Auth Redesign + Schema Foundation
-- ============================================================
-- Adds two tables that Phase 17 (wizard), Phase 18 (timeline),
-- and the onboarding gate all depend on.
-- Extends handle_new_user trigger to auto-create onboarding rows.
-- ============================================================

-- ============================================================
-- USER ONBOARDING STATE
-- ============================================================
-- Tracks each user's progress through the onboarding wizard.
-- NULL completed_at = still onboarding; NULL row = legacy user (treated as completed).

CREATE TABLE public.user_onboarding_state (
  user_id    uuid        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  current_step integer   NOT NULL DEFAULT 1 CHECK (current_step BETWEEN 1 AND 4),
  completed_at timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.user_onboarding_state ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own_onboarding" ON public.user_onboarding_state
  FOR ALL USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE TRIGGER set_updated_at BEFORE UPDATE ON public.user_onboarding_state
  FOR EACH ROW EXECUTE FUNCTION moddatetime(updated_at);

-- ============================================================
-- ACTIVITY EVENTS
-- ============================================================
-- Workspace-scoped activity feed consumed by the dashboard timeline.
-- 30-day retention enforced by pg_cron (see below).

CREATE TABLE public.activity_events (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid        NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  actor_id     uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  event_type   text        NOT NULL CHECK (event_type IN (
    'sync_started',
    'sync_completed',
    'context_generated',
    'integration_connected',
    'integration_disconnected',
    'user_signed_up'
  )),
  metadata     jsonb       DEFAULT '{}',
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_activity_events_workspace_time
  ON public.activity_events (workspace_id, created_at DESC);

ALTER TABLE public.activity_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_data" ON public.activity_events
  FOR ALL USING (
    workspace_id IN (
      SELECT workspace_id FROM public.workspace_members WHERE user_id = auth.uid()
    )
  );

-- ============================================================
-- EXTEND handle_new_user TRIGGER
-- ============================================================
-- Replaces the existing function to add onboarding state creation.
-- Keeps ALL original logic (workspace, profile, membership) intact.
-- The existing on_auth_user_created trigger already fires this function.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  new_workspace_id uuid;
  email_prefix text;
  display_name text;
  workspace_slug text;
BEGIN
  -- Extract email prefix and full name for workspace naming
  email_prefix := split_part(NEW.email, '@', 1);
  display_name := COALESCE(NEW.raw_user_meta_data->>'full_name', email_prefix);
  workspace_slug := lower(regexp_replace(email_prefix, '[^a-z0-9]', '-', 'g')) || '-' || substr(gen_random_uuid()::text, 1, 8);

  -- Create workspace
  INSERT INTO public.workspaces (name, slug)
  VALUES (display_name || '''s Workspace', workspace_slug)
  RETURNING id INTO new_workspace_id;

  -- Create profile
  INSERT INTO public.profiles (id, email, full_name)
  VALUES (NEW.id, NEW.email, COALESCE(NEW.raw_user_meta_data->>'full_name', email_prefix));

  -- Create membership (owner role)
  INSERT INTO public.workspace_members (workspace_id, user_id, role)
  VALUES (new_workspace_id, NEW.id, 'owner');

  -- Create onboarding state (step 1, not completed)
  INSERT INTO public.user_onboarding_state (user_id)
  VALUES (NEW.id);

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- pg_cron 30-DAY RETENTION JOB
-- ============================================================
-- Deletes activity_events older than 30 days, daily at 3:00 AM UTC.
-- Wrapped in exception handler so local dev (without pg_cron) doesn't fail.

DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS pg_cron WITH SCHEMA pg_catalog;
  PERFORM cron.schedule(
    'activity-events-30d-retention',
    '0 3 * * *',
    'DELETE FROM public.activity_events WHERE created_at < now() - interval ''30 days'''
  );
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pg_cron not available -- skip retention job (hosted Supabase will have it)';
END $$;
