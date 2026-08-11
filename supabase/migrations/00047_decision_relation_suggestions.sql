-- Migration 00047: decision relation proposals surface through suggestions
-- The relation classifier (SAME/SUPPORTS/SUPERSEDES/CONTRADICTS/REFINES)
-- proposes supersession/contradiction reviews as suggestions; humans confirm
-- from there. See docs/technical-plan-winter-2027.md Phase 2.

ALTER TABLE public.suggestions DROP CONSTRAINT IF EXISTS suggestions_type_check;
ALTER TABLE public.suggestions ADD CONSTRAINT suggestions_type_check CHECK (type IN (
  'missing_source_coverage',
  'missed_decision',
  'action_prompt',
  'decision_relation'
));

COMMENT ON CONSTRAINT suggestions_type_check ON public.suggestions IS
  'decision_relation added for supersession/contradiction review proposals.';
