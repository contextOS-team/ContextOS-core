'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { Key, Copy, Check, ExternalLink, Loader2 } from 'lucide-react'
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
  type WorkspaceResponse,
  type ApiKeyResponse,
  type ApiKeyCreatedResponse,
  type TeamMember,
} from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

function SettingsSkeleton() {
  return (
    <div className="space-y-6 animate-fade-in-up">
      <Skeleton className="h-8 w-32" />

      {/* General skeleton */}
      <div>
        <Skeleton className="h-3 w-28 mb-3" />
        <div className="rounded-xl border bg-card p-6">
          <Skeleton className="h-9 w-full max-w-sm" />
        </div>
      </div>

      {/* API Keys skeleton */}
      <div>
        <Skeleton className="h-3 w-28 mb-3" />
        <div className="space-y-3">
          <div className="flex gap-2">
            <Skeleton className="h-9 w-64" />
            <Skeleton className="h-9 w-24" />
          </div>
          <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
            {[1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-16 ml-auto" />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Team skeleton */}
      <div>
        <Skeleton className="h-3 w-28 mb-3" />
        <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center gap-3 px-4 py-3">
              <Skeleton className="h-8 w-8 rounded-full" />
              <div className="space-y-1.5">
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-3 w-40" />
              </div>
              <Skeleton className="h-5 w-14 ml-auto rounded-full" />
            </div>
          ))}
        </div>
      </div>

      {/* Integrations skeleton */}
      <div>
        <Skeleton className="h-3 w-28 mb-3" />
        <div className="rounded-xl border bg-card p-6">
          <Skeleton className="h-4 w-48" />
        </div>
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Workspace state
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null)
  const [workspaceName, setWorkspaceName] = useState('')
  const [originalName, setOriginalName] = useState('')
  const [isSavingName, setIsSavingName] = useState(false)

  // API Keys state
  const [apiKeys, setApiKeys] = useState<ApiKeyResponse[]>([])
  const [newKeyName, setNewKeyName] = useState('')
  const [isCreatingKey, setIsCreatingKey] = useState(false)
  const [createdKey, setCreatedKey] = useState<ApiKeyCreatedResponse | null>(null)
  const [copied, setCopied] = useState(false)
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Team state
  const [members, setMembers] = useState<TeamMember[]>([])

  const fetchData = useCallback(async () => {
    try {
      const [ws, keysResp, membersResp] = await Promise.all([
        getWorkspace(),
        listApiKeys(),
        listTeamMembers(),
      ])
      setWorkspace(ws)
      setWorkspaceName(ws.name)
      setOriginalName(ws.name)
      setApiKeys(keysResp.keys)
      setMembers(membersResp.members)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Cleanup copy timeout on unmount
  useEffect(() => {
    return () => {
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current)
    }
  }, [])

  const handleSaveName = async () => {
    if (!workspaceName.trim() || workspaceName === originalName) return
    setIsSavingName(true)
    try {
      const updated = await updateWorkspaceName(workspaceName.trim())
      setWorkspace(updated)
      setWorkspaceName(updated.name)
      setOriginalName(updated.name)
      toast.success('Workspace name updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update workspace name')
    } finally {
      setIsSavingName(false)
    }
  }

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) return
    setIsCreatingKey(true)
    try {
      const created = await createApiKey(newKeyName.trim())
      setCreatedKey(created)
      setNewKeyName('')
      // Refresh key list
      const keysResp = await listApiKeys()
      setApiKeys(keysResp.keys)
      toast.success('API key created')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create API key')
    } finally {
      setIsCreatingKey(false)
    }
  }

  const handleCopyKey = async () => {
    if (!createdKey) return
    await navigator.clipboard.writeText(createdKey.key)
    setCopied(true)
    if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current)
    copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000)
  }

  const handleRevokeKey = async (keyId: string) => {
    try {
      await revokeApiKey(keyId)
      const keysResp = await listApiKeys()
      setApiKeys(keysResp.keys)
      toast.success('API key revoked')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to revoke API key')
    }
  }

  const handleDismissCreatedKey = () => {
    setCreatedKey(null)
    setCopied(false)
  }

  if (isLoading) {
    return <SettingsSkeleton />
  }

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

  const nameChanged = workspaceName.trim() !== originalName && workspaceName.trim().length > 0

  return (
    <div className="space-y-6 animate-fade-in-up">
      <h2 className="text-2xl font-semibold tracking-[-0.03em] text-foreground">Settings</h2>

      {/* Section 1: General */}
      <div>
        <h3 className="section-label mb-3">General</h3>
        <div className="rounded-xl border bg-card p-6">
          <div className="flex flex-col gap-3 max-w-sm">
            <Label htmlFor="workspace-name">Workspace name</Label>
            <div className="flex gap-2">
              <Input
                id="workspace-name"
                value={workspaceName}
                onChange={(e) => setWorkspaceName(e.target.value)}
                placeholder="My workspace"
              />
              <Button
                onClick={handleSaveName}
                disabled={!nameChanged || isSavingName}
              >
                {isSavingName && <Loader2 className="h-4 w-4 animate-spin" />}
                Save
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Section 2: API Keys */}
      <div>
        <h3 className="section-label mb-3">API Keys</h3>
        <div className="space-y-3">
          {/* Create key form */}
          <div className="flex gap-2">
            <Input
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="e.g. MCP Server, CI Pipeline"
              className="max-w-sm"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && newKeyName.trim() && !isCreatingKey) {
                  handleCreateKey()
                }
              }}
            />
            <Button
              onClick={handleCreateKey}
              disabled={!newKeyName.trim() || isCreatingKey}
            >
              {isCreatingKey && <Loader2 className="h-4 w-4 animate-spin" />}
              Create key
            </Button>
          </div>

          {/* Newly created key display */}
          {createdKey && (
            <div className="rounded-lg border border-teal-500/30 bg-teal-500/5 p-4 space-y-3">
              <div className="flex items-start gap-2">
                <Key className="h-4 w-4 mt-0.5 text-teal-500 shrink-0" />
                <p className="font-mono text-sm break-all flex-1">{createdKey.key}</p>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={handleCopyKey}
                  className="shrink-0"
                >
                  {copied ? (
                    <Check className="h-3.5 w-3.5 text-teal-500" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Make sure to copy your API key now. You won&apos;t be able to see it again.
              </p>
              <Button variant="outline" size="sm" onClick={handleDismissCreatedKey}>
                Done
              </Button>
            </div>
          )}

          {/* Key list */}
          {apiKeys.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">
              No API keys yet. Create one to get started.
            </p>
          ) : (
            <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
              {apiKeys.map((apiKey) => (
                <div
                  key={apiKey.id}
                  className="flex items-center gap-3 px-4 py-3"
                >
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
                          onClick={() => handleRevokeKey(apiKey.id)}
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
      </div>

      {/* Section 3: Team */}
      <div>
        <h3 className="section-label mb-3">
          Team{' '}
          <span className="text-muted-foreground">
            &middot; {members.length} member{members.length !== 1 ? 's' : ''}
          </span>
        </h3>
        <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
          {members.map((member) => {
            const displayName = member.full_name || member.email
            const initials = getInitials(displayName)
            return (
              <div
                key={member.user_id}
                className="flex items-center gap-3 px-4 py-3"
              >
                <div className="w-8 h-8 rounded-full bg-elevated flex items-center justify-center text-xs font-medium shrink-0">
                  {initials}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium truncate">
                    {member.full_name || member.email}
                  </p>
                  {member.full_name && (
                    <p className="text-xs text-muted-foreground truncate">
                      {member.email}
                    </p>
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

      {/* Section 4: Integrations */}
      <div>
        <h3 className="section-label mb-3">Integrations</h3>
        <div className="rounded-xl border bg-card p-6">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Manage your connected services
            </p>
            <Button variant="outline" size="sm" asChild>
              <Link href="/dashboard/integrations">
                <ExternalLink className="h-3.5 w-3.5" />
                Integrations
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
