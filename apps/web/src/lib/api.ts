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

export function getSlackChannels(): Promise<{ channels: SlackChannel[] }> {
  return apiFetch<{ channels: SlackChannel[] }>('/api/slack/channels')
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

export function getGithubRepos(): Promise<{ repos: GithubRepo[] }> {
  return apiFetch<{ repos: GithubRepo[] }>('/api/github/repos')
}

export function refreshGithubRepos(): Promise<{ repos: GithubRepo[] }> {
  return apiFetch<{ repos: GithubRepo[] }>('/api/github/repos/refresh', {
    method: 'POST',
  })
}

export function saveGithubRepoSelection(
  repoFullNames: string[]
): Promise<{ status: string; selected_repos: string[] }> {
  return apiFetch<{ status: string; selected_repos: string[] }>(
    '/api/github/repos/select',
    {
      method: 'POST',
      body: JSON.stringify({ repo_full_names: repoFullNames }),
    }
  )
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
