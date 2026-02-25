-- Migration: Vault lazy migration tracking
--
-- Adds a vault_migrated_at column to oauth_tokens for tracking which rows
-- have been verified as Vault-only. Token columns (access_token, refresh_token)
-- store Vault secret NAME references, NOT actual token values. The real
-- encrypted tokens live in Supabase Vault.
--
-- These columns are NOT dropped because they hold Vault key names needed for
-- lookups. The "hardening" ensures values are always encrypted in Vault and
-- column values are just name references.

-- Track when each oauth_token row was verified as Vault-migrated
ALTER TABLE public.oauth_tokens
  ADD COLUMN IF NOT EXISTS vault_migrated_at TIMESTAMPTZ DEFAULT NULL;

-- Document that token columns contain Vault secret name references
COMMENT ON COLUMN public.oauth_tokens.access_token IS
  'Vault secret name reference (e.g. oauth_linear_{uuid}_access). NOT an actual token value.';

COMMENT ON COLUMN public.oauth_tokens.refresh_token IS
  'Vault secret name reference (e.g. oauth_linear_{uuid}_refresh). NOT an actual token value. NULL if provider does not issue refresh tokens.';

COMMENT ON COLUMN public.oauth_tokens.vault_migrated_at IS
  'Timestamp when this row was verified as Vault-only. NULL means not yet verified.';
