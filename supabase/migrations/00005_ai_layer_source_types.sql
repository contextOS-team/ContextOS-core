-- Add github_pull_request and github_review to embeddings.source_type CHECK constraint.
-- These source types were missing from migration 00001 when GitHub integration was added.

ALTER TABLE public.embeddings
  DROP CONSTRAINT IF EXISTS embeddings_source_type_check;

ALTER TABLE public.embeddings
  ADD CONSTRAINT embeddings_source_type_check
  CHECK (source_type IN (
    'slack_message',
    'linear_ticket',
    'linear_comment',
    'notion_page',
    'meeting_transcript',
    'meeting_segment',
    'context_page',
    'github_pull_request',
    'github_review'
  ));
