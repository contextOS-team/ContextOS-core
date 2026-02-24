-- Trigger: Auto-create workspace, profile, and membership on user signup
-- This fires when a new user is inserted into auth.users by Supabase Auth.
-- Creates everything atomically in one transaction.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  new_workspace_id uuid;
  email_prefix text;
  workspace_slug text;
BEGIN
  -- Extract email prefix for workspace naming
  email_prefix := split_part(NEW.email, '@', 1);
  workspace_slug := lower(regexp_replace(email_prefix, '[^a-z0-9]', '-', 'g')) || '-' || substr(gen_random_uuid()::text, 1, 8);

  -- Create workspace
  INSERT INTO public.workspaces (name, slug)
  VALUES (email_prefix || '''s Workspace', workspace_slug)
  RETURNING id INTO new_workspace_id;

  -- Create profile
  INSERT INTO public.profiles (id, email, full_name)
  VALUES (NEW.id, NEW.email, COALESCE(NEW.raw_user_meta_data->>'full_name', email_prefix));

  -- Create membership (owner role)
  INSERT INTO public.workspace_members (workspace_id, user_id, role)
  VALUES (new_workspace_id, NEW.id, 'owner');

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Attach trigger to auth.users table
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
