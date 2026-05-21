'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Lock, Globe, RefreshCw, Search, Database, Check, GitMerge } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  getGitlabRepos,
  refreshGitlabRepos,
  selectGitlabRepos,
  triggerGitlabIndex,
  getGitlabIndexStatus,
  triggerGitlabSync,
  getGitlabSyncStatus,
  type GitlabProject,
  type GitlabIndexStatus,
  type GitlabSyncStatus,
} from '@/lib/api'

interface GitlabReposProps {
  onSaved?: () => void
}

export function GitlabRepos({ onSaved }: GitlabReposProps) {
  const [repos, setRepos] = useState<GitlabProject[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [savedIds, setSavedIds] = useState<Set<number>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [indexStatus, setIndexStatus] = useState<GitlabIndexStatus | null>(null)
  const [syncStatus, setSyncStatus] = useState<GitlabSyncStatus | null>(null)
  const [isSyncing, setIsSyncing] = useState(false)
  const indexPollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const syncPollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (indexPollRef.current) clearTimeout(indexPollRef.current)
      if (syncPollRef.current) clearTimeout(syncPollRef.current)
    }
  }, [])

  const applyReposResponse = useCallback(
    (data: { repos: GitlabProject[]; selected_projects: number[] }) => {
      setRepos(data.repos || [])
      const selected = new Set(data.selected_projects || [])
      setSelectedIds(selected)
      setSavedIds(selected)
    },
    []
  )

  const fetchRepos = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getGitlabRepos()
      // Auto-fetch from GitLab if cache is empty
      if ((!data.repos || data.repos.length === 0) && mountedRef.current) {
        setIsRefreshing(true)
        try {
          const fresh = await refreshGitlabRepos()
          applyReposResponse(fresh)
        } catch {
          // Fall back to empty -- user can manually refresh
          applyReposResponse(data)
        } finally {
          setIsRefreshing(false)
        }
      } else {
        applyReposResponse(data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load projects')
    } finally {
      setIsLoading(false)
    }
  }, [applyReposResponse])

  const pollIndexStatus = useCallback(async () => {
    if (!mountedRef.current) return
    try {
      const status = await getGitlabIndexStatus()
      if (!mountedRef.current) return
      setIndexStatus(status)
      if (status.status === 'indexing') {
        indexPollRef.current = setTimeout(pollIndexStatus, 3000)
      }
    } catch {
      // Silently ignore -- status is optional
    }
  }, [])

  const pollSyncStatus = useCallback(async () => {
    if (!mountedRef.current) return
    try {
      const status = await getGitlabSyncStatus()
      if (!mountedRef.current) return
      setSyncStatus(status)
      if (status.is_syncing) {
        setIsSyncing(true)
        syncPollRef.current = setTimeout(pollSyncStatus, 3000)
      } else {
        setIsSyncing(false)
      }
    } catch {
      // Silently ignore
    }
  }, [])

  useEffect(() => {
    fetchRepos()
    pollIndexStatus()
    pollSyncStatus()
  }, [fetchRepos, pollIndexStatus, pollSyncStatus])

  async function handleRefresh() {
    setIsRefreshing(true)
    setError(null)
    try {
      const data = await refreshGitlabRepos()
      applyReposResponse(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to refresh projects'
      )
    } finally {
      setIsRefreshing(false)
    }
  }

  /** Trigger indexing and start polling. Returns true on success. */
  async function startIndexing(): Promise<boolean> {
    try {
      await triggerGitlabIndex()
      setIndexStatus((prev) => prev
        ? { ...prev, status: 'indexing', progress: 0, total: null, current_repo: null }
        : { status: 'indexing', last_indexed_at: null, repos: [], progress: 0, total: null, current_repo: null })
      if (indexPollRef.current) clearTimeout(indexPollRef.current)
      indexPollRef.current = setTimeout(pollIndexStatus, 3000)
      return true
    } catch {
      return false
    }
  }

  async function handleSave() {
    setIsSaving(true)
    setError(null)
    try {
      const result = await selectGitlabRepos(Array.from(selectedIds))
      const saved = new Set(result.selected_projects || [])
      setSavedIds(saved)
      setSelectedIds(saved)
      onSaved?.()

      // Auto-trigger indexing and MR sync after save
      if (saved.size > 0) {
        await startIndexing()
        // MR sync is auto-triggered by backend on repo selection
        // Start polling for sync status
        setIsSyncing(true)
        if (syncPollRef.current) clearTimeout(syncPollRef.current)
        syncPollRef.current = setTimeout(pollSyncStatus, 3000)
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to save selection'
      )
    } finally {
      setIsSaving(false)
    }
  }

  async function handleReindex() {
    setError(null)
    const ok = await startIndexing()
    if (!ok) {
      setError('Failed to start code indexing. Try again.')
    }
  }

  function toggleProject(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  function toggleAll() {
    if (selectedIds.size === filteredRepos.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredRepos.map((r) => r.id)))
    }
  }

  const filteredRepos = repos.filter((repo) =>
    repo.path_with_namespace.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // Check if selection has changed from saved state
  const hasChanges =
    selectedIds.size !== savedIds.size ||
    [...selectedIds].some((id) => !savedIds.has(id))

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        {isRefreshing ? 'Fetching projects from GitLab...' : 'Loading projects...'}
      </div>
    )
  }

  // Build index status summary
  const isIndexing = indexStatus?.status === 'indexing'
  const totalChunks = indexStatus?.repos?.reduce((sum, r) => sum + r.chunks, 0) ?? 0
  const indexedRepoCount = indexStatus?.repos?.length ?? 0

  // Build MR sync status summary
  const totalMRsSynced = syncStatus?.total_mrs ?? 0

  async function handleResync() {
    setIsSyncing(true)
    try {
      await triggerGitlabSync()
      if (syncPollRef.current) clearTimeout(syncPollRef.current)
      syncPollRef.current = setTimeout(pollSyncStatus, 3000)
    } catch {
      setIsSyncing(false)
    }
  }

  return (
    <div className="space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground">
          {savedIds.size} of {repos.length} projects selected
        </p>
        <Button
          variant="ghost"
          size="xs"
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="text-muted-foreground"
        >
          <RefreshCw
            className={`mr-1 h-3 w-3 ${isRefreshing ? 'animate-spin' : ''}`}
          />
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </Button>
      </div>

      {/* Indexing status */}
      {savedIds.size > 0 && indexStatus && (
        <div
          className={`rounded-md px-3 py-2 text-xs ${
            isIndexing
              ? 'bg-primary/10 text-primary'
              : 'bg-muted/50 text-muted-foreground'
          }`}
        >
          {isIndexing ? (
            (() => {
              const progress = indexStatus.progress ?? 0
              const hasTotal = indexStatus.total != null && indexStatus.total > 0
              const percent = hasTotal ? Math.round((progress / indexStatus.total!) * 100) : 0
              // Show last 2 segments for nested namespaces (e.g. "client-app/ios" from "hivetaxi/client-app/ios")
              const shortRepo = indexStatus.current_repo
                ? indexStatus.current_repo.split('/').slice(-2).join('/')
                : null
              return (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <RefreshCw className="h-3 w-3 animate-spin shrink-0" />
                      <span>
                        {shortRepo
                          ? `Indexing ${shortRepo}...`
                          : 'Indexing projects...'}
                      </span>
                    </div>
                    {hasTotal && (
                      <span className="font-mono text-[11px] opacity-70">
                        {progress}/{indexStatus.total} projects
                      </span>
                    )}
                  </div>
                  {hasTotal && (
                    <div
                      className="h-1.5 w-full rounded-full bg-primary/20 overflow-hidden"
                      role="progressbar"
                      aria-valuenow={percent}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label="GitLab indexing progress"
                    >
                      <div
                        className="h-full rounded-full bg-primary transition-[width] duration-700 ease-out relative overflow-hidden"
                        style={{ width: `${Math.max(percent, 2)}%` }}
                      >
                        <div className="absolute inset-0 animate-[sync-shimmer_1.5s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-white/40 to-transparent" />
                      </div>
                    </div>
                  )}
                </div>
              )
            })()
          ) : (
            <div className="flex items-center gap-2">
              <Database className="h-3 w-3 shrink-0" />
              <span className="flex-1">
                {totalChunks > 0
                  ? `${totalChunks.toLocaleString()} code symbols indexed across ${indexedRepoCount} of ${savedIds.size} project${savedIds.size !== 1 ? 's' : ''}`
                  : 'No code indexed yet'}
              </span>
              <button
                onClick={handleReindex}
                className="ml-auto flex items-center gap-1 text-[11px] text-primary hover:text-primary/80 transition-colors shrink-0"
              >
                <RefreshCw className="h-2.5 w-2.5" />
                Re-index
              </button>
              {indexStatus.last_indexed_at && (
                <span className="text-[10px] opacity-60">
                  {new Date(indexStatus.last_indexed_at).toLocaleDateString()}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {/* MR sync status */}
      {savedIds.size > 0 && (
        <div
          className={`rounded-md px-3 py-2 text-xs ${
            isSyncing
              ? 'bg-primary/10 text-primary'
              : 'bg-muted/50 text-muted-foreground'
          }`}
        >
          {isSyncing ? (
            <div className="flex items-center gap-2">
              <RefreshCw className="h-3 w-3 animate-spin shrink-0" />
              <span>Syncing merge requests...</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <GitMerge className="h-3 w-3 shrink-0" />
              <span className="flex-1">
                {totalMRsSynced > 0
                  ? `${totalMRsSynced.toLocaleString()} merge requests synced`
                  : 'No merge requests synced yet'}
              </span>
              <button
                onClick={handleResync}
                className="ml-auto flex items-center gap-1 text-[11px] text-primary hover:text-primary/80 transition-colors shrink-0"
              >
                <RefreshCw className="h-2.5 w-2.5" />
                Re-sync
              </button>
            </div>
          )}
        </div>
      )}

      {/* Search */}
      {repos.length > 5 && (
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter projects..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="dashboard-input h-8 pl-8 text-xs"
          />
        </div>
      )}

      {/* Error */}
      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      {/* Helper text */}
      <p className="text-[11px] text-muted-foreground/70">
        Selected projects are cloned and indexed for code context in AI-generated pages.
      </p>

      {/* Project list */}
      <div className="dashboard-list-panel max-h-[320px] space-y-0.5">
        {filteredRepos.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            {searchQuery ? 'No projects match your search' : 'No projects found'}
          </p>
        ) : (
          <>
            {/* Select all row */}
            {filteredRepos.length > 2 && (
              <label className="dashboard-list-row dashboard-list-row--bordered flex cursor-pointer items-center gap-3 px-3 py-2">
                <input
                  type="checkbox"
                  checked={
                    filteredRepos.length > 0 &&
                    selectedIds.size === filteredRepos.length
                  }
                  onChange={toggleAll}
                  className="h-3.5 w-3.5 rounded border-gray-300 text-primary accent-primary"
                />
                <span className="text-xs font-medium text-muted-foreground">
                  Select all
                </span>
              </label>
            )}

            {filteredRepos.map((repo) => (
              <label
                key={repo.id}
                className="dashboard-list-row flex cursor-pointer items-center gap-3 px-3 py-2"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(repo.id)}
                  onChange={() => toggleProject(repo.id)}
                  className="h-3.5 w-3.5 rounded border-gray-300 text-primary accent-primary"
                />
                <span className="flex items-center gap-1.5 text-xs">
                  {repo.visibility === 'private' ? (
                    <Lock className="h-3 w-3 text-muted-foreground" />
                  ) : repo.visibility === 'internal' ? (
                    <Lock className="h-3 w-3 text-muted-foreground/60" />
                  ) : (
                    <Globe className="h-3 w-3 text-muted-foreground" />
                  )}
                  <span className="font-medium">{repo.path_with_namespace}</span>
                </span>
              </label>
            ))}
          </>
        )}
      </div>

      {/* Save button */}
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
            'Save selection'
          )}
        </Button>
        {!hasChanges && savedIds.size > 0 && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Check className="h-3 w-3" />
            Saved
          </span>
        )}
      </div>
    </div>
  )
}
