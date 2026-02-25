-- ============================================================
-- ContextOS Vault Token Functions & Webhook Deliveries
-- Phase 2: Linear Integration
-- ============================================================

-- Enable pgsodium (required by Supabase Vault)
create extension if not exists pgsodium with schema pgsodium;

-- Enable Supabase Vault (wraps pgsodium with a simpler API)
create extension if not exists supabase_vault with schema vault;

-- ============================================================
-- VAULT HELPER FUNCTIONS
-- ============================================================
-- These wrap the vault.secrets table with a simple name-based API.
-- Secret naming convention: oauth_{provider}_{workspace_id}_{token_type}
-- e.g., oauth_linear_<uuid>_access, oauth_linear_<uuid>_refresh

-- Store or update a secret by name
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
    -- Update existing secret
    update vault.secrets
    set secret = secret_value,
        description = coalesce(store_vault_secret.description, vault.secrets.description),
        updated_at = now()
    where id = existing_id;
    return existing_id;
  else
    -- Insert new secret
    insert into vault.secrets (name, secret, description)
    values (secret_name, secret_value, description)
    returning id into new_id;
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
-- In local Supabase, vault.secrets is owned by supabase_admin.
-- The postgres role (used by the backend) needs INSERT/UPDATE access.
-- Grant full access so security-definer functions can operate.
grant all on vault.secrets to postgres;
grant all on vault.decrypted_secrets to postgres;

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
