'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Lock, RefreshCw, Search, Hash } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  getSlackChannels,
  refreshSlackChannels,
  saveSlackChannelSelection,
  type SlackChannel,
} from '@/lib/api'

interface SlackChannelsProps {
  /** Callback after selection is saved, so parent can refresh status. */
  onSaved?: () => void
}

export function SlackChannels({ onSaved }: SlackChannelsProps) {
  const [channels, setChannels] = useState<SlackChannel[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [searchQuery, setSearchQuery] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const successTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchChannels = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getSlackChannels()
      setChannels(data.channels || [])
      if (data.selected_channels) {
        setSelectedIds(new Set(data.selected_channels))
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load channels')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchChannels()
  }, [fetchChannels])

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
      const data = await refreshSlackChannels()
      setChannels(data.channels || [])
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to refresh channels'
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
      await saveSlackChannelSelection(Array.from(selectedIds))
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

  function toggleChannel(channelId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(channelId)) {
        next.delete(channelId)
      } else {
        next.add(channelId)
      }
      return next
    })
    setSaveSuccess(false)
  }

  function toggleAll() {
    if (selectedIds.size === filteredChannels.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(filteredChannels.map((c) => c.id)))
    }
    setSaveSuccess(false)
  }

  const filteredChannels = channels.filter((ch) =>
    ch.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        Loading channels...
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground">
          {selectedIds.size} of {channels.length} channels selected
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
          placeholder="Filter channels..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="dashboard-input h-8 pl-8 text-xs"
        />
      </div>

      {/* Error */}
      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      {/* Channel list */}
      <div className="dashboard-list-panel max-h-[320px] space-y-0.5">
        {filteredChannels.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            {searchQuery ? 'No channels match your search' : 'No channels found'}
          </p>
        ) : (
          <>
            {/* Select all row */}
            <label className="dashboard-list-row dashboard-list-row--bordered flex cursor-pointer items-center gap-3 px-3 py-2">
              <input
                type="checkbox"
                checked={
                  filteredChannels.length > 0 &&
                  selectedIds.size === filteredChannels.length
                }
                onChange={toggleAll}
                className="h-3.5 w-3.5 rounded border-gray-300 text-primary accent-primary"
              />
              <span className="text-xs font-medium text-muted-foreground">
                Select all
              </span>
            </label>

            {filteredChannels.map((channel) => (
              <label
                key={channel.id}
                className="dashboard-list-row flex cursor-pointer items-center gap-3 px-3 py-2"
              >
                <input
                  type="checkbox"
                  checked={selectedIds.has(channel.id)}
                  onChange={() => toggleChannel(channel.id)}
                  className="h-3.5 w-3.5 rounded border-gray-300 text-primary accent-primary"
                />
                <span className="flex items-center gap-1 text-xs">
                  {channel.is_private ? (
                    <Lock className="h-3 w-3 text-muted-foreground" />
                  ) : (
                    <Hash className="h-3 w-3 text-muted-foreground" />
                  )}
                  <span className="font-medium">{channel.name}</span>
                </span>
                <span className="ml-auto text-xs text-muted-foreground">
                  {channel.num_members} members
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
          disabled={isSaving || selectedIds.size === 0}
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
