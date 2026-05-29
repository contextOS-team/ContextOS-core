/**
 * Typed API client for making authenticated requests to the ContextOS backend.
 *
 * Reads the Supabase JWT from the current session and includes it as a
 * Bearer token in the Authorization header.
 */

import { cache } from 'react'
import { createClient } from '@/lib/supabase/client'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

/**
 * Generic fetch wrapper that attaches the Supabase JWT.
 *
 * Caching: every request uses `cache: 'no-store'`. The Next.js Data Cache
 * keys fetches by URL + method + body — NOT by Authorization header — so
 * sharing responses across users via `next: { revalidate }` would leak one
 * user's data to another. Per-request dedup within a single Server
 * Component render is handled by `React.cache(...)` wrappers further down.
 *
 * @param path - API path starting with / (e.g. "/api/integrations/status")
 * @param options - Standard RequestInit options
 * @returns Parsed JSON response
 * @throws Error if response is not ok
 */
export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const supabase = createClient()
  const {
    data: { session },
  } = await supabase.auth.getSession()

  const accessToken = session?.access_token ?? ''

  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...options,
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(`API error ${response.status}: ${text}`)
  }

  return response.json()
}

// ---------------------------------------------------------------------------
// Suggestions
// ---------------------------------------------------------------------------

export type SuggestionStatus = 'open' | 'snoozed' | 'dismissed' | 'resolved'
export type SuggestionPriority = 'high' | 'medium' | 'low'

export interface SuggestionItem {
  id: string
  workspace_id: string
  type: 'missing_source_coverage' | 'missed_decision' | 'action_prompt'
  status: SuggestionStatus
  priority: SuggestionPriority
  fingerprint: string
  entity_type: string | null
  entity_id: string | null
  title: string
  body: string
  primary_action: string | null
  action_href: string | null
  evidence: Record<string, unknown>
  details: Record<string, unknown>
  provenance: Record<string, unknown>
  snoozed_until: string | null
  dismissed_at: string | null
  resolved_at: string | null
  reopened_at: string | null
  last_seen_at: string | null
  created_at: string | null
  updated_at: string | null
}

export function getDashboardSuggestions(
  limit = 3,
  options: { excludeTypes?: SuggestionItem['type'][] } = {}
): Promise<SuggestionItem[]> {
  const params = new URLSearchParams({ limit: String(limit) })
  for (const type of options.excludeTypes ?? []) {
    params.append('exclude_type', type)
  }
  return apiFetch<SuggestionItem[]>(`/api/suggestions?${params.toString()}`)
}

export function getAllSuggestions(limit = 100): Promise<SuggestionItem[]> {
  return apiFetch<SuggestionItem[]>(`/api/suggestions/all?limit=${limit}`)
}

export function dismissSuggestion(id: string): Promise<SuggestionItem> {
  return apiFetch<SuggestionItem>(`/api/suggestions/${id}/dismiss`, {
    method: 'POST',
  })
}

export function snoozeSuggestion(
  id: string,
  snoozedUntil?: string
): Promise<SuggestionItem> {
  return apiFetch<SuggestionItem>(`/api/suggestions/${id}/snooze`, {
    method: 'POST',
    body: JSON.stringify({ snoozed_until: snoozedUntil ?? null }),
  })
}

export function resolveSuggestion(id: string): Promise<SuggestionItem> {
  return apiFetch<SuggestionItem>(`/api/suggestions/${id}/resolve`, {
    method: 'POST',
  })
}

export function reopenSuggestion(id: string): Promise<SuggestionItem> {
  return apiFetch<SuggestionItem>(`/api/suggestions/${id}/reopen`, {
    method: 'POST',
  })
}

// ---------------------------------------------------------------------------
// Missed decisions
// ---------------------------------------------------------------------------

export type MissedDecisionConfidence = 'needs_review' | 'high' | 'very_high'

export type MissedDecisionReviewStatus =
  | 'surfaced'
  | 'confirmed'
  | 'linked'
  | 'deferred'
  | 'rejected'
  | 'suppressed'

export type MissedDecisionMatchStatus =
  | 'strong_match'
  | 'weak_match'
  | 'no_match'
  | string

export type MissedDecisionLegalAction =
  | 'confirm'
  | 'add_evidence'
  | 'defer'
  | 'reject'
  | 'ignore_duplicate'

export interface MissedDecisionPossibleExistingMatch {
  match_status: MissedDecisionMatchStatus | null
  entity_type: string | null
  entity_id: string | null
  title?: string | null
  href?: string | null
  match_reason?: string | null
}

export interface MissedDecisionReviewContext {
  business_category?: string | null
  affected_object?: string | null
  affected_objects?: string[]
  expected_artifact_type?: string | null
  expected_artifact?: string | null
  impact_level?: string | null
  impact_reason?: string | null
  searched_sources?: string[]
  missing_artifact_status?: string | null
  missing_artifact_reason?: string | null
  quality_gate?: {
    passed?: boolean | null
    suppress_reason?: string | null
    artifact_search?: string | null
  }
}

export type MissedDecisionRecommendedAction =
  | 'save_as_new_decision'
  | 'add_as_evidence'
  | 'inspect_existing_match'
  | 'ignore_duplicate'
  | string

export interface MissedDecisionReviewSuggestion {
  id: string
  workspace_id: string
  status: MissedDecisionReviewStatus
  suggestion_id: string | null
  title: string
  inferred_decision: string
  inferred_rationale: string
  source_quote: string
  source_link: string
  confidence: MissedDecisionConfidence
  people: string[]
  author_name?: string | null
  source_channel?: string | null
  source_context?: string | null
  affected_systems: string[]
  review_context: MissedDecisionReviewContext
  possible_existing_match: MissedDecisionPossibleExistingMatch | null
  recommended_action?: MissedDecisionRecommendedAction | null
  legal_actions: MissedDecisionLegalAction[]
}

export interface MissedDecisionActionResponse
  extends MissedDecisionReviewSuggestion {
  decision_node_id?: string | null
}

export type MissedDecisionScanSourceType =
  | 'slack_message'
  | 'notion_page'
  | 'telegram_message'
  | 'fathom_transcript'

export type MissedDecisionScanRunStatus =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'

export interface MissedDecisionScanStatus {
  id: string
  source_type: MissedDecisionScanSourceType
  source_resource_id: string | null
  status: MissedDecisionScanRunStatus
  source_window_start: string | null
  source_window_end: string | null
  sources_scanned: number
  sources_total: number | null
  progress_percent: number | null
  candidates_created: number
  review_candidates: number
  auto_saved: number
  suppressed: number
  started_at: string | null
  completed_at: string | null
  error_message: string | null
}

export function getMissedDecisionReviewSuggestions(
  limit = 5
): Promise<MissedDecisionReviewSuggestion[]> {
  return apiFetch<MissedDecisionReviewSuggestion[]>(
    `/api/missed-decisions/review?limit=${limit}`
  )
}

export function getMissedDecisionScanStatus(): Promise<MissedDecisionScanStatus[]> {
  return apiFetch<MissedDecisionScanStatus[]>('/api/missed-decisions/scans')
}

export function saveMissedDecisionAsNewDecision(
  candidateId: string
): Promise<MissedDecisionActionResponse> {
  return apiFetch<MissedDecisionActionResponse>(
    `/api/missed-decisions/${encodeURIComponent(candidateId)}/confirm`,
    { method: 'POST' }
  )
}

export function addMissedDecisionAsEvidence(
  candidateId: string,
  targetDecisionId?: string | null
): Promise<MissedDecisionActionResponse> {
  return apiFetch<MissedDecisionActionResponse>(
    `/api/missed-decisions/${encodeURIComponent(candidateId)}/add-evidence`,
    {
      method: 'POST',
      body: JSON.stringify({ target_decision_id: targetDecisionId ?? null }),
    }
  )
}

export function deferMissedDecision(
  candidateId: string,
  snoozedUntil?: string | null
): Promise<MissedDecisionActionResponse> {
  return apiFetch<MissedDecisionActionResponse>(
    `/api/missed-decisions/${encodeURIComponent(candidateId)}/defer`,
    {
      method: 'POST',
      body: JSON.stringify({ snoozed_until: snoozedUntil ?? null }),
    }
  )
}

export function dismissMissedDecision(
  candidateId: string,
  reason?: string | null
): Promise<MissedDecisionActionResponse> {
  return apiFetch<MissedDecisionActionResponse>(
    `/api/missed-decisions/${encodeURIComponent(candidateId)}/reject`,
    {
      method: 'POST',
      body: JSON.stringify({ reason: reason ?? null }),
    }
  )
}

export function ignoreMissedDecisionDuplicate(
  candidateId: string
): Promise<MissedDecisionActionResponse> {
  return apiFetch<MissedDecisionActionResponse>(
    `/api/missed-decisions/${encodeURIComponent(candidateId)}/ignore-duplicate`,
    { method: 'POST' }
  )
}

// ---------------------------------------------------------------------------
// Integration status
// ---------------------------------------------------------------------------

export interface ProviderStatus {
  status: 'connected' | 'disconnected' | 'error'
  external_name: string | null
  connected_at: string | null
  selected_channels_count?: number
  selected_repos_count?: number
  pages_synced?: number
  last_sync_at?: string | null
}

/**
 * Slack-specific provider status. Carries the extra fields populated from
 * `/api/slack/status` (introduced in Plan 39-01) so the Settings UI can render
 * the re-auth banner and DM toggle conditionally.
 *
 * The aggregator endpoint `/api/integrations/status` does not populate these
 * fields — the Settings page fetches them on demand via `getSlackStatus()`.
 * Both fields are therefore optional on this type.
 */
export interface SlackProviderStatus extends ProviderStatus {
  needs_reauth?: boolean
  include_dms?: boolean
}

export interface IntegrationStatusResponse {
  linear: ProviderStatus
  slack: SlackProviderStatus
  fathom: ProviderStatus
  github: ProviderStatus
  gitlab: ProviderStatus
  notion: ProviderStatus
  telegram: ProviderStatus
  jira: ProviderStatus
}

export function fetchIntegrationStatus(): Promise<IntegrationStatusResponse> {
  return apiFetch<IntegrationStatusResponse>('/api/integrations/status')
}

export const getIntegrationStatus = cache(fetchIntegrationStatus)

// ---------------------------------------------------------------------------
// Linear
// ---------------------------------------------------------------------------

export function connectLinear(): Promise<{ authorization_url: string }> {
  return apiFetch<{ authorization_url: string }>('/api/linear/connect')
}

export function disconnectLinear(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/linear/disconnect', {
    method: 'POST',
  })
}

export interface LinearTicketSearchResult {
  id: string
  identifier: string
  title: string
  state: string | null
  state_type: string | null
  assignee: string | null
  team_key: string | null
  team_name: string | null
  priority: number | null
  updated_at: string | null
}

export type LinearTicketSearchResponse = {
  tickets: LinearTicketSearchResult[]
  count: number
  has_next_page: boolean
  end_cursor: string | null
}

export function triggerLinearSync(
  teamIds: string[]
): Promise<{ status: string; team_ids: string[] }> {
  return apiFetch<{ status: string; team_ids: string[] }>('/api/linear/sync', {
    method: 'POST',
    body: JSON.stringify({ team_ids: teamIds }),
  })
}

export interface LinearSyncStatus {
  synced_teams: string[]
  sync_status: string | null
  tickets_synced: number
  last_sync_at: string | null
  tickets_count: number
}

export function fetchLinearSyncStatus(): Promise<LinearSyncStatus> {
  return apiFetch<LinearSyncStatus>('/api/linear/sync/status')
}

export const getLinearSyncStatus = cache(fetchLinearSyncStatus)

export const searchLinearTickets = cache(
  (
    query?: string,
    limit?: number,
    after?: string
  ): Promise<LinearTicketSearchResponse> => {
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    if (limit) params.set('limit', String(limit))
    if (after) params.set('after', after)
    const qs = params.toString()
    return apiFetch<LinearTicketSearchResponse>(
      `/api/linear/tickets/search${qs ? `?${qs}` : ''}`
    )
  }
)

// ---------------------------------------------------------------------------
// Slack
// ---------------------------------------------------------------------------

export function connectSlack(): Promise<{ authorization_url: string }> {
  return apiFetch<{ authorization_url: string }>('/api/slack/connect')
}

export function disconnectSlack(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/slack/disconnect', {
    method: 'POST',
  })
}

export interface SlackChannel {
  id: string
  name: string
  is_private: boolean
  num_members: number
}

export const getSlackChannels = cache(
  (): Promise<{ channels: SlackChannel[]; selected_channels?: string[] }> =>
    apiFetch<{ channels: SlackChannel[]; selected_channels?: string[] }>(
      '/api/slack/channels'
    )
)

export function refreshSlackChannels(): Promise<{ channels: SlackChannel[] }> {
  return apiFetch<{ channels: SlackChannel[] }>('/api/slack/channels/refresh', {
    method: 'POST',
  })
}

export function saveSlackChannelSelection(
  channelIds: string[]
): Promise<{ status: string; selected_channels: string[] }> {
  return apiFetch<{ status: string; selected_channels: string[] }>(
    '/api/slack/channels/select',
    {
      method: 'POST',
      body: JSON.stringify({ channel_ids: channelIds }),
    }
  )
}

export interface SlackStatusResponse {
  connected: boolean
  team_name: string | null
  status: 'connected' | 'disconnected' | string
  needs_reauth: boolean
  include_dms: boolean
}

/**
 * Fetch the scoped Slack status — includes `needs_reauth` and `include_dms`
 * which are not populated by the aggregator `/api/integrations/status`.
 */
export const getSlackStatus = cache(
  (): Promise<SlackStatusResponse> =>
    apiFetch<SlackStatusResponse>('/api/slack/status')
)

/**
 * Toggle DM ingestion on/off.
 *
 * Errors:
 * - 409 (detail="needs_reauth") — user token not present; user must reconnect.
 * - 400 (detail="Slack not connected") — no Slack integration at all.
 */
export function toggleSlackDms(
  enabled: boolean
): Promise<{ include_dms: boolean }> {
  return apiFetch<{ include_dms: boolean }>('/api/slack/dms/toggle', {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  })
}

// ---------------------------------------------------------------------------
// Fathom
// ---------------------------------------------------------------------------

export function connectFathom(
  apiKey: string
): Promise<{ status: string; team_name?: string }> {
  return apiFetch<{ status: string; team_name?: string }>(
    '/api/fathom/connect',
    {
      method: 'POST',
      body: JSON.stringify({ api_key: apiKey }),
    }
  )
}

export function disconnectFathom(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/fathom/disconnect', {
    method: 'POST',
  })
}

// ---------------------------------------------------------------------------
// GitHub
// ---------------------------------------------------------------------------

export function connectGithub(): Promise<{ installation_url: string }> {
  return apiFetch<{ installation_url: string }>('/api/github/connect')
}

export function disconnectGithub(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/github/disconnect', {
    method: 'POST',
  })
}

export interface GithubRepo {
  full_name: string
  name: string
  private: boolean
  description: string | null
  language: string | null
}

export interface GithubReposResponse {
  repos: GithubRepo[]
  selected_repos: string[]
}

export const getGithubRepos = cache(
  (): Promise<GithubReposResponse> =>
    apiFetch<GithubReposResponse>('/api/github/repos')
)

export function refreshGithubRepos(): Promise<GithubReposResponse> {
  return apiFetch<GithubReposResponse>('/api/github/repos/refresh', {
    method: 'POST',
  })
}

export function saveGithubRepoSelection(
  repoFullNames: string[]
): Promise<{ selected_repos: string[] }> {
  return apiFetch<{ selected_repos: string[] }>(
    '/api/github/repos/select',
    {
      method: 'POST',
      body: JSON.stringify({ repo_full_names: repoFullNames }),
    }
  )
}

export function triggerGithubIndex(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/github/index', {
    method: 'POST',
  })
}

export function triggerGithubSync(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/github/sync', {
    method: 'POST',
  })
}

export interface GithubSyncStatus {
  repo_sync_status: Record<
    string,
    { status: string; synced: number; total: number }
  >
  last_sync_at: string | null
}

export function fetchGithubSyncStatus(): Promise<GithubSyncStatus> {
  return apiFetch<GithubSyncStatus>('/api/github/sync/status')
}

export const getGithubSyncStatus = cache(fetchGithubSyncStatus)

export interface GithubIndexStatus {
  status: string
  last_indexed_at: string | null
  repos: { repo: string; chunks: number }[]
}

export const getGithubIndexStatus = cache(
  (): Promise<GithubIndexStatus> =>
    apiFetch<GithubIndexStatus>('/api/github/index/status')
)

// ---------------------------------------------------------------------------
// GitLab
// ---------------------------------------------------------------------------

export function connectGitlab(): Promise<{ authorization_url: string }> {
  return apiFetch<{ authorization_url: string }>('/api/gitlab/connect')
}

export function disconnectGitlab(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/gitlab/disconnect', {
    method: 'POST',
  })
}

export interface GitlabProject {
  id: number
  path_with_namespace: string
  name: string
  visibility: 'private' | 'internal' | 'public'
  web_url: string
  description?: string | null
}

export interface GitlabReposResponse {
  repos: GitlabProject[]
  selected_projects: number[]
}

export const getGitlabRepos = cache(
  (): Promise<GitlabReposResponse> =>
    apiFetch<GitlabReposResponse>('/api/gitlab/repos')
)

export function refreshGitlabRepos(): Promise<GitlabReposResponse> {
  return apiFetch<GitlabReposResponse>('/api/gitlab/repos/refresh', {
    method: 'POST',
  })
}

export function selectGitlabRepos(
  projectIds: number[]
): Promise<{ selected_projects: number[] }> {
  return apiFetch<{ selected_projects: number[] }>(
    '/api/gitlab/repos/select',
    {
      method: 'POST',
      body: JSON.stringify({ project_ids: projectIds }),
    }
  )
}

export function triggerGitlabIndex(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/gitlab/index', {
    method: 'POST',
  })
}

export interface GitlabIndexStatus {
  status: string
  last_indexed_at: string | null
  repos: { repo: string; chunks: number }[]
  progress: number | null
  total: number | null
  current_repo: string | null
}

export const getGitlabIndexStatus = cache(
  (): Promise<GitlabIndexStatus> =>
    apiFetch<GitlabIndexStatus>('/api/gitlab/index/status')
)

export function triggerGitlabSync(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/gitlab/sync', {
    method: 'POST',
  })
}

export interface GitlabSyncStatus {
  project_sync_status: Record<
    string,
    { status: string; synced: number; total: number; error_message?: string | null }
  >
  total_mrs: number
  total_reviews: number
  is_syncing: boolean
  last_sync_at: string | null
}

export function fetchGitlabSyncStatus(): Promise<GitlabSyncStatus> {
  return apiFetch<GitlabSyncStatus>('/api/gitlab/sync/status')
}

export const getGitlabSyncStatus = cache(fetchGitlabSyncStatus)

// ---------------------------------------------------------------------------
// Notion
// ---------------------------------------------------------------------------

export function connectNotion(): Promise<{ authorization_url: string }> {
  return apiFetch<{ authorization_url: string }>('/api/notion/connect')
}

export function disconnectNotion(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/notion/disconnect', {
    method: 'POST',
  })
}

export function syncNotion(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/notion/sync', {
    method: 'POST',
  })
}

export function resyncNotion(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/notion/resync', {
    method: 'POST',
  })
}

export interface NotionSyncStatus {
  connected: boolean
  status: string
  sync_status: string | null
  workspace_name: string | null
  pages_count: number
  sync_progress: number | null
  sync_total: number | null
  sync_error: string | null
  sync_started_at: string | null
  last_sync_at: string | null
}

export function fetchNotionSyncStatus(): Promise<NotionSyncStatus> {
  return apiFetch<NotionSyncStatus>('/api/notion/status')
}

export const getNotionSyncStatus = cache(fetchNotionSyncStatus)

export interface NotionPageInfo {
  id: string
  notion_id: string
  title: string
  page_type: string | null
  url: string | null
}

export interface NotionPagesResponse {
  pages: NotionPageInfo[]
  total: number
  page: number
  page_size: number
}

export const getNotionPages = cache(
  (
    page: number = 1,
    pageSize: number = 10
  ): Promise<NotionPagesResponse> =>
    apiFetch<NotionPagesResponse>(
      `/api/notion/pages?page=${page}&page_size=${pageSize}`
    )
)

// ---------------------------------------------------------------------------
// Telegram
// ---------------------------------------------------------------------------

/**
 * Phase 40 shared-bot pairing flow. The user clicks "Connect via @ContextOSBot",
 * the server mints a single-use 16-char base64url code and returns a deep link
 * (https://t.me/<bot>?startgroup=<code>). The frontend opens the deep link in
 * a new tab and listens for the bot's claim via Supabase Realtime on
 * telegram_chat_workspace inserts.
 *
 * Disconnect is intentionally NOT exposed here: in the shared-bot model, the
 * user removes @ContextOSBot from each Telegram group themselves; the bot's
 * `my_chat_member` handler then soft-deletes the chat→workspace mapping.
 */
export interface TelegramPairingCodeResponse {
  code: string
  deep_link: string
  expires_at: string // ISO 8601 UTC
}

/**
 * Thrown when the workspace already has at least one active Telegram chat
 * mapping. The pairing UI surfaces this as "already connected" instead of
 * opening a Telegram deep link.
 */
export class TelegramAlreadyConnectedError extends Error {
  readonly chatCount: number
  constructor(chatCount: number) {
    super('Workspace already has Telegram chat(s) paired')
    this.name = 'TelegramAlreadyConnectedError'
    this.chatCount = chatCount
  }
}

export async function createTelegramPairingCode(): Promise<TelegramPairingCodeResponse> {
  const supabase = createClient()
  const { data: { session } } = await supabase.auth.getSession()
  const response = await fetch(`${BACKEND_URL}/api/telegram/pairing-code`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${session?.access_token ?? ''}`,
    },
  })
  if (response.status === 409) {
    const body = await response.json().catch(() => ({}))
    const detail = (body as { detail?: { chat_count?: number } }).detail
    throw new TelegramAlreadyConnectedError(detail?.chat_count ?? 1)
  }
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(`API error ${response.status}: ${text}`)
  }
  return response.json()
}

// ---------------------------------------------------------------------------
// Jira
// ---------------------------------------------------------------------------

export function connectJira(): Promise<{ authorization_url: string }> {
  return apiFetch<{ authorization_url: string }>('/api/jira/connect')
}

export function disconnectJira(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/jira/disconnect', {
    method: 'POST',
  })
}

export function triggerJiraSync(
  jql?: string | null
): Promise<{ status: string; jql: string | null }> {
  return apiFetch<{ status: string; jql: string | null }>('/api/jira/sync', {
    method: 'POST',
    body: JSON.stringify({ jql: jql ?? null }),
  })
}

export interface JiraSyncStatus {
  sync_status: string | null
  issues_synced: number
  last_sync_at: string | null
  issues_count: number
}

export function fetchJiraSyncStatus(): Promise<JiraSyncStatus> {
  return apiFetch<JiraSyncStatus>('/api/jira/sync/status')
}

export const getJiraSyncStatus = cache(fetchJiraSyncStatus)

export interface JiraIssueSearchResult {
  jira_id: string
  key: string
  summary: string
  status: string | null
  assignee: string | null
  issue_type: string | null
}

export type JiraIssueSearchResponse = {
  issues: JiraIssueSearchResult[]
  count: number
}

export const searchJiraIssues = cache(
  (query?: string): Promise<JiraIssueSearchResponse> => {
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    const qs = params.toString()
    return apiFetch<JiraIssueSearchResponse>(
      `/api/jira/search${qs ? `?${qs}` : ''}`
    )
  }
)

// ---------------------------------------------------------------------------
// Context Pages
// ---------------------------------------------------------------------------

export interface ContextPageSource {
  type: string
  id: string
  title: string
  relevance_score: number
  url?: string
  targets?: string[]
  retrieval_targets?: string[]
  retrieval_signals?: string[]
  retrieval_metadata?: Record<string, unknown>
  features?: ContextPageSourceFeatures
  retrieval_features?: ContextPageSourceFeatures
  graph_path?: ContextPageSourceGraphPathStep[]
  freshness?: string
  verification_state?: string
  source_originality?: string
  why_selected?: string
  suppress_reason?: string
  route_omission_reason?: string
  source_explanation?: string
}

export interface ContextPageSourceGraphPathStep {
  node_id?: string
  entity_type?: string
  title?: string
  relationship?: string | null
}

export interface ContextPageSourceFeatures extends Record<string, unknown> {
  freshness_state?: string
  verification_state?: string
  source_originality?: string
  graph_depth?: number
  graph_path?: ContextPageSourceGraphPathStep[]
}

export interface ContextPageResponse {
  id: string
  ticket_identifier: string
  title: string
  content: string
  summary: string | null
  status: 'draft' | 'generating' | 'ready' | 'stale'
  sources: ContextPageSource[]
  generated_at: string | null
  generation_model: string | null
  generation_tokens_used: number | null
  created_at: string | null
  updated_at: string | null
}

export const getContextPage = cache(
  (ticketIdentifier: string): Promise<ContextPageResponse> =>
    apiFetch<ContextPageResponse>(
      `/api/context/${encodeURIComponent(ticketIdentifier)}`
    )
)

export function generateContextPage(
  ticketIdentifier: string,
  linearIssueId?: string
): Promise<{ status: string; message: string; ticket_identifier: string }> {
  return apiFetch<{
    status: string
    message: string
    ticket_identifier: string
  }>(`/api/context/${encodeURIComponent(ticketIdentifier)}/generate`, {
    method: 'POST',
    body: JSON.stringify(
      linearIssueId ? { linear_issue_id: linearIssueId } : {}
    ),
  })
}

export interface SearchResult {
  id: string
  source_type: string
  source_id: string
  similarity: number
  metadata: Record<string, unknown> | null
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  count: number
}

export const searchContext = cache(
  (
    query: string,
    sourceType?: string,
    limit?: number
  ): Promise<SearchResponse> => {
    const params = new URLSearchParams({ q: query })
    if (sourceType) params.set('source_type', sourceType)
    if (limit) params.set('limit', String(limit))
    return apiFetch<SearchResponse>(`/api/context/?${params.toString()}`)
  }
)

// ---------------------------------------------------------------------------
// Settings - API Keys
// ---------------------------------------------------------------------------

export interface ApiKeyResponse {
  id: string
  name: string
  key_prefix: string
  created_at: string
}

export interface ApiKeyCreatedResponse extends ApiKeyResponse {
  key: string // Full key, shown once only
}

export const listApiKeys = cache(
  (): Promise<{ keys: ApiKeyResponse[] }> =>
    apiFetch<{ keys: ApiKeyResponse[] }>('/api/workspaces/current/api-keys')
)

export function createApiKey(name: string): Promise<ApiKeyCreatedResponse> {
  return apiFetch<ApiKeyCreatedResponse>('/api/workspaces/current/api-keys', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function revokeApiKey(keyId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/api/workspaces/current/api-keys/${keyId}`, {
    method: 'DELETE',
  })
}

// ---------------------------------------------------------------------------
// Settings - Workspace
// ---------------------------------------------------------------------------

export interface WorkspaceResponse {
  id: string
  name: string
  slug: string
  created_at: string
}

export const getWorkspace = cache(
  (): Promise<WorkspaceResponse> =>
    apiFetch<WorkspaceResponse>('/api/workspaces/current')
)

export function updateWorkspaceName(name: string): Promise<WorkspaceResponse> {
  return apiFetch<WorkspaceResponse>('/api/workspaces/current', {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

// ---------------------------------------------------------------------------
// Settings - Team
// ---------------------------------------------------------------------------

export interface TeamMember {
  user_id: string
  full_name: string | null
  email: string
  role: string
  created_at: string
}

export const listTeamMembers = cache(
  (): Promise<{ members: TeamMember[] }> =>
    apiFetch<{ members: TeamMember[] }>('/api/workspaces/current/members')
)

// ---------------------------------------------------------------------------
// Dashboard Intelligence Widgets
// ---------------------------------------------------------------------------

export interface AttentionItem {
  type: 'stale_context' | 'no_sources' | 'pr_review' | 'mr_review'
  id: string
  title: string
  ticket_identifier?: string
  repo_full_name?: string
  project_path?: string
  number?: number
  author?: string
  age?: string
  status?: string
}

export interface DaySummary {
  date: string
  activity_count: number
  contexts_updated: number
  prs_merged: number
}

export interface SprintData {
  team_name: string
  cycle_name: string
  cycle_number: number
  starts_at: string
  ends_at: string
  completed: number
  total: number
  progress: number
}

export interface ResurfacedItem {
  id: string
  text: string
  channel_name: string | null
  user_name: string | null
  created_at: string
  type: 'resurfaced'
}

export const getDashboardAttention = cache(() =>
  apiFetch<AttentionItem[]>('/api/dashboard/attention')
)

export const getDashboardWeeklySummary = cache(() =>
  apiFetch<DaySummary[]>('/api/dashboard/weekly-summary')
)

export const getDashboardSprint = cache(() =>
  apiFetch<SprintData | null>('/api/dashboard/sprint')
)

export const getDashboardResurfaced = cache(() =>
  apiFetch<ResurfacedItem[]>('/api/dashboard/resurfaced')
)

// ---------------------------------------------------------------------------
// Graph Neighborhood
// ---------------------------------------------------------------------------

import type {
  ApiNode,
  GraphNeighborhoodResponse,
  WorkspaceGraphResponse,
  LensGraphResponse,
} from '@/components/graph/types'

export const fetchWorkspaceGraph = cache(
  (limit: number = 200): Promise<WorkspaceGraphResponse> =>
    apiFetch<WorkspaceGraphResponse>(`/api/graph/?limit=${limit}`)
)

export function fetchDecisions(limit: number = 500): Promise<ApiNode[]> {
  return apiFetch<ApiNode[]>(`/api/graph/decisions?limit=${limit}`)
}

export const fetchDecision = cache(
  (decisionId: string): Promise<ApiNode> =>
    apiFetch<ApiNode>(`/api/graph/decisions/${encodeURIComponent(decisionId)}`)
)

export const fetchGraphNeighborhood = cache(
  (
    ticketIdentifier: string,
    depth: number = 2,
    limit: number = 50
  ): Promise<GraphNeighborhoodResponse> =>
    apiFetch<GraphNeighborhoodResponse>(
      `/api/graph/${encodeURIComponent(ticketIdentifier)}?depth=${depth}&limit=${limit}`
    )
)

// ---------------------------------------------------------------------------
// Graph Lenses
// ---------------------------------------------------------------------------

export const fetchMyWorkGraph = cache(
  (): Promise<LensGraphResponse> =>
    apiFetch<LensGraphResponse>('/api/graph/lens/my-work')
)

export const fetchSprintGraph = cache(
  (): Promise<LensGraphResponse> =>
    apiFetch<LensGraphResponse>('/api/graph/lens/sprint')
)

export const fetchBlockedGraph = cache(
  (): Promise<LensGraphResponse> =>
    apiFetch<LensGraphResponse>('/api/graph/lens/blocked')
)

// ---------------------------------------------------------------------------
// SSE Generation Progress
// ---------------------------------------------------------------------------

export interface GenerationStep {
  source: string
  label: string
  status: 'waiting' | 'active' | 'complete' | 'error'
  detail?: string
  count?: number
  syncing?: boolean
}

export type SSEEventData =
  | { event: 'start'; steps: string[] }
  | { event: 'step_start'; source: string }
  | { event: 'step_complete'; source: string; count: number; detail: string; syncing?: boolean }
  | { event: 'step_error'; source: string; error: string }
  | { event: 'complete'; context_page_id: string }
  | { event: 'error'; message: string }

/** Map source keys to human-readable labels */
export const SOURCE_LABELS: Record<string, string> = {
  slack: 'Slack',
  github: 'GitHub',
  gitlab: 'GitLab',
  notion: 'Notion',
  fathom: 'Fathom',
  slack_huddle: 'Slack Huddles',
  linear: 'Linear',
  jira: 'Jira',
  telegram: 'Telegram',
  synthesize: 'Synthesize',
}

/**
 * Consume an SSE stream from the backend with auth headers.
 *
 * Uses fetch + ReadableStream instead of EventSource because
 * EventSource cannot send custom Authorization headers.
 *
 * @param path - API path starting with / (e.g. "/api/context/CON-51/generate-stream")
 * @param onEvent - Callback for each parsed SSE event
 * @param onError - Optional error callback
 * @returns AbortController to cancel the stream
 */
export function apiFetchSSE(
  path: string,
  onEvent: (data: SSEEventData) => void,
  onError?: (error: Error) => void,
): AbortController {
  const controller = new AbortController()

  ;(async () => {
    try {
      const supabase = createClient()
      const { data: { session } } = await supabase.auth.getSession()
      const accessToken = session?.access_token ?? ''

      const response = await fetch(`${BACKEND_URL}${path}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          Accept: 'text/event-stream',
        },
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`SSE error ${response.status}`)
      }
      if (!response.body) {
        throw new Error('No response body')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      let currentData = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const rawLine of lines) {
          const line = rawLine.replace(/\r$/, '')

          if (line.startsWith('data: ')) {
            currentData = line.slice(6)
          } else if (line === '' && currentData) {
            try {
              onEvent(JSON.parse(currentData) as SSEEventData)
            } catch {
              // Skip malformed events
            }
            currentData = ''
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        onError?.(err instanceof Error ? err : new Error(String(err)))
      }
    }
  })()

  return controller
}
