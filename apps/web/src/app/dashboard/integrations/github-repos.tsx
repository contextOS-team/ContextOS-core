'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Lock, Globe, RefreshCw, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  getGithubRepos,
  refreshGithubRepos,
  saveGithubRepoSelection,
  type GithubRepo,
} from '@/lib/api'

interface GithubReposProps {
  /** Callback after selection is saved, so parent can refresh status. */
  onSaved?: () => void
}

export function GithubRepos({ onSaved }: GithubReposProps) {
  const [repos, setRepos] = useState<GithubRepo[]>([])
  const [selectedNames, setSelectedNames] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const successTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchRepos = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getGithubRepos()
      setRepos(data.repos || [])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load repos')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchRepos()
  }, [fetchRepos])

  useEffect(() => {
    return () => {
      if (successTimeoutRef.current) {
        clearTimeout(successTimeoutRef.current)
      }
    }
  }, [])

  async function handleRefresh() {
    setIsRefreshing(true)
    setError(null)
    try {
      const data = await refreshGithubRepos()
      setRepos(data.repos || [])
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
    setSaveSuccess(false)
    setError(null)
    try {
      await saveGithubRepoSelection(Array.from(selectedNames))
      setSaveSuccess(true)
      onSaved?.()
      // Clear success message after 3 seconds
      successTimeoutRef.current = setTimeout(() => setSaveSuccess(false), 3000)
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
    setSaveSuccess(false)
  }

  function toggleAll() {
    if (selectedNames.size === filteredRepos.length) {
      setSelectedNames(new Set())
    } else {
      setSelectedNames(new Set(filteredRepos.map((r) => r.full_name)))
    }
    setSaveSuccess(false)
  }

  const filteredRepos = repos.filter((repo) =>
    repo.full_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        Loading repos...
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground">
          {selectedNames.size} of {repos.length} repos selected
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

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Filter repos..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="h-8 pl-8 text-xs"
        />
      </div>

      {/* Error */}
      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      {/* Repo list */}
      <div className="max-h-[320px] space-y-0.5 overflow-y-auto rounded-md border bg-background">
        {filteredRepos.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            {searchQuery ? 'No repos match your search' : 'No repos found'}
          </p>
        ) : (
          <>
            {/* Select all row */}
            <label className="flex cursor-pointer items-center gap-3 border-b px-3 py-2 hover:bg-muted/50">
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

            {filteredRepos.map((repo) => (
              <label
                key={repo.full_name}
                className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-muted/50"
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
          disabled={isSaving || selectedNames.size === 0}
        >
          {isSaving ? 'Saving...' : 'Save selection'}
        </Button>
        {saveSuccess && (
          <span className="text-xs text-emerald-600">Saved successfully</span>
        )}
      </div>
    </div>
  )
}
