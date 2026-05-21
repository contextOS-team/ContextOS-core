'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Lock, Globe, RefreshCw, Search, Database, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  getGithubRepos,
  refreshGithubRepos,
  saveGithubRepoSelection,
  triggerGithubIndex,
  getGithubIndexStatus,
  type GithubRepo,
  type GithubIndexStatus,
} from '@/lib/api'

interface GithubReposProps {
  onSaved?: () => void
}

export function GithubRepos({ onSaved }: GithubReposProps) {
  const [repos, setRepos] = useState<GithubRepo[]>([])
  const [selectedNames, setSelectedNames] = useState<Set<string>>(new Set())
  const [savedNames, setSavedNames] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [indexStatus, setIndexStatus] = useState<GithubIndexStatus | null>(null)
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
    (data: { repos: GithubRepo[]; selected_repos: string[] }) => {
      setRepos(data.repos || [])
      const selected = new Set(data.selected_repos || [])
      setSelectedNames(selected)
      setSavedNames(selected)
    },
    []
  )

  const fetchRepos = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getGithubRepos()
      // Auto-fetch from GitHub if cache is empty
      if ((!data.repos || data.repos.length === 0) && mountedRef.current) {
        setIsRefreshing(true)
        try {
          const fresh = await refreshGithubRepos()
          applyReposResponse(fresh)
        } catch {
          // Fall back to empty — user can manually refresh
          applyReposResponse(data)
        } finally {
          setIsRefreshing(false)
        }
      } else {
        applyReposResponse(data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load repos')
    } finally {
      setIsLoading(false)
    }
  }, [applyReposResponse])

  const pollIndexStatus = useCallback(async () => {
    if (!mountedRef.current) return
    try {
      const status = await getGithubIndexStatus()
      if (!mountedRef.current) return
      setIndexStatus(status)
      if (status.status === 'indexing') {
        indexPollRef.current = setTimeout(pollIndexStatus, 3000)
      }
    } catch {
      // Silently ignore — status is optional
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
      const data = await refreshGithubRepos()
      applyReposResponse(data)
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to refresh repos'
      )
    } finally {
      setIsRefreshing(false)
    }
  }

  async function handleSave() {
    setIsSaving(true)
    setError(null)
    try {
      const result = await saveGithubRepoSelection(Array.from(selectedNames))
      const saved = new Set(result.selected_repos || [])
      setSavedNames(saved)
      setSelectedNames(saved)
      onSaved?.()

      // Auto-trigger indexing after save
      if (saved.size > 0) {
        try {
          await triggerGithubIndex()
          setIndexStatus((prev) => prev ? { ...prev, status: 'indexing' } : { status: 'indexing', last_indexed_at: null, repos: [] })
          // Start polling for progress
          if (indexPollRef.current) clearTimeout(indexPollRef.current)
          indexPollRef.current = setTimeout(pollIndexStatus, 3000)
        } catch {
          // Indexing trigger failed — not critical, selection was saved
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

  function toggleRepo(fullName: string) {
    setSelectedNames((prev) => {
      const next = new Set(prev)
      if (next.has(fullName)) {
        next.delete(fullName)
      } else {
        next.add(fullName)
      }
      return next
    })
  }

  function toggleAll() {
    if (selectedNames.size === filteredRepos.length) {
      setSelectedNames(new Set())
    } else {
      setSelectedNames(new Set(filteredRepos.map((r) => r.full_name)))
    }
  }

  const filteredRepos = repos.filter((repo) =>
    repo.full_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  // Check if selection has changed from saved state
  const hasChanges =
    selectedNames.size !== savedNames.size ||
    [...selectedNames].some((n) => !savedNames.has(n))

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        {isRefreshing ? 'Fetching repos from GitHub...' : 'Loading repos...'}
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
          {savedNames.size} of {repos.length} repos selected
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
      {savedNames.size > 0 && indexStatus && (
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
              <span>Indexing repos...</span>
            </>
          ) : (
            <>
              <Database className="h-3 w-3 shrink-0" />
              <span>
                {totalChunks > 0
                  ? `${totalChunks.toLocaleString()} code symbols indexed across ${indexedRepoCount} repo${indexedRepoCount !== 1 ? 's' : ''}`
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
            placeholder="Filter repos..."
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
        Selected repos are cloned and indexed for code context in AI-generated pages.
      </p>

      {/* Repo list */}
      <div className="dashboard-list-panel max-h-[320px] space-y-0.5">
        {filteredRepos.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            {searchQuery ? 'No repos match your search' : 'No repos found'}
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
                    selectedNames.size === filteredRepos.length
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
                key={repo.full_name}
                className="dashboard-list-row flex cursor-pointer items-center gap-3 px-3 py-2"
              >
                <input
                  type="checkbox"
                  checked={selectedNames.has(repo.full_name)}
                  onChange={() => toggleRepo(repo.full_name)}
                  className="h-3.5 w-3.5 rounded border-gray-300 text-primary accent-primary"
                />
                <span className="flex items-center gap-1.5 text-xs">
                  {repo.private ? (
                    <Lock className="h-3 w-3 text-muted-foreground" />
                  ) : (
                    <Globe className="h-3 w-3 text-muted-foreground" />
                  )}
                  <span className="font-medium">{repo.full_name}</span>
                </span>
                {repo.language && (
                  <span className="ml-auto text-xs text-muted-foreground">
                    {repo.language}
                  </span>
                )}
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
        {!hasChanges && savedNames.size > 0 && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Check className="h-3 w-3" />
            Saved
          </span>
        )}
      </div>
    </div>
  )
}
