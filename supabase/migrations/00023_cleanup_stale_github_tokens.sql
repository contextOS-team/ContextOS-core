-- Clean up stale GitHub OAuth tokens where the installation no longer exists.
-- Workspace b0e959c1 has installation_id 114429989 which returns 404 from GitHub.
-- The token expired on 2026-03-07 and was never refreshed.
-- Soft-delete so the indexer stops trying to use it.

UPDATE oauth_tokens
SET deleted_at = now()
WHERE provider = 'github'
  AND deleted_at IS NULL
  AND token_expires_at < now() - interval '1 day';
