-- Add missing deleted_at column to jira_comments table
-- (jira_issues already has it, jira_comments was missed in 00019b)

alter table public.jira_comments add column if not exists deleted_at timestamptz;
