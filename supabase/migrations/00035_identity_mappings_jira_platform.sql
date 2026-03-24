-- Add 'jira' to identity_mappings platform CHECK constraint.
-- Required for Jira roster seeding and assignee-to-Person linking.

ALTER TABLE public.identity_mappings
  DROP CONSTRAINT IF EXISTS identity_mappings_platform_check;

ALTER TABLE public.identity_mappings
  ADD CONSTRAINT identity_mappings_platform_check
  CHECK (platform IN ('linear', 'slack', 'github', 'fathom', 'jira'));
