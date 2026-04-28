-- ============================================================
-- Early Access Allowlist
-- ============================================================
-- Restricts signup to emails on the allowlist. The check runs inside
-- handle_new_user(), so a RAISE EXCEPTION rolls back the auth.users
-- insert too — this gates email/password, magic-link, and OAuth in one place.
--
-- Admin invite flow:
--   INSERT INTO public.allowed_emails (email, invited_by_email)
--   VALUES ('user@example.com', 'you@yourcompany.com');
--
-- To re-open public signup later: drop the EXCEPTION branch from
-- handle_new_user() (or always-return TRUE from the membership check).
-- ============================================================

CREATE TABLE IF NOT EXISTS public.allowed_emails (
  email text PRIMARY KEY,
  invited_at timestamptz NOT NULL DEFAULT now(),
  invited_by_email text,
  note text
);

-- Emails are stored lowercased; enforce it.
CREATE OR REPLACE FUNCTION public.allowed_emails_normalize()
RETURNS TRIGGER AS $$
BEGIN
  NEW.email := lower(trim(NEW.email));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS allowed_emails_normalize_trigger ON public.allowed_emails;
CREATE TRIGGER allowed_emails_normalize_trigger
  BEFORE INSERT OR UPDATE ON public.allowed_emails
  FOR EACH ROW EXECUTE FUNCTION public.allowed_emails_normalize();

-- RLS: only service_role can read/write. Frontend never touches this table.
ALTER TABLE public.allowed_emails ENABLE ROW LEVEL SECURITY;

-- Update handle_new_user to enforce the allowlist before creating
-- workspace/profile/membership. Raising an exception here aborts the
-- entire transaction including the auth.users insert.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
DECLARE
  new_workspace_id uuid;
  email_prefix text;
  display_name text;
  workspace_slug text;
  is_allowed boolean;
BEGIN
  -- Allowlist check (case-insensitive).
  SELECT EXISTS (
    SELECT 1 FROM public.allowed_emails
    WHERE email = lower(NEW.email)
  ) INTO is_allowed;

  IF NOT is_allowed THEN
    -- Custom SQLSTATE 'PT001' lets the API layer recognize this rejection.
    RAISE EXCEPTION 'early_access_required'
      USING ERRCODE = 'PT001',
            HINT = 'This email is not on the early-access allowlist.';
  END IF;

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

-- Seed: backfill all existing users so this migration is non-breaking.
INSERT INTO public.allowed_emails (email, invited_by_email, note)
SELECT lower(email), 'system', 'backfilled existing user'
FROM auth.users
WHERE email IS NOT NULL
ON CONFLICT (email) DO NOTHING;
