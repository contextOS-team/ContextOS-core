-- Migration 00045: missed_decision_reliability_counts
-- Adds inspectable scan counters and an idempotent candidate key.

ALTER TABLE public.missed_decision_scan_runs
  ADD COLUMN IF NOT EXISTS review_candidates INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS auto_saved INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS suppressed INTEGER NOT NULL DEFAULT 0;

WITH duplicate_live_candidates AS (
  SELECT
    id,
    ROW_NUMBER() OVER (
      PARTITION BY
        workspace_id,
        source_type,
        source_id,
        quote_fingerprint,
        decision_fingerprint
      ORDER BY
        CASE lifecycle_status
          WHEN 'confirmed' THEN 0
          WHEN 'linked' THEN 1
          WHEN 'surfaced' THEN 2
          WHEN 'detected' THEN 3
          WHEN 'deferred' THEN 4
          WHEN 'rejected' THEN 5
          WHEN 'suppressed' THEN 6
          ELSE 7
        END,
        created_at ASC,
        id ASC
    ) AS rn
  FROM public.missed_decision_candidates
  WHERE deleted_at IS NULL
)
UPDATE public.missed_decision_candidates AS candidate
SET
  deleted_at = now(),
  updated_at = now(),
  suppression_reason = COALESCE(
    candidate.suppression_reason,
    'duplicate_existing_decision'
  )
FROM duplicate_live_candidates AS duplicate
WHERE candidate.id = duplicate.id
  AND duplicate.rn > 1
  AND candidate.deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_missed_decision_candidates_source_fingerprints
  ON public.missed_decision_candidates (
    workspace_id,
    source_type,
    source_id,
    quote_fingerprint,
    decision_fingerprint
  )
  WHERE deleted_at IS NULL;
