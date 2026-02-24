-- Seed data for local development
-- Run with: supabase db reset

-- Insert test workspace
INSERT INTO public.workspaces (id, name, slug) VALUES
  ('00000000-0000-0000-0000-000000000001', 'Test Workspace', 'test-workspace');

-- Note: test user must be created via Supabase Auth (supabase/config.toml or dashboard)
-- After auth user exists, insert profile and membership:
-- INSERT INTO public.profiles (id, email, full_name) VALUES ('<auth-user-id>', 'test@example.com', 'Test User');
-- INSERT INTO public.workspace_members (workspace_id, user_id) VALUES ('00000000-0000-0000-0000-000000000001', '<auth-user-id>');
