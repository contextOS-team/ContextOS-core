-- ============================================================
-- Multi-Provider Name Extraction for handle_new_user
-- Phase 21: Auth Redesign & Social OAuth
-- ============================================================
-- Updates handle_new_user to support name extraction from multiple
-- OAuth providers. GitHub uses 'user_name'/'name', Google uses
-- 'full_name'/'name', email signup uses 'full_name'.
-- ============================================================

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
  -- Google provides 'full_name' and 'name'
  -- GitHub provides 'user_name', 'name', and 'preferred_username'
  -- Email signup provides 'full_name' from the form
  display_name := COALESCE(
    NEW.raw_user_meta_data->>'full_name',
    NEW.raw_user_meta_data->>'name',
    NEW.raw_user_meta_data->>'user_name',
    NEW.raw_user_meta_data->>'preferred_username',
    email_prefix
  );
  workspace_slug := lower(regexp_replace(email_prefix, '[^a-z0-9]', '-', 'g')) || '-' || substr(gen_random_uuid()::text, 1, 8);

  -- Create workspace
  INSERT INTO public.workspaces (name, slug)
  VALUES (display_name || '''s Workspace', workspace_slug)
  RETURNING id INTO new_workspace_id;

  -- Create profile
  INSERT INTO public.profiles (id, email, full_name)
  VALUES (NEW.id, NEW.email, display_name);

  -- Create membership (owner role)
  INSERT INTO public.workspace_members (workspace_id, user_id, role)
  VALUES (new_workspace_id, NEW.id, 'owner');

  -- Create onboarding state (step 1, not completed)
  INSERT INTO public.user_onboarding_state (user_id)
  VALUES (NEW.id);

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
