'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'

import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { getSlackStatus, toggleSlackDms } from '@/lib/api'

interface Props {
  /**
   * Optional — when the parent already has the include_dms value (e.g. from
   * getSlackStatus()), pass it to skip the extra fetch and avoid the mount
   * skeleton. When undefined, the component re-reads status on mount.
   */
  initialIncludeDms?: boolean
}

/**
 * DM ingestion toggle. Re-reads include_dms on mount when initialIncludeDms
 * is undefined so the state survives page reloads. Optimistic updates with
 * rollback on error. Shows a sonner toast on every transition.
 */
export function SlackDmToggle({ initialIncludeDms }: Props) {
  const [enabled, setEnabled] = useState<boolean>(initialIncludeDms ?? false)
  const [loading, setLoading] = useState<boolean>(
    initialIncludeDms === undefined,
  )
  const [pending, setPending] = useState(false)

  useEffect(() => {
    if (initialIncludeDms !== undefined) {
      setEnabled(initialIncludeDms)
      setLoading(false)
      return
    }
    let cancelled = false
    ;(async () => {
      try {
        const s = await getSlackStatus()
        if (!cancelled) setEnabled(!!s.include_dms)
      } catch {
        // Non-blocking — leave default false on failure.
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [initialIncludeDms])

  async function handleChange(next: boolean) {
    const prev = enabled
    setEnabled(next)
    setPending(true)
    try {
      const res = await toggleSlackDms(next)
      setEnabled(res.include_dms)
      toast.success(
        res.include_dms ? 'DM ingestion enabled' : 'DM ingestion disabled',
      )
    } catch (err) {
      setEnabled(prev)
      toast.error(
        err instanceof Error ? err.message : 'Failed to update DM setting',
      )
    } finally {
      setPending(false)
    }
  }

  if (loading) {
    return (
      <div
        className="dashboard-panel h-[72px] w-full animate-pulse"
        aria-hidden="true"
      />
    )
  }

  return (
    <div className="dashboard-panel space-y-1.5 p-3">
      {/*
        The Label's htmlFor wires clicks on the text to the Switch and gives
        the label+switch pair a >=40px hit area (min-h-10). The Switch itself
        stays visually compact (w-9 h-5) per the shadcn default.
      */}
      <Label
        htmlFor="slack-dm-toggle"
        className="flex min-h-10 cursor-pointer items-center justify-between gap-4"
      >
        <span className="flex-1 text-xs font-medium text-foreground">
          Include direct messages
        </span>
        <Switch
          id="slack-dm-toggle"
          checked={enabled}
          onCheckedChange={handleChange}
          disabled={pending}
        />
      </Label>
      <p
        className="text-[11px] text-muted-foreground"
        style={{ textWrap: 'pretty' }}
      >
        DM messages will be indexed for context generation. Only you can see
        this data.
      </p>
    </div>
  )
}
