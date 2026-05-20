'use client'

import { useEffect, useState } from 'react'
import { Dialog as DialogPrimitive } from 'radix-ui'
import { toast } from 'sonner'
import { getIntegrationStatus, type IntegrationStatusResponse } from '@/lib/api'

interface IntegrationDrawerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  workspaceId: string | null
}

const PROVIDER_LABELS: Array<keyof IntegrationStatusResponse> = [
  'linear',
  'slack',
  'github',
  'gitlab',
  'notion',
  'telegram',
  'jira',
  'fathom',
]

export function IntegrationDrawer({ open, onOpenChange, workspaceId }: IntegrationDrawerProps) {
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(null)

  useEffect(() => {
    if (!open || !workspaceId) return

    let cancelled = false

    getIntegrationStatus()
      .then((data) => {
        if (!cancelled) setStatuses(data)
      })
      .catch(() => {
        if (!cancelled) setStatuses(null)
      })

    return () => {
      cancelled = true
    }
  }, [open, workspaceId])

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content
          className="fixed right-0 top-0 z-50 h-full w-[360px] border-l border-white/5 bg-[#13110f] p-6 text-[#ece9e3] shadow-none outline-none"
          aria-describedby="integration-drawer-description"
        >
          <DialogPrimitive.Title className="font-serif text-xl text-[#ece9e3]">
            Integrations
          </DialogPrimitive.Title>
          <p id="integration-drawer-description" className="mt-2 text-sm text-[#a8a59f]">
            Per-provider detail coming soon.
          </p>

          <button
            type="button"
            className="mt-6 h-9 rounded-md bg-white/10 px-3 text-sm text-[#ece9e3] transition-colors duration-[160ms] hover:bg-white/[0.14]"
            onClick={() => toast.message('Manual sync queued')}
          >
            Sync all
          </button>

          <div className="mt-6 space-y-3">
            {PROVIDER_LABELS.map((provider) => {
              const status = statuses?.[provider]
              return (
                <div
                  key={provider}
                  className="flex items-center justify-between rounded-md bg-white/[0.025] px-3 py-2 text-sm"
                >
                  <span className="lowercase text-[#ece9e3]">{provider}</span>
                  <span className="text-xs text-[#6e6b66]">{status?.status ?? 'unknown'}</span>
                </div>
              )
            })}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
