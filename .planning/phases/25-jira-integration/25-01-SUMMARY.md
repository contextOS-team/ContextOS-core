---
phase: 25-jira-integration
plan: 01
subsystem: backend/database
tags: [jira, database, models, migration, config]
dependency_graph:
  requires: []
  provides: [jira_issues_table, jira_comments_table, provider_jira_enum, jira_settings]
  affects: [oauth_tokens_constraint, workspace_integrations_constraint, sync_cursors_constraint, context_pages_schema]
tech_stack:
  added: []
  patterns: [sqlmodel-table-mapping, rls-workspace-scoping, provider-check-constraints]
key_files:
  created:
    - supabase/migrations/00019_jira_tables.sql
    - backend/src/models/jira.py
  modified:
    - backend/src/models/integration.py
    - backend/src/config.py
decisions:
  - "Skipped embeddings source_type constraint update -- migration 00017 already dropped the CHECK constraint entirely (source types enforced in application code)"
  - "Skipped context_pages error status update -- migration 00014 already added 'error' to the CHECK constraint"
  - "JiraComment.body nullable (unlike LinearComment) -- Jira allows empty comments with attachments"
metrics:
  duration: 3min
  completed: "2026-03-10"
---

# Phase 25 Plan 01: Database Schema & Backend Models Summary

Jira tables (issues + comments) with workspace-scoped RLS, provider constraint updates, SQLModel classes, and Settings config fields.

## What Was Done

### Task 1: Supabase Migration (00019_jira_tables.sql)
- Created `jira_issues` table with all specified columns (jira_id, jira_key, summary, description, status, priority, issue_type, assignee/reporter names, project key/name, labels array, timestamps, raw_data JSONB)
- Created `jira_comments` table with issue FK, author_name, body, timestamps, raw_data
- Added indexes: workspace_id, trigram on summary, composite (workspace_id, jira_key), composite (workspace_id, issue_id)
- Enabled RLS with workspace_data policies on both tables (workspace_members auth.uid() pattern)
- Added moddatetime triggers for updated_at on both tables
- Updated provider CHECK constraints on oauth_tokens, workspace_integrations, and sync_cursors to include 'jira'
- Added jira_issue_id FK column to context_pages with index

### Task 2: Python Models, Enum, and Config
- Created `backend/src/models/jira.py` with JiraIssue and JiraComment SQLModel classes matching migration schema exactly
- Added `JIRA = "jira"` to Provider enum in integration.py
- Added JIRA_CLIENT_ID, JIRA_CLIENT_SECRET, JIRA_REDIRECT_URI, JIRA_WEBHOOK_SECRET to Settings
- Added jira_redirect_uri property following existing OAuth redirect pattern

## Deviations from Plan

### Skipped Steps (Not Needed)

**1. Embeddings source_type constraint (Plan item 8)**
- Migration 00017 already dropped the embeddings_source_type_check constraint entirely
- Source types are now enforced in application code (SOURCE_TYPE_MAP in embedding.py)
- No migration needed

**2. Context pages error status (Plan item 9)**
- Migration 00014 already added 'error' to context_pages_status_check
- No action needed

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 285e123 | feat(25-01): add Jira tables migration with RLS and constraint updates |
| 2 | 399205f | feat(25-01): add JiraIssue/JiraComment models, Provider.JIRA enum, and Settings config |

## Verification

- Migration file creates jira_issues + jira_comments with RLS, indexes, constraint updates, context_pages FK
- Python models importable and match migration schema
- Provider.JIRA == 'jira' assertion passes
- Settings has all JIRA_* fields accessible
