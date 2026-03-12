/**
 * Typed API client for making authenticated requests to the ContextOS backend.
 *
 * Reads the Supabase JWT from the current session and includes it as a
 * Bearer token in the Authorization header.
 */

import { createClient } from '@/lib/supabase/client'

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000'

/**
 * Generic fetch wrapper that attaches the Supabase JWT.
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

export interface IntegrationStatusResponse {
  linear: ProviderStatus
  slack: ProviderStatus
  fathom: ProviderStatus
  github: ProviderStatus
  notion: ProviderStatus
}

export function getIntegrationStatus(): Promise<IntegrationStatusResponse> {
  return apiFetch<IntegrationStatusResponse>('/api/integrations/status')
}

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

export function searchLinearTickets(
  query?: string,
  limit?: number,
  after?: string
): Promise<LinearTicketSearchResponse> {
  const params = new URLSearchParams()
  if (query) params.set('q', query)
  if (limit) params.set('limit', String(limit))
  if (after) params.set('after', after)
  const qs = params.toString()
  return apiFetch<LinearTicketSearchResponse>(
    `/api/linear/tickets/search${qs ? `?${qs}` : ''}`
  )
}

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

export function getSlackChannels(): Promise<{ channels: SlackChannel[]; selected_channels?: string[] }> {
  return apiFetch<{ channels: SlackChannel[]; selected_channels?: string[] }>('/api/slack/channels')
}

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

export function getGithubRepos(): Promise<GithubReposResponse> {
  return apiFetch<GithubReposResponse>('/api/github/repos')
}

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

export interface GithubIndexStatus {
  status: string
  last_indexed_at: string | null
  repos: { repo: string; chunks: number }[]
}

export function getGithubIndexStatus(): Promise<GithubIndexStatus> {
  return apiFetch<GithubIndexStatus>('/api/github/index/status')
}

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
  last_sync_at: string | null
}

export function getNotionSyncStatus(): Promise<NotionSyncStatus> {
  return apiFetch<NotionSyncStatus>('/api/notion/status')
}

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

export function getNotionPages(
  page: number = 1,
  pageSize: number = 10
): Promise<NotionPagesResponse> {
  return apiFetch<NotionPagesResponse>(
    `/api/notion/pages?page=${page}&page_size=${pageSize}`
  )
}

// ---------------------------------------------------------------------------
// Context Pages
// ---------------------------------------------------------------------------

export interface ContextPageSource {
  type: string
  id: string
  title: string
  relevance_score: number
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

export function getContextPage(
  ticketIdentifier: string
): Promise<ContextPageResponse> {
  return apiFetch<ContextPageResponse>(
    `/api/context/${encodeURIComponent(ticketIdentifier)}`
  )
}

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

export function searchContext(
  query: string,
  sourceType?: string,
  limit?: number
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query })
  if (sourceType) params.set('source_type', sourceType)
  if (limit) params.set('limit', String(limit))
  return apiFetch<SearchResponse>(`/api/context/?${params.toString()}`)
}

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

export function listApiKeys(): Promise<{ keys: ApiKeyResponse[] }> {
  return apiFetch<{ keys: ApiKeyResponse[] }>('/api/workspaces/current/api-keys')
}

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

export function getWorkspace(): Promise<WorkspaceResponse> {
  return apiFetch<WorkspaceResponse>('/api/workspaces/current')
}

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

export function listTeamMembers(): Promise<{ members: TeamMember[] }> {
  return apiFetch<{ members: TeamMember[] }>('/api/workspaces/current/members')
}

// ---------------------------------------------------------------------------
// SSE Generation Progress
// ---------------------------------------------------------------------------

export interface GenerationStep {
  source: string
  label: string
  status: 'waiting' | 'active' | 'complete' | 'error'
  detail?: string
  count?: number
}

export type SSEEventData =
  | { event: 'start'; steps: string[] }
  | { event: 'step_start'; source: string }
  | { event: 'step_complete'; source: string; count: number; detail: string }
  | { event: 'step_error'; source: string; error: string }
  | { event: 'complete'; context_page_id: string }
  | { event: 'error'; message: string }

/** Map source keys to human-readable labels */
export const SOURCE_LABELS: Record<string, string> = {
  slack: 'Slack',
  github: 'GitHub',
  notion: 'Notion',
  fathom: 'Fathom',
  linear: 'Linear',
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
