-- Migration: Vault lazy migration tracking
ALTER TABLE public.oauth_tokens
  ADD COLUMN IF NOT EXISTS vault_migrated_at TIMESTAMPTZ DEFAULT NULL;

COMMENT ON COLUMN public.oauth_tokens.access_token IS
  'Vault secret name reference (e.g. oauth_linear_{uuid}_access). NOT an actual token value.';

COMMENT ON COLUMN public.oauth_tokens.refresh_token IS
  'Vault secret name reference (e.g. oauth_linear_{uuid}_refresh). NOT an actual token value. NULL if provider does not issue refresh tokens.';

COMMENT ON COLUMN public.oauth_tokens.vault_migrated_at IS
  'Timestamp when this row was verified as Vault-only. NULL means not yet verified.';
