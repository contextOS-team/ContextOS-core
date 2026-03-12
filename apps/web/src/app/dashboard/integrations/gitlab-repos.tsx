'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Lock, Globe, RefreshCw, Search, Database, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  getGitlabRepos,
  refreshGitlabRepos,
  selectGitlabRepos,
  triggerGitlabIndex,
  getGitlabIndexStatus,
  type GitlabProject,
  type GitlabIndexStatus,
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
  const indexPollRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (indexPollRef.current) clearTimeout(indexPollRef.current)
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

  useEffect(() => {
    fetchRepos()
    pollIndexStatus()
  }, [fetchRepos, pollIndexStatus])

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

  async function handleSave() {
    setIsSaving(true)
    setError(null)
    try {
      const result = await selectGitlabRepos(Array.from(selectedIds))
      const saved = new Set(result.selected_projects || [])
      setSavedIds(saved)
      setSelectedIds(saved)
      onSaved?.()

      // Auto-trigger indexing after save
      if (saved.size > 0) {
        try {
          await triggerGitlabIndex()
          setIndexStatus((prev) => prev ? { ...prev, status: 'indexing' } : { status: 'indexing', last_indexed_at: null, repos: [] })
          // Start polling for progress
          if (indexPollRef.current) clearTimeout(indexPollRef.current)
          indexPollRef.current = setTimeout(pollIndexStatus, 3000)
        } catch {
          // Indexing trigger failed -- not critical, selection was saved
        }
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to save selection'
      )
    } finally {
      setIsSaving(false)
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
          className={`flex items-center gap-2 rounded-md px-3 py-2 text-xs ${
            isIndexing
              ? 'bg-primary/10 text-primary'
              : 'bg-muted/50 text-muted-foreground'
          }`}
        >
          {isIndexing ? (
            <>
              <RefreshCw className="h-3 w-3 animate-spin shrink-0" />
              <span>Indexing projects...</span>
            </>
          ) : (
            <>
              <Database className="h-3 w-3 shrink-0" />
              <span>
                {totalChunks > 0
                  ? `${totalChunks.toLocaleString()} code symbols indexed across ${indexedRepoCount} project${indexedRepoCount !== 1 ? 's' : ''}`
                  : 'No code indexed yet'}
              </span>
              {indexStatus.last_indexed_at && (
                <span className="ml-auto text-[10px] opacity-60">
                  Last indexed {new Date(indexStatus.last_indexed_at).toLocaleDateString()}
                </span>
              )}
            </>
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
            className="h-8 pl-8 text-xs"
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
      <div className="max-h-[320px] space-y-0.5 overflow-y-auto rounded-md border bg-background">
        {filteredRepos.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            {searchQuery ? 'No projects match your search' : 'No projects found'}
          </p>
        ) : (
          <>
            {/* Select all row */}
            {filteredRepos.length > 2 && (
              <label className="flex cursor-pointer items-center gap-3 border-b px-3 py-2 hover:bg-muted/50">
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
                className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-muted/50"
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
