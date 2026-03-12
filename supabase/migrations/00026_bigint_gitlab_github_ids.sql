-- Upgrade external ID columns from INTEGER to BIGINT.
-- GitLab note IDs already exceed int32 (max 2,147,483,647);
-- GitHub IDs will follow eventually.

ALTER TABLE gitlab_merge_requests
  ALTER COLUMN gitlab_id TYPE bigint,
  ALTER COLUMN project_id TYPE bigint;

ALTER TABLE gitlab_reviews
  ALTER COLUMN gitlab_id TYPE bigint;

ALTER TABLE github_pull_requests
  ALTER COLUMN github_id TYPE bigint;

ALTER TABLE github_reviews
  ALTER COLUMN github_id TYPE bigint;
