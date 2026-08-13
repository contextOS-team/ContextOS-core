-- Migration 00049: wire api_keys for agent authentication
-- The salted-hash design (00022) made idx_api_keys_hash unusable for lookup —
-- you can't compute the hash without first fetching the row's salt. Auth must
-- look up by key_prefix instead, which had no index. Add it, plus scopes,
-- expiry, and last_used_at for the Decision Context API.

ALTER TABLE public.api_keys
  ADD COLUMN IF NOT EXISTS scopes TEXT[] NOT NULL DEFAULT ARRAY['decisions:read'],
  ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_api_keys_prefix
  ON public.api_keys (key_prefix)
  WHERE revoked_at IS NULL;

COMMENT ON COLUMN public.api_keys.scopes IS
  'Granted scopes, e.g. decisions:read. Agent Decision Context API is read-only.';
COMMENT ON COLUMN public.api_keys.expires_at IS
  'Optional hard expiry; NULL means no expiry.';
COMMENT ON COLUMN public.api_keys.last_used_at IS
  'Stamped on each authenticated request for abuse observability.';
