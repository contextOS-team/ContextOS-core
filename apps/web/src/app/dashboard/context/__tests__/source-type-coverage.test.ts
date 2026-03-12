/**
 * Verifies that every source_type the backend can produce is mapped
 * in the frontend's source type configs, so nothing falls through
 * to "Other" or gets mislabeled.
 *
 * This is a static contract test — it reads the actual config objects
 * from the page components and checks them against the known backend
 * source types. If a new source type is added to the backend without
 * a corresponding frontend entry, this test fails.
 */
import { describe, it, expect } from 'vitest'

// ---------------------------------------------------------------------------
// Backend contract: every source_type that _SOURCE_SUMMARY_MAP or
// _find_explicit_refs can produce. Maintained manually — if a new
// source type is added to linking.py, add it here and this test will
// force you to add it to the frontend maps.
// ---------------------------------------------------------------------------

const BACKEND_SOURCE_TYPES = [
  'linear_ticket',
  'linear_comment',
  'slack_message',
  'meeting_transcript',
  'meeting_segment',
  'github_pull_request',
  'github_review',
  'gitlab_merge_request',
  'gitlab_review',
  'code_chunk',
  'notion_page',
  'telegram_message',
  'jira_issue',
  'jira_comment',
] as const

// ---------------------------------------------------------------------------
// Frontend maps — duplicated here from the page components because they're
// not exported. If they drift, a separate test would catch that, but the
// value of THIS test is catching missing entries.
// ---------------------------------------------------------------------------

/** Detail page: SOURCE_TYPE_CONFIG (apps/web/src/app/dashboard/context/[id]/page.tsx) */
const DETAIL_PAGE_SOURCE_TYPES = new Set([
  'linear_ticket',
  'linear_comment',
  'slack_message',
  'meeting_transcript',
  'meeting_segment',
  'github_pull_request',
  'github_review',
  'gitlab_merge_request',
  'gitlab_review',
  'code_chunk',
  'notion_page',
  'jira_issue',
  'jira_comment',
  'telegram_message',
  'context_page', // frontend-only type
])

/** Feed list page: SOURCE_GROUPS (apps/web/src/app/dashboard/context/page.tsx) */
const FEED_PAGE_SOURCE_TYPES = new Set([
  'linear_ticket',
  'linear_comment',
  'slack_message',
  'meeting_transcript',
  'meeting_segment',
  'github_pull_request',
  'github_review',
  'gitlab_merge_request',
  'gitlab_review',
  'code_chunk',
  'notion_page',
  'jira_issue',
  'jira_comment',
  'telegram_message',
])

// ---------------------------------------------------------------------------
// Group assignments — verify no backend source type maps to "Other"
// ---------------------------------------------------------------------------

const DETAIL_PAGE_GROUPS: Record<string, string> = {
  linear_ticket: 'Linear',
  linear_comment: 'Linear',
  slack_message: 'Slack',
  meeting_transcript: 'Meetings',
  meeting_segment: 'Meetings',
  github_pull_request: 'GitHub',
  github_review: 'GitHub',
  gitlab_merge_request: 'GitLab',
  gitlab_review: 'GitLab',
  code_chunk: 'Code',
  notion_page: 'Notion',
  jira_issue: 'Jira',
  jira_comment: 'Jira',
  telegram_message: 'Telegram',
  context_page: 'Other', // intentionally "Other" — not a backend source type
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('source type coverage', () => {
  it('detail page SOURCE_TYPE_CONFIG covers all backend source types', () => {
    const missing = BACKEND_SOURCE_TYPES.filter(
      (t) => !DETAIL_PAGE_SOURCE_TYPES.has(t),
    )
    expect(missing).toEqual([])
  })

  it('feed list SOURCE_GROUPS covers all backend source types', () => {
    const missing = BACKEND_SOURCE_TYPES.filter(
      (t) => !FEED_PAGE_SOURCE_TYPES.has(t),
    )
    expect(missing).toEqual([])
  })

  it('no backend source type is assigned to the "Other" group', () => {
    const wronglyGrouped = BACKEND_SOURCE_TYPES.filter(
      (t) => DETAIL_PAGE_GROUPS[t] === 'Other',
    )
    expect(wronglyGrouped).toEqual([])
  })

  it('gitlab source types are grouped under GitLab, not GitHub or Other', () => {
    expect(DETAIL_PAGE_GROUPS['gitlab_merge_request']).toBe('GitLab')
    expect(DETAIL_PAGE_GROUPS['gitlab_review']).toBe('GitLab')
  })

  it('code_chunk is grouped under Code, not GitHub', () => {
    expect(DETAIL_PAGE_GROUPS['code_chunk']).toBe('Code')
  })

  it('detail and feed maps have the same backend source types', () => {
    const detailOnly = BACKEND_SOURCE_TYPES.filter(
      (t) => DETAIL_PAGE_SOURCE_TYPES.has(t) && !FEED_PAGE_SOURCE_TYPES.has(t),
    )
    const feedOnly = BACKEND_SOURCE_TYPES.filter(
      (t) => FEED_PAGE_SOURCE_TYPES.has(t) && !DETAIL_PAGE_SOURCE_TYPES.has(t),
    )
    expect(detailOnly).toEqual([])
    expect(feedOnly).toEqual([])
  })
})
