'use client'

import { useEffect, useState } from 'react'
import { Dialog as DialogPrimitive } from 'radix-ui'
import { X } from 'lucide-react'
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

const STATUS_STYLES: Record<string, string> = {
  connected: 'text-[#6d8c6d]',
  disconnected: 'text-[#6e6b66]',
  error: 'text-[#c4a050]',
  unknown: 'text-[#6e6b66]',
}

export function IntegrationDrawer({ open, onOpenChange, workspaceId }: IntegrationDrawerProps) {
  const [statuses, setStatuses] = useState<IntegrationStatusResponse | null>(null)
  const connectedCount = statuses
    ? PROVIDER_LABELS.filter((provider) => statuses[provider]?.status === 'connected').length
    : null

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
          className="fixed right-0 top-0 z-50 h-full w-[420px] max-w-[calc(100vw-16px)] border-l border-white/[0.06] bg-[#0f0e0d] p-6 text-[#ece9e3] shadow-none outline-none"
          aria-describedby="integration-drawer-description"
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <DialogPrimitive.Title className="font-serif text-2xl leading-none text-[#ece9e3]">
                Source status
              </DialogPrimitive.Title>
              <DialogPrimitive.Description
                id="integration-drawer-description"
                className="mt-3 text-sm text-[#a8a59f]"
              >
                {connectedCount == null
                  ? 'Checking connected sources'
                  : `${connectedCount} connected · ${PROVIDER_LABELS.length} sources`}
              </DialogPrimitive.Description>
            </div>
            <DialogPrimitive.Close asChild>
              <button
                type="button"
                aria-label="Close source status"
                className="flex h-8 w-8 items-center justify-center rounded-md text-[#6e6b66] transition-colors duration-[160ms] hover:bg-white/[0.04] hover:text-[#ece9e3]"
              >
                <X className="h-4 w-4" />
              </button>
            </DialogPrimitive.Close>
          </div>

          <button
            type="button"
            className="mt-7 h-9 rounded-md bg-white/10 px-3 text-sm text-[#ece9e3] transition-colors duration-[160ms] hover:bg-white/[0.14]"
            onClick={() => toast.message('Sync controls stay per-source for now')}
          >
            Sync all
          </button>

          <div className="mt-6 overflow-hidden rounded-lg bg-white/[0.025]">
            {PROVIDER_LABELS.map((provider) => {
              const status = statuses?.[provider]
              const statusLabel = status?.status ?? 'unknown'
              return (
                <div
                  key={provider}
                  className="flex min-h-12 items-center justify-between border-b border-white/[0.045] px-4 py-3 text-sm last:border-b-0"
                >
                  <span className="min-w-0">
                    <span className="block lowercase text-[#ece9e3]">{provider}</span>
                    {status?.external_name && (
                      <span className="mt-0.5 block truncate text-xs text-[#6e6b66]">
                        {status.external_name}
                      </span>
                    )}
                  </span>
                  <span className={`text-xs ${STATUS_STYLES[statusLabel] ?? STATUS_STYLES.unknown}`}>
                    {statusLabel}
                  </span>
                </div>
              )
            })}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}
