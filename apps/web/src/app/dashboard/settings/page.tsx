'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import {
  Key,
  Copy,
  Check,
  Loader2,
  RefreshCw,
  AlertCircle,
  Terminal,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import {
  getWorkspace,
  updateWorkspaceName,
  listApiKeys,
  createApiKey,
  revokeApiKey,
  listTeamMembers,
  getIntegrationStatus,
  connectLinear,
  disconnectLinear,
  connectSlack,
  disconnectSlack,
  connectFathom,
  disconnectFathom,
  connectTelegram,
  disconnectTelegram,
  connectGithub,
  disconnectGithub,
  connectGitlab,
  disconnectGitlab,
  connectNotion,
  disconnectNotion,
  connectJira,
  disconnectJira,
  resyncNotion,
  getNotionSyncStatus,
  type WorkspaceResponse,
  type ApiKeyResponse,
  type ApiKeyCreatedResponse,
  type TeamMember,
  type IntegrationStatusResponse,
} from '@/lib/api'
import { displayName, formatRelativeTime } from '@/lib/utils'
import {
  LinearLogo,
  SlackLogo,
  GitHubLogo,
  GitLabLogo,
  FathomLogo,
  NotionLogo,
  TelegramLogo,
  JiraLogo,
} from '@/components/icons/brand-logos'
import { IntegrationCard } from '../integrations/integration-card'
import { SlackChannels } from '../integrations/slack-channels'
import { FathomConnect } from '../integrations/fathom-connect'
import { GithubRepos } from '../integrations/github-repos'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Tab = 'general' | 'api-keys' | 'team' | 'integrations'

const TABS: { id: Tab; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'api-keys', label: 'API Keys' },
  { id: 'team', label: 'Team' },
  { id: 'integrations', label: 'Integrations' },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function SettingsSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in-up">
      <Skeleton className="h-8 w-32" />
      <div className="flex gap-1">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-8 w-24 rounded-lg" />
        ))}
      </div>
      <div className="rounded-xl border bg-card p-6 space-y-4">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-9 w-full max-w-sm" />
        <Skeleton className="h-9 w-20" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: General
// ---------------------------------------------------------------------------

function GeneralTab({
  workspace,
  onUpdate,
}: {
  workspace: WorkspaceResponse
  onUpdate: (ws: WorkspaceResponse) => void
}) {
  const [workspaceName, setWorkspaceName] = useState(workspace.name)
  const [originalName] = useState(workspace.name)
  const [isSaving, setIsSaving] = useState(false)
  const nameChanged = workspaceName.trim() !== originalName && workspaceName.trim().length > 0

  const handleSave = async () => {
    if (!nameChanged) return
    setIsSaving(true)
    try {
      const updated = await updateWorkspaceName(workspaceName.trim())
      onUpdate(updated)
      toast.success('Workspace name updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-xl border bg-card p-6">
      <div className="flex flex-col gap-4 max-w-sm">
        <Label htmlFor="workspace-name" className="text-sm font-medium">
          Workspace name
        </Label>
        <div className="flex gap-2">
          <Input
            id="workspace-name"
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
            placeholder="My workspace"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && nameChanged && !isSaving) handleSave()
            }}
          />
          <Button onClick={handleSave} disabled={!nameChanged || isSaving} size="sm">
            {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
            Save
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: API Keys
// ---------------------------------------------------------------------------

function ApiKeysTab() {
  const [apiKeys, setApiKeys] = useState<ApiKeyResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [newKeyName, setNewKeyName] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [createdKey, setCreatedKey] = useState<ApiKeyCreatedResponse | null>(null)
  const [copied, setCopied] = useState(false)
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchKeys = useCallback(async () => {
    try {
      const resp = await listApiKeys()
      setApiKeys(resp.keys)
    } catch {
      toast.error('Failed to load API keys')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchKeys()
  }, [fetchKeys])

  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current)
    }
  }, [])

  const handleCreate = async () => {
    if (!newKeyName.trim()) return
    setIsCreating(true)
    try {
      const created = await createApiKey(newKeyName.trim())
      setCreatedKey(created)
      setNewKeyName('')
      await fetchKeys()
      toast.success('API key created')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create key')
    } finally {
      setIsCreating(false)
    }
  }

  const handleCopy = async () => {
    if (!createdKey) return
    try {
      await navigator.clipboard.writeText(createdKey.key)
      setCopied(true)
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current)
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('Failed to copy to clipboard')
    }
  }

  const handleRevoke = async (keyId: string) => {
    try {
      await revokeApiKey(keyId)
      await fetchKeys()
      toast.success('API key revoked')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to revoke key')
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-9 w-full max-w-md" />
        <Skeleton className="h-16 w-full rounded-xl" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Create form */}
      <div className="flex gap-2">
        <Input
          value={newKeyName}
          onChange={(e) => setNewKeyName(e.target.value)}
          placeholder="Key name, e.g. MCP Server"
          className="max-w-sm"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && newKeyName.trim() && !isCreating) handleCreate()
          }}
        />
        <Button onClick={handleCreate} disabled={!newKeyName.trim() || isCreating} size="sm">
          {isCreating && <Loader2 className="h-4 w-4 animate-spin" />}
          Create key
        </Button>
      </div>

      {/* Newly created key banner */}
      {createdKey && (
        <div className="rounded-xl border border-primary/20 bg-primary/[0.03] p-4 space-y-3 animate-scale-in">
          <div className="flex items-start gap-2">
            <Key className="h-4 w-4 mt-0.5 text-primary shrink-0" />
            <p className="font-mono text-sm break-all flex-1 text-foreground">
              {createdKey.key}
            </p>
            <Button variant="ghost" size="icon-xs" onClick={handleCopy} className="shrink-0">
              {copied ? (
                <Check className="h-3.5 w-3.5 text-primary" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Copy this key now — you won&apos;t be able to see it again.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setCreatedKey(null)
              setCopied(false)
            }}
          >
            Done
          </Button>
        </div>
      )}

      {/* Key list or empty state */}
      {apiKeys.length === 0 ? (
        <div className="rounded-xl border bg-card p-8 text-center">
          <div className="mx-auto w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-3">
            <Terminal className="h-5 w-5 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium text-foreground mb-1">No API keys yet</p>
          <p className="text-xs text-muted-foreground max-w-xs mx-auto">
            API keys let external tools like the ContextOS MCP server access your workspace data.
            Create one above to get started.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
          {apiKeys.map((apiKey) => (
            <div key={apiKey.id} className="flex items-center gap-3 px-4 py-3">
              <span className="font-medium text-sm">{apiKey.name}</span>
              <span className="font-mono text-sm text-muted-foreground">
                {apiKey.key_prefix}...
              </span>
              <span className="text-xs text-muted-foreground ml-auto mr-2">
                {formatRelativeTime(apiKey.created_at)}
              </span>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                  >
                    Revoke
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>
                      Revoke &lsquo;{apiKey.name}&rsquo;?
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      This key will stop working immediately. This cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => handleRevoke(apiKey.id)}
                      className="bg-destructive text-white hover:bg-destructive/90"
                    >
                      Revoke
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab: Team
// ---------------------------------------------------------------------------

function TeamTab() {
  const [members, setMembers] = useState<TeamMember[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    listTeamMembers()
      .then((resp) => setMembers(resp.members))
      .catch(() => toast.error('Failed to load team'))
      .finally(() => setIsLoading(false))
  }, [])

  if (isLoading) {
    return (
      <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
        {[1, 2].map((i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-3">
            <Skeleton className="h-8 w-8 rounded-full" />
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-3 w-40" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-3">
        {members.length} member{members.length !== 1 ? 's' : ''} in this workspace
      </p>
      <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
        {members.map((member) => {
          const name = member.full_name || member.email
          const initials = getInitials(name)
          return (
            <div key={member.user_id} className="flex items-center gap-3 px-4 py-3">
              <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-semibold shrink-0">
                {initials}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">
                  {member.full_name || member.email}
                </p>
                {member.full_name && (
                  <p className="text-xs text-muted-foreground truncate">{member.email}</p>
                )}
              </div>
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${
                  member.role === 'owner'
                    ? 'bg-primary/10 text-primary'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {member.role === 'owner' ? 'Owner' : 'Member'}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Telegram Connect Form
// ---------------------------------------------------------------------------

function TelegramConnect({ onConnected }: { onConnected?: () => void }) {
  const [token, setToken] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!token.trim()) {
      setError('Bot token is required')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      await connectTelegram(token.trim())
      setToken('')
      onConnected?.()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to connect. Check your bot token.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="telegram-bot-token" className="text-xs">
          Bot Token
        </Label>
        <Input
          id="telegram-bot-token"
          type="password"
          placeholder="Bot token from @BotFather"
          value={token}
          onChange={(e) => {
            setToken(e.target.value)
            setError(null)
          }}
          className="h-8 text-xs"
          autoComplete="off"
        />
        <p className="text-xs text-muted-foreground">
          Create a bot via @BotFather on Telegram. In Bot Settings, turn Group Privacy OFF so the bot can read all messages.
        </p>
      </div>

      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      <Button size="sm" type="submit" disabled={isLoading || !token.trim()}>
        {isLoading ? 'Connecting...' : 'Connect'}
      </Button>
    </form>
  )
}

// ---------------------------------------------------------------------------
// Tab: Integrations
// ---------------------------------------------------------------------------

function IntegrationsTab() {
  const searchParams = useSearchParams()
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    for (const provider of ['github', 'gitlab', 'notion', 'jira'] as const) {
      const status = searchParams.get(provider)
      if (status === 'connected') {
        setError(null)
        window.history.replaceState({}, '', '/dashboard/settings?tab=integrations')
      } else if (status === 'error') {
        const reason = searchParams.get('reason') || 'unknown'
        const label = provider === 'github' ? 'GitHub' : provider === 'gitlab' ? 'GitLab' : provider === 'jira' ? 'Jira' : 'Notion'
        const messages: Record<string, string> = {
          invalid_state: `${label} connection failed: invalid or expired session.`,
          callback_failed: `${label} connection failed. Please try again.`,
          exchange_failed: `${label} connection failed. Please try again.`,
          internal_error: `An internal error occurred during ${label} connection.`,
        }
        setError(messages[reason] || `${label} connection failed: ${reason}`)
        window.history.replaceState({}, '', '/dashboard/settings?tab=integrations')
      }
    }
  }, [searchParams])

  const fetchStatuses = useCallback(async () => {
    try {
      const data = await getIntegrationStatus()
      setStatuses(data)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load integrations')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchStatuses()
  }, [fetchStatuses])

  function makeConnectHandler(
    connectFn: () => Promise<{ authorization_url?: string; installation_url?: string }>,
    urlKey: 'authorization_url' | 'installation_url'
  ) {
    return async () => {
      try {
        const result = await connectFn()
        const url = result[urlKey]
        if (url) window.location.href = url
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to start connection')
      }
    }
  }

  function makeDisconnectHandler(disconnectFn: () => Promise<unknown>, name: string) {
    return async () => {
      try {
        await disconnectFn()
      } catch (err) {
        setError(err instanceof Error ? err.message : `Failed to disconnect ${name}`)
      }
      await fetchStatuses()
    }
  }

  const handleConnectLinear = makeConnectHandler(connectLinear, 'authorization_url')
  const handleDisconnectLinear = makeDisconnectHandler(disconnectLinear, 'Linear')
  const handleConnectSlack = makeConnectHandler(connectSlack, 'authorization_url')
  const handleDisconnectSlack = makeDisconnectHandler(disconnectSlack, 'Slack')
  const handleDisconnectFathom = makeDisconnectHandler(disconnectFathom, 'Fathom')
  const handleDisconnectTelegram = makeDisconnectHandler(disconnectTelegram, 'Telegram')
  const handleConnectGithub = makeConnectHandler(connectGithub, 'installation_url')
  const handleDisconnectGithub = makeDisconnectHandler(disconnectGithub, 'GitHub')
  const handleConnectGitlab = makeConnectHandler(connectGitlab, 'authorization_url')
  const handleDisconnectGitlab = makeDisconnectHandler(disconnectGitlab, 'GitLab')
  const handleConnectNotion = makeConnectHandler(connectNotion, 'authorization_url')
  const handleDisconnectNotion = makeDisconnectHandler(disconnectNotion, 'Notion')
  const handleConnectJira = makeConnectHandler(connectJira, 'authorization_url')
  const handleDisconnectJira = makeDisconnectHandler(disconnectJira, 'Jira')

  const [isResyncing, setIsResyncing] = useState(false)
  const [syncProgress, setSyncProgress] = useState<number | null>(null)
  const [syncTotal, setSyncTotal] = useState<number | null>(null)
  const cancelledRef = useRef(false)

  const pollSyncProgress = useCallback(async () => {
    cancelledRef.current = false
    for (let i = 0; i < 180; i++) {
      if (cancelledRef.current) return
      await new Promise((r) => setTimeout(r, 2000))
      if (cancelledRef.current) return
      const s = await getNotionSyncStatus()
      if (cancelledRef.current) return
      setSyncProgress(s.sync_progress ?? s.pages_count)
      setSyncTotal(s.sync_total ?? null)
      if (s.sync_status === 'error') {
        setError('Notion re-sync failed.')
        break
      }
      if (s.sync_status !== 'syncing') break
    }
    if (cancelledRef.current) return
    await fetchStatuses()
    setIsResyncing(false)
    setSyncProgress(null)
    setSyncTotal(null)
  }, [fetchStatuses])

  useEffect(() => {
    if (isLoading || isResyncing) return
    let cancelled = false
    getNotionSyncStatus()
      .then((s) => {
        if (cancelled) return
        if (s.sync_status === 'syncing') {
          setIsResyncing(true)
          setSyncProgress(s.sync_progress ?? 0)
          setSyncTotal(s.sync_total ?? null)
          pollSyncProgress()
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
      cancelledRef.current = true
    }
  }, [isLoading]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleResyncNotion = async () => {
    setIsResyncing(true)
    setSyncProgress(0)
    try {
      await resyncNotion()
      await pollSyncProgress()
    } catch {
      setError('Failed to start Notion re-sync.')
      setIsResyncing(false)
      setSyncProgress(null)
      setSyncTotal(null)
    }
  }

  if (isLoading) {
    return (
      <div className="grid gap-3 md:grid-cols-2 items-start">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="rounded-2xl border border-border p-4 space-y-3">
            <div className="flex items-center gap-3">
              <Skeleton className="h-5 w-5 rounded shrink-0" />
              <Skeleton className="h-5 w-24" />
              <Skeleton className="h-1.5 w-1.5 rounded-full ml-auto" />
            </div>
            <Skeleton className="h-8 w-20" />
          </div>
        ))}
      </div>
    )
  }

  const linear = statuses?.linear ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const slack = statuses?.slack ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const fathom = statuses?.fathom ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const github = statuses?.github ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const gitlab = statuses?.gitlab ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const notion = statuses?.notion ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const telegram = statuses?.telegram ?? { status: 'disconnected' as const, external_name: null, connected_at: null }
  const jira = statuses?.jira ?? { status: 'disconnected' as const, external_name: null, connected_at: null }

  const connectedCount = [linear, slack, fathom, github, gitlab, notion, telegram, jira].filter(
    (s) => s.status === 'connected'
  ).length

  return (
    <div className="space-y-4">
      {/* Status line */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          Manage your tool connections
        </p>
        <span className="text-xs font-mono text-muted-foreground/60">
          {connectedCount}/8
        </span>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-3 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm animate-scale-in">
          <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
          <span className="flex-1 text-destructive">{error}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchStatuses}
            className="h-7 gap-1.5 text-destructive hover:text-destructive"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </Button>
        </div>
      )}

      {/* Cards grid */}
      <div className="grid gap-3 md:grid-cols-2 items-start">
        <div className="flex flex-col gap-3 stagger-children">
          <IntegrationCard
            name="Linear"
            icon={<LinearLogo width={20} height={20} className="text-violet-600 dark:text-violet-400" />}
            status={linear.status}
            externalName={linear.external_name}
            connectedAt={linear.connected_at}
            onConnect={handleConnectLinear}
            onDisconnect={handleDisconnectLinear}
          />
          <IntegrationCard
            name="Jira"
            icon={<JiraLogo width={20} height={20} />}
            status={jira.status}
            externalName={jira.external_name}
            connectedAt={jira.connected_at}
            onConnect={handleConnectJira}
            onDisconnect={handleDisconnectJira}
          />
          <IntegrationCard
            name="Fathom"
            icon={<FathomLogo width={20} height={20} />}
            status={fathom.status}
            externalName={fathom.external_name}
            connectedAt={fathom.connected_at}
            onConnect={() => {}}
            onDisconnect={handleDisconnectFathom}
            connectForm={<FathomConnect onConnected={fetchStatuses} />}
          />
          <IntegrationCard
            name="Notion"
            icon={<NotionLogo width={20} height={20} className="text-foreground" />}
            status={notion.status}
            externalName={displayName(notion.external_name)}
            connectedAt={notion.connected_at}
            onConnect={handleConnectNotion}
            onDisconnect={handleDisconnectNotion}
          >
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {isResyncing && syncProgress !== null
                  ? `Syncing\u2026 ${syncProgress}${syncTotal ? `/${syncTotal}` : ''} pages`
                  : notion.pages_synced != null && notion.pages_synced > 0
                    ? `${notion.pages_synced} pages synced${notion.last_sync_at ? ` \u00b7 ${formatRelativeTime(notion.last_sync_at)}` : ''}`
                    : 'No pages synced yet'}
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleResyncNotion}
                disabled={isResyncing}
                className="text-[13px]"
              >
                {isResyncing && <RefreshCw className="mr-1.5 h-3 w-3 animate-spin" />}
                {isResyncing ? 'Syncing\u2026' : 'Re-sync'}
              </Button>
            </div>
          </IntegrationCard>
        </div>

        <div className="flex flex-col gap-3 stagger-children">
          <IntegrationCard
            name="Slack"
            icon={<SlackLogo width={20} height={20} />}
            status={slack.status}
            externalName={slack.external_name}
            connectedAt={slack.connected_at}
            onConnect={handleConnectSlack}
            onDisconnect={handleDisconnectSlack}
          >
            <SlackChannels onSaved={fetchStatuses} />
          </IntegrationCard>
          <IntegrationCard
            name="Telegram"
            icon={<TelegramLogo width={20} height={20} className="text-[#26A5E4]" />}
            status={telegram.status}
            externalName={telegram.external_name}
            connectedAt={telegram.connected_at}
            onConnect={() => {}}
            onDisconnect={handleDisconnectTelegram}
            connectForm={<TelegramConnect onConnected={fetchStatuses} />}
          />
          <IntegrationCard
            name="GitHub"
            icon={<GitHubLogo width={20} height={20} className="text-foreground" />}
            status={github.status}
            externalName={github.external_name}
            connectedAt={github.connected_at}
            onConnect={handleConnectGithub}
            onDisconnect={handleDisconnectGithub}
          >
            <GithubRepos onSaved={fetchStatuses} />
          </IntegrationCard>
          <IntegrationCard
            name="GitLab"
            icon={<GitLabLogo width={20} height={20} className="text-foreground" />}
            status={gitlab.status}
            externalName={gitlab.external_name}
            connectedAt={gitlab.connected_at}
            onConnect={handleConnectGitlab}
            onDisconnect={handleDisconnectGitlab}
          />
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Settings Page
// ---------------------------------------------------------------------------

export default function SettingsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null)

  // Derive active tab from URL search param
  const tabParam = searchParams.get('tab') as Tab | null
  const activeTab: Tab = tabParam && TABS.some((t) => t.id === tabParam) ? tabParam : 'general'

  const setActiveTab = (tab: Tab) => {
    const params = new URLSearchParams(searchParams.toString())
    if (tab === 'general') {
      params.delete('tab')
    } else {
      params.set('tab', tab)
    }
    const qs = params.toString()
    router.replace(`/dashboard/settings${qs ? `?${qs}` : ''}`, { scroll: false })
  }

  useEffect(() => {
    getWorkspace()
      .then((ws) => {
        setWorkspace(ws)
        setError(null)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load settings')
      })
      .finally(() => setIsLoading(false))
  }, [])

  if (isLoading) return <SettingsSkeleton />

  if (error) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        <h2 className="text-2xl font-semibold tracking-[-0.03em] text-foreground">Settings</h2>
        <div className="rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      {/* Header */}
      <h2 className="text-2xl font-semibold tracking-[-0.03em] text-foreground">Settings</h2>

      {/* Tab navigation */}
      <nav className="flex gap-1 border-b border-border pb-0 mb-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`relative px-3 py-2 text-sm font-medium transition-colors duration-150 ${
              activeTab === tab.id
                ? 'text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab.label}
            {activeTab === tab.id && (
              <span className="absolute bottom-0 left-2 right-2 h-[2px] rounded-full bg-primary" />
            )}
          </button>
        ))}
      </nav>

      {/* Tab content */}
      <div className="animate-fade-in-up" key={activeTab}>
        {activeTab === 'general' && workspace && (
          <GeneralTab workspace={workspace} onUpdate={setWorkspace} />
        )}
        {activeTab === 'api-keys' && <ApiKeysTab />}
        {activeTab === 'team' && <TeamTab />}
        {activeTab === 'integrations' && <IntegrationsTab />}
      </div>
    </div>
  )
}
