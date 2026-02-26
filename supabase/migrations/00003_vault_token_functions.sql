-- ============================================================
-- ContextOS Vault Token Functions & Webhook Deliveries
-- Phase 2: Linear Integration
-- ============================================================

-- pgsodium and supabase_vault are pre-installed by Supabase local dev.
-- No need to CREATE EXTENSION; they are managed by the platform.
-- Verify vault schema exists (will fail fast if something is wrong).
do $$ begin
  if not exists (select 1 from information_schema.schemata where schema_name = 'vault') then
    raise exception 'vault schema not found — supabase_vault extension is not installed';
  end if;
end $$;

-- ============================================================
-- VAULT HELPER FUNCTIONS
-- ============================================================
-- These wrap the vault.secrets table with a simple name-based API.
-- Secret naming convention: oauth_{provider}_{workspace_id}_{token_type}
-- e.g., oauth_linear_<uuid>_access, oauth_linear_<uuid>_refresh

-- Store or update a secret by name
-- Uses vault.create_secret / vault.update_secret (the official API) instead of
-- direct INSERT/UPDATE, which require pgsodium crypto function privileges.
create or replace function public.store_vault_secret(
  secret_name text,
  secret_value text,
  description text default null
) returns uuid as $$
declare
  existing_id uuid;
  new_id uuid;
begin
  -- Check if secret with this name already exists
  select id into existing_id
  from vault.secrets
  where name = secret_name;

  if existing_id is not null then
    -- Update existing secret via vault API
    perform vault.update_secret(existing_id, secret_value, store_vault_secret.secret_name,
      coalesce(store_vault_secret.description, (select s.description from vault.secrets s where s.id = existing_id)));
    return existing_id;
  else
    -- Insert new secret via vault API
    new_id := vault.create_secret(secret_value, secret_name, coalesce(description, ''));
    return new_id;
  end if;
end;
$$ language plpgsql security definer
set search_path = vault, public;

-- Read a decrypted secret by name
create or replace function public.read_vault_secret(
  secret_name text
) returns text as $$
declare
  result text;
begin
  select decrypted_secret into result
  from vault.decrypted_secrets
  where name = secret_name;
  return result;
end;
$$ language plpgsql security definer
set search_path = vault, public;

-- Delete a secret by name
create or replace function public.delete_vault_secret(
  secret_name text
) returns void as $$
begin
  delete from vault.secrets
  where name = secret_name;
end;
$$ language plpgsql security definer
set search_path = vault, public;

-- ============================================================
-- VAULT PERMISSIONS
-- ============================================================
-- The postgres role needs SELECT access on vault tables for reads/lookups,
-- and DELETE access for secret removal. INSERT/UPDATE go through the
-- vault.create_secret / vault.update_secret API functions instead of
-- direct DML (which would require pgsodium crypto function privileges).
grant select, delete on vault.secrets to postgres;
grant select on vault.decrypted_secrets to postgres;

-- ============================================================
-- WEBHOOK DELIVERIES (idempotency tracking)
-- ============================================================
create table public.webhook_deliveries (
  id uuid primary key default gen_random_uuid(),
  delivery_id text not null unique,
  provider text not null check (provider in ('linear', 'slack', 'github')),
  processed_at timestamptz not null default now()
);

create index on public.webhook_deliveries (delivery_id);

-- Auto-cleanup: delete deliveries older than 7 days (optional future cron)
-- For now, this is handled by application-level cleanup or pg_cron.
