'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  connectSlack,
  connectGithub,
  connectGitlab,
  connectNotion,
  connectFathom,
  resyncNotion,
  getNotionSyncStatus,
  getGithubRepos,
  refreshGithubRepos,
  saveGithubRepoSelection,
  triggerGithubIndex,
  getGitlabRepos,
  refreshGitlabRepos,
  selectGitlabRepos,
  triggerGitlabIndex,
  type IntegrationStatusResponse,
  type GithubRepo,
  type GitlabProject,
} from '@/lib/api'
import {
  SlackLogo,
  GitHubLogo,
  GitLabLogo,
  NotionLogo,
  FathomLogo,
  TelegramLogo,
} from '@/components/icons/brand-logos'
import { SourceCard } from './source-card'
import { SlackDmToggle } from '@/app/dashboard/integrations/slack-dm-toggle'
import { TelegramPairingProgress } from '@/app/dashboard/integrations/telegram-pairing-progress'
import { createClient } from '@/lib/supabase/client'
import { toast } from 'sonner'
import { Check, Lock, Globe, RefreshCw, Search } from 'lucide-react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ExpandedSource = 'github' | 'gitlab' | 'notion' | 'slack' | 'telegram' | null

interface StepSourcesProps {
  onComplete: () => void
  integrations: IntegrationStatusResponse | null
  onSourceConnected: () => void
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function StepSources({ onComplete, integrations, onSourceConnected }: StepSourcesProps) {
  const [connecting, setConnecting] = useState<string | null>(null)
  const [showFathomForm, setShowFathomForm] = useState(false)
  const [fathomKey, setFathomKey] = useState('')
  const [fathomLoading, setFathomLoading] = useState(false)

  // Phase 40 shared-bot pairing — Telegram source card opens an inline
  // TelegramPairingProgress panel, identical to the Settings → Integrations
  // surface. The new flow has no bot-token form and no history sync.
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)

  // Post-connect config state
  const [expandedSource, setExpandedSource] = useState<ExpandedSource>(null)

  const slackConnected = integrations?.slack.status === 'connected'
  const githubConnected = integrations?.github.status === 'connected'
  const gitlabConnected = integrations?.gitlab?.status === 'connected'
  const notionConnected = integrations?.notion.status === 'connected'
  const fathomConnected = integrations?.fathom.status === 'connected'
  const telegramConnected = integrations?.telegram.status === 'connected'

  // Resolve workspace_id client-side via auth.getUser → workspace_members
  // (mirror of the pattern in telegram-connect.tsx). RLS scopes the SELECT
  // to the user's own membership row.
  useEffect(() => {
    let cancelled = false
    const run = async () => {
      const supabase = createClient()
      const {
        data: { user },
      } = await supabase.auth.getUser()
      if (!user || cancelled) return
      const { data: ws } = await supabase
        .from('workspace_members')
        .select('workspace_id')
        .eq('user_id', user.id)
        .limit(1)
        .maybeSingle()
      if (cancelled) return
      if (ws?.workspace_id) {
        setWorkspaceId(ws.workspace_id as string)
      }
    }
    void run()
    return () => {
      cancelled = true
    }
  }, [])

  // Auto-expand config panel when returning from OAuth
  const autoExpandedRef = useRef(false)
  useEffect(() => {
    if (autoExpandedRef.current) return
    if (githubConnected && !expandedSource) {
      autoExpandedRef.current = true
      setExpandedSource('github')
    } else if (gitlabConnected && !expandedSource) {
      autoExpandedRef.current = true
      setExpandedSource('gitlab')
    } else if (notionConnected && !expandedSource) {
      autoExpandedRef.current = true
      setExpandedSource('notion')
    } else if (slackConnected && !expandedSource) {
      autoExpandedRef.current = true
      setExpandedSource('slack')
    }
  }, [githubConnected, gitlabConnected, notionConnected, slackConnected, expandedSource])

  // ---- Connect handlers ----

  async function handleSlack() {
    setConnecting('slack')
    try {
      const { authorization_url } = await connectSlack()
      window.location.href = authorization_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect Slack')
      setConnecting(null)
    }
  }

  async function handleGithub() {
    setConnecting('github')
    try {
      const { installation_url } = await connectGithub()
      window.location.href = installation_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect GitHub')
      setConnecting(null)
    }
  }

  async function handleGitlab() {
    setConnecting('gitlab')
    try {
      const { authorization_url } = await connectGitlab()
      window.location.href = authorization_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect GitLab')
      setConnecting(null)
    }
  }

  async function handleNotion() {
    setConnecting('notion')
    try {
      const { authorization_url } = await connectNotion()
      window.location.href = authorization_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect Notion')
      setConnecting(null)
    }
  }

  function handleFathomClick() {
    if (fathomConnected) return
    setShowFathomForm(true)
    setExpandedSource(null)
  }

  function handleTelegramClick() {
    if (telegramConnected) return
    setShowFathomForm(false)
    setFathomKey('')
    setExpandedSource(expandedSource === 'telegram' ? null : 'telegram')
  }

  async function handleFathomSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!fathomKey.trim()) return
    setFathomLoading(true)
    try {
      await connectFathom(fathomKey.trim())
      setShowFathomForm(false)
      setFathomKey('')
      onSourceConnected()
      toast.success('Fathom connected')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect Fathom')
    } finally {
      setFathomLoading(false)
    }
  }

  // Handle source card click for sources that need post-connect config
  function handleSourceCardClick(source: string) {
    if (source === 'github' && githubConnected) {
      setExpandedSource(expandedSource === 'github' ? null : 'github')
      return
    }
    if (source === 'gitlab' && gitlabConnected) {
      setExpandedSource(expandedSource === 'gitlab' ? null : 'gitlab')
      return
    }
    if (source === 'notion' && notionConnected) {
      setExpandedSource(expandedSource === 'notion' ? null : 'notion')
      return
    }
    if (source === 'slack' && slackConnected) {
      setExpandedSource(expandedSource === 'slack' ? null : 'slack')
      return
    }
  }

  const connectedCount = [slackConnected, githubConnected, gitlabConnected, notionConnected, fathomConnected, telegramConnected].filter(Boolean).length

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Connect your tools</h2>
        <p className="text-sm text-muted-foreground">
          The more sources you connect, the richer your context pages will be.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <SourceCard
          name="Slack"
          logo={<SlackLogo width={32} height={32} />}
          connected={slackConnected}
          onClick={slackConnected ? () => handleSourceCardClick('slack') : handleSlack}
          disabled={connecting === 'slack'}
        />
        <SourceCard
          name="GitHub"
          logo={<GitHubLogo width={32} height={32} />}
          connected={githubConnected}
          onClick={githubConnected ? () => handleSourceCardClick('github') : handleGithub}
          disabled={connecting === 'github'}
        />
        <SourceCard
          name="GitLab"
          logo={<GitLabLogo width={32} height={32} />}
          connected={gitlabConnected}
          onClick={gitlabConnected ? () => handleSourceCardClick('gitlab') : handleGitlab}
          disabled={connecting === 'gitlab'}
        />
        <SourceCard
          name="Notion"
          logo={<NotionLogo width={32} height={32} />}
          connected={notionConnected}
          onClick={notionConnected ? () => handleSourceCardClick('notion') : handleNotion}
          disabled={connecting === 'notion'}
        />
        <SourceCard
          name="Fathom"
          logo={<FathomLogo width={32} height={32} />}
          connected={fathomConnected}
          onClick={handleFathomClick}
        />
        <SourceCard
          name="Telegram"
          logo={<TelegramLogo width={32} height={32} />}
          connected={telegramConnected}
          onClick={handleTelegramClick}
        />
      </div>

      {/* Inline post-connect config panels */}
      {expandedSource === 'github' && githubConnected && (
        <OnboardingRepoPicker provider="github" />
      )}
      {expandedSource === 'gitlab' && gitlabConnected && (
        <OnboardingRepoPicker provider="gitlab" />
      )}
      {expandedSource === 'notion' && notionConnected && (
        <OnboardingNotionSync />
      )}
      {expandedSource === 'slack' && slackConnected && (
        <OnboardingSlackDms />
      )}

      {/* Telegram inline pairing block (Phase 40 shared-bot model) */}
      {expandedSource === 'telegram' && !telegramConnected && workspaceId && (
        <div className="dashboard-panel p-4">
          <TelegramPairingProgress
            workspaceId={workspaceId}
            onConnected={() => {
              onSourceConnected()
              setExpandedSource(null)
              toast.success('Telegram connected')
            }}
            onClose={() => setExpandedSource(null)}
          />
        </div>
      )}

      {/* Fathom inline form */}
      {showFathomForm && !fathomConnected && (
        <form onSubmit={handleFathomSubmit} className="dashboard-panel space-y-3 p-4">
          <div className="space-y-1.5">
            <label htmlFor="fathom-api-key-onboarding" className="text-xs font-medium">
              Fathom API Key
            </label>
            <Input
              id="fathom-api-key-onboarding"
              type="password"
              placeholder="Enter your Fathom API key"
              value={fathomKey}
              onChange={(e) => setFathomKey(e.target.value)}
              className="dashboard-input h-8 text-xs"
              autoComplete="off"
              autoFocus
            />
            <p className="text-xs text-muted-foreground">
              Find your API key in{' '}
              <a
                href="https://fathom.video/api_clients/new"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-primary underline underline-offset-2 hover:text-primary/80"
              >
                Fathom &rarr; API Clients
              </a>
            </p>
          </div>
          <div className="flex gap-2">
            <Button size="sm" type="submit" disabled={fathomLoading || !fathomKey.trim()}>
              {fathomLoading ? 'Connecting...' : 'Connect'}
            </Button>
            <Button
              size="sm"
              type="button"
              variant="ghost"
              onClick={() => { setShowFathomForm(false); setFathomKey('') }}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      <Button onClick={onComplete} className="w-full">
        {connectedCount > 0 ? 'Go to dashboard' : 'Skip for now'}
      </Button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline repo picker (compact version for onboarding)
// ---------------------------------------------------------------------------

function OnboardingRepoPicker({ provider }: { provider: 'github' | 'gitlab' }) {
  const [repos, setRepos] = useState<(GithubRepo | GitlabProject)[]>([])
  const [selectedKeys, setSelectedKeys] = useState<Set<string | number>>(new Set())
  const [savedKeys, setSavedKeys] = useState<Set<string | number>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const fetchRepos = useCallback(async () => {
    setIsLoading(true)
    try {
      if (provider === 'github') {
        const data = await getGithubRepos()
        if ((!data.repos || data.repos.length === 0) && mountedRef.current) {
          setIsRefreshing(true)
          try {
            const fresh = await refreshGithubRepos()
            setRepos(fresh.repos || [])
            const sel = new Set<string | number>(fresh.selected_repos || [])
            setSelectedKeys(sel)
            setSavedKeys(sel)
          } catch {
            setRepos(data.repos || [])
          } finally {
            setIsRefreshing(false)
          }
        } else {
          setRepos(data.repos || [])
          const sel = new Set<string | number>(data.selected_repos || [])
          setSelectedKeys(sel)
          setSavedKeys(sel)
        }
      } else {
        const data = await getGitlabRepos()
        if ((!data.repos || data.repos.length === 0) && mountedRef.current) {
          setIsRefreshing(true)
          try {
            const fresh = await refreshGitlabRepos()
            setRepos(fresh.repos || [])
            const sel = new Set<string | number>(fresh.selected_projects || [])
            setSelectedKeys(sel)
            setSavedKeys(sel)
          } catch {
            setRepos(data.repos || [])
          } finally {
            setIsRefreshing(false)
          }
        } else {
          setRepos(data.repos || [])
          const sel = new Set<string | number>(data.selected_projects || [])
          setSelectedKeys(sel)
          setSavedKeys(sel)
        }
      }
    } catch {
      // Show empty state
    } finally {
      setIsLoading(false)
    }
  }, [provider])

  useEffect(() => { fetchRepos() }, [fetchRepos])

  function getKey(repo: GithubRepo | GitlabProject): string | number {
    return 'full_name' in repo ? repo.full_name : repo.id
  }

  function getName(repo: GithubRepo | GitlabProject): string {
    return 'full_name' in repo ? repo.full_name : repo.path_with_namespace
  }

  function isPrivate(repo: GithubRepo | GitlabProject): boolean {
    return 'private' in repo ? repo.private : repo.visibility === 'private'
  }

  function toggle(key: string | number) {
    setSelectedKeys(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
    setSaved(false)
  }

  function toggleAll() {
    if (selectedKeys.size === filtered.length) {
      setSelectedKeys(new Set())
    } else {
      setSelectedKeys(new Set(filtered.map(getKey)))
    }
    setSaved(false)
  }

  async function handleSave() {
    setIsSaving(true)
    try {
      if (provider === 'github') {
        const result = await saveGithubRepoSelection(Array.from(selectedKeys) as string[])
        const s = new Set<string | number>(result.selected_repos || [])
        setSavedKeys(s)
        setSelectedKeys(s)
        if (s.size > 0) {
          try { await triggerGithubIndex() } catch { /* non-critical */ }
        }
      } else {
        const result = await selectGitlabRepos(Array.from(selectedKeys) as number[])
        const s = new Set<string | number>(result.selected_projects || [])
        setSavedKeys(s)
        setSelectedKeys(s)
        if (s.size > 0) {
          try { await triggerGitlabIndex() } catch { /* non-critical */ }
        }
      }
      setSaved(true)
      toast.success(`${provider === 'github' ? 'GitHub' : 'GitLab'} repos saved — indexing started`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to save selection')
    } finally {
      setIsSaving(false)
    }
  }

  const filtered = repos.filter(r =>
    getName(r).toLowerCase().includes(searchQuery.toLowerCase())
  )

  const hasChanges =
    selectedKeys.size !== savedKeys.size ||
    [...selectedKeys].some(k => !savedKeys.has(k))

  if (isLoading) {
    return (
      <div className="dashboard-panel flex items-center justify-center py-6 text-xs text-muted-foreground">
        <RefreshCw className="mr-2 h-3.5 w-3.5 animate-spin" />
        {isRefreshing ? `Fetching from ${provider === 'github' ? 'GitHub' : 'GitLab'}...` : 'Loading repos...'}
      </div>
    )
  }

  return (
    <div className="dashboard-panel space-y-3 p-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-foreground">
          Select repos to index
        </p>
        <p className="text-[11px] text-muted-foreground">
          {selectedKeys.size} of {repos.length} selected
        </p>
      </div>

      {repos.length > 5 && (
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter repos..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="dashboard-input h-8 pl-8 text-xs"
          />
        </div>
      )}

      <div className="dashboard-list-panel max-h-[200px] space-y-0.5">
        {filtered.length === 0 ? (
          <p className="px-3 py-4 text-center text-xs text-muted-foreground">
            {searchQuery ? 'No repos match' : 'No repos found'}
          </p>
        ) : (
          <>
            {filtered.length > 2 && (
              <label className="dashboard-list-row dashboard-list-row--bordered flex cursor-pointer items-center gap-3 px-3 py-2">
                <input
                  type="checkbox"
                  checked={filtered.length > 0 && selectedKeys.size === filtered.length}
                  onChange={toggleAll}
                  className="h-3.5 w-3.5 rounded border-gray-300 text-primary accent-primary"
                />
                <span className="text-xs font-medium text-muted-foreground">Select all</span>
              </label>
            )}
            {filtered.map(repo => (
              <label
                key={getKey(repo)}
                className="dashboard-list-row flex cursor-pointer items-center gap-3 px-3 py-2"
              >
                <input
                  type="checkbox"
                  checked={selectedKeys.has(getKey(repo))}
                  onChange={() => toggle(getKey(repo))}
                  className="h-3.5 w-3.5 rounded border-gray-300 text-primary accent-primary"
                />
                <span className="flex items-center gap-1.5 text-xs min-w-0">
                  {isPrivate(repo) ? (
                    <Lock className="h-3 w-3 text-muted-foreground shrink-0" />
                  ) : (
                    <Globe className="h-3 w-3 text-muted-foreground shrink-0" />
                  )}
                  <span className="font-medium truncate">{getName(repo)}</span>
                </span>
              </label>
            ))}
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        <Button
          size="sm"
          onClick={handleSave}
          disabled={isSaving || !hasChanges}
        >
          {isSaving ? (
            <>
              <RefreshCw className="mr-1.5 h-3 w-3 animate-spin" />
              Saving...
            </>
          ) : (
            'Save & index'
          )}
        </Button>
        {saved && !hasChanges && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Check className="h-3 w-3 text-green-500" />
            Indexing started
          </span>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline Notion sync (auto-triggers on mount)
// ---------------------------------------------------------------------------

function OnboardingNotionSync() {
  const [syncing, setSyncing] = useState(false)
  const [pageCount, setPageCount] = useState(0)
  const [done, setDone] = useState(false)
  const pollRef = useRef<NodeJS.Timeout | null>(null)
  const mountedRef = useRef(true)
  const startedRef = useRef(false)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const pollStatus = useCallback(async () => {
    try {
      const status = await getNotionSyncStatus()
      if (!mountedRef.current) return
      if (status.status === 'syncing' || status.status === 'discovering') {
        setPageCount(status.sync_progress ?? 0)
      } else {
        setPageCount(status.pages_count ?? status.sync_total ?? 0)
        setDone(true)
        setSyncing(false)
        if (pollRef.current) clearInterval(pollRef.current)
      }
    } catch {
      // Non-blocking
    }
  }, [])

  // Auto-trigger sync on mount
  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true

    async function autoSync() {
      setSyncing(true)
      try {
        // Check if already syncing or has pages
        const status = await getNotionSyncStatus()
        if (status.status === 'syncing' || status.status === 'discovering') {
          // Already syncing, just poll
          setPageCount(status.sync_progress ?? 0)
          pollRef.current = setInterval(pollStatus, 2500)
          return
        }
        if ((status.pages_count ?? 0) > 0) {
          // Already has data
          setPageCount(status.pages_count ?? 0)
          setDone(true)
          setSyncing(false)
          return
        }
        // Trigger sync
        await resyncNotion()
        pollRef.current = setInterval(pollStatus, 2500)
      } catch {
        setSyncing(false)
      }
    }
    autoSync()
  }, [pollStatus])

  return (
    <div className="dashboard-panel p-4">
      <div className="flex items-center gap-2">
        {syncing ? (
          <>
            <div className="h-2 w-2 animate-pulse rounded-full bg-primary" />
            <p className="text-xs text-muted-foreground">
              Syncing Notion pages{pageCount > 0 ? ` — ${pageCount} pages` : '...'}
            </p>
          </>
        ) : done ? (
          <>
            <Check className="h-3.5 w-3.5 text-green-500" />
            <p className="text-xs text-muted-foreground">
              {pageCount} Notion page{pageCount !== 1 ? 's' : ''} synced
            </p>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">
            Preparing to sync Notion pages...
          </p>
        )}
      </div>
      {syncing && (
        <p className="mt-1.5 text-[11px] text-muted-foreground/60">
          Syncing continues in background — you can leave this page
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline Slack DM consent (post-connect)
// ---------------------------------------------------------------------------

function OnboardingSlackDms() {
  return (
    <div className="dashboard-panel space-y-2 p-4">
      <p className="text-xs font-medium text-foreground">Direct messages</p>
      <SlackDmToggle />
      <p
        className="text-[11px] text-muted-foreground/80"
        style={{ textWrap: 'pretty' }}
      >
        You can also change this later in Settings. Channels are monitored
        separately via the Slack bot.
      </p>
    </div>
  )
}
