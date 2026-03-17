-- Enable pg_trgm extension for trigram-based text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN trigram index on slack_messages.text for fast ILIKE '%...%' queries.
-- Without this index, the explicit reference search for Slack messages
-- containing ticket identifiers triggers a full sequential scan.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_slack_messages_text_trgm
  ON slack_messages USING gin (text gin_trgm_ops);
