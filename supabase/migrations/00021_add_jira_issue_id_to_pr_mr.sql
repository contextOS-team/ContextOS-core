-- Add jira_issue_id FK to github_pull_requests and gitlab_merge_requests
-- so PRs/MRs can be explicitly linked to Jira issues (same pattern as linear_ticket_id).

ALTER TABLE public.github_pull_requests
  ADD COLUMN IF NOT EXISTS jira_issue_id uuid REFERENCES public.jira_issues(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_github_pull_requests_jira_issue_id
  ON public.github_pull_requests(jira_issue_id)
  WHERE jira_issue_id IS NOT NULL;

ALTER TABLE public.gitlab_merge_requests
  ADD COLUMN IF NOT EXISTS jira_issue_id uuid REFERENCES public.jira_issues(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_gitlab_merge_requests_jira_issue_id
  ON public.gitlab_merge_requests(jira_issue_id)
  WHERE jira_issue_id IS NOT NULL;
