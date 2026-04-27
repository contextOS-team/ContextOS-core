-- ============================================================
-- Fix: Re-apply 'error' to context_pages.status CHECK constraint
-- ============================================================
-- Migration 00014 was supposed to widen the constraint to include
-- 'error' but never landed in the deployed schemas (both local and
-- prod still have the old four-value constraint). Without 'error'
-- as an allowed value, the polling_fallback scheduler crashes every
-- ~15 minutes when it tries to mark stuck "generating" pages as
-- failed (see backend/src/services/sync_scheduler.py:_expire_stale_generations).
--
-- Idempotent: drops the existing constraint by name and recreates it
-- with the full set of allowed values. Safe to apply multiple times.
-- ============================================================

ALTER TABLE public.context_pages
  DROP CONSTRAINT IF EXISTS context_pages_status_check;

ALTER TABLE public.context_pages
  ADD CONSTRAINT context_pages_status_check
  CHECK (status IN ('draft', 'generating', 'ready', 'stale', 'error'));
