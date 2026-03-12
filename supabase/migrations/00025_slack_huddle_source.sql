-- Add 'slack_huddle' to meeting_transcripts.source CHECK constraint
-- This enables storing Slack huddle transcripts alongside existing Fathom transcripts.

ALTER TABLE meeting_transcripts
  DROP CONSTRAINT IF EXISTS meeting_transcripts_source_check;

ALTER TABLE meeting_transcripts
  ADD CONSTRAINT meeting_transcripts_source_check
  CHECK (source IN ('google_meet', 'zoom', 'teams', 'fathom', 'manual', 'slack_huddle'));
