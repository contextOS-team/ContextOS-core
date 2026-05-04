-- Seed data for local development
-- Run with: supabase db reset

-- Local-only: bypass the early-access allowlist so any email can sign up
-- on localhost. Re-defines handle_new_user() without the allowlist gate.
-- Production runs migrations only (not seed.sql), so the gate stays intact there.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  new_workspace_id uuid;
  email_prefix text;
  display_name text;
  workspace_slug text;
BEGIN
  email_prefix := split_part(NEW.email, '@', 1);
  display_name := COALESCE(
    NEW.raw_user_meta_data->>'full_name',
    NEW.raw_user_meta_data->>'name',
    NEW.raw_user_meta_data->>'user_name',
    NEW.raw_user_meta_data->>'preferred_username',
    email_prefix
  );
  workspace_slug := lower(regexp_replace(email_prefix, '[^a-z0-9]', '-', 'g')) || '-' || substr(gen_random_uuid()::text, 1, 8);

  INSERT INTO public.workspaces (name, slug)
  VALUES (display_name || '''s Workspace', workspace_slug)
  RETURNING id INTO new_workspace_id;

  INSERT INTO public.profiles (id, email, full_name)
  VALUES (NEW.id, NEW.email, display_name);

  INSERT INTO public.workspace_members (workspace_id, user_id, role)
  VALUES (new_workspace_id, NEW.id, 'owner');

  INSERT INTO public.user_onboarding_state (user_id)
  VALUES (NEW.id);

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Insert test workspace
INSERT INTO public.workspaces (id, name, slug) VALUES
  ('00000000-0000-0000-0000-000000000001', 'Test Workspace', 'test-workspace');

-- Note: test user must be created via Supabase Auth (supabase/config.toml or dashboard)
-- After auth user exists, insert profile and membership:
-- INSERT INTO public.profiles (id, email, full_name) VALUES ('<auth-user-id>', 'test@example.com', 'Test User');
-- INSERT INTO public.workspace_members (workspace_id, user_id) VALUES ('00000000-0000-0000-0000-000000000001', '<auth-user-id>');
