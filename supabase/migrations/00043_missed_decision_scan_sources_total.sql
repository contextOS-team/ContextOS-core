-- Migration 00043: missed-decision scan source totals.
-- Stores the source-window count once at scan start so dashboards can read
-- progress without re-counting Slack/Notion/Telegram/Fathom rows repeatedly.

ALTER TABLE public.missed_decision_scan_runs
  ADD COLUMN IF NOT EXISTS sources_total INTEGER;

COMMENT ON COLUMN public.missed_decision_scan_runs.sources_total IS
  'Total source rows in the scan window, computed once when the scan starts.';
