'use client'

import Link from 'next/link'
import { ArrowRight, Zap, Layers } from 'lucide-react'
import type { IntegrationStatusResponse } from '@/lib/api'

interface EmptyStateProps {
  statuses: IntegrationStatusResponse | null
}

export function EmptyState({ statuses }: EmptyStateProps) {
  const connected = statuses
    ? Object.entries(statuses).filter(([, v]) => v?.status === 'connected')
    : []

  const hasConnections = connected.length > 0

  return (
    <div className="space-y-6">
      {/* Primary CTA — same inline style as smart status banner, not a different card system */}
      <Link
        href={hasConnections ? '/dashboard/context/generate' : '/dashboard/settings'}
        className="group flex items-center gap-3 px-4 py-2.5 rounded-xl border border-primary/20 transition-colors hover:border-primary/40"
      >
        {hasConnections ? (
          <Zap className="h-3.5 w-3.5 shrink-0 text-primary" />
        ) : (
          <Layers className="h-3.5 w-3.5 shrink-0 text-primary" />
        )}
        <p className="text-xs text-muted-foreground flex-1">
          {hasConnections
            ? 'Generate your first context to see your dashboard come alive'
            : 'Connect your tools to get started'}
        </p>
        <ArrowRight className="h-3 w-3 text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-foreground" />
      </Link>

      {/* Ghost preview — matches real component shapes */}
      <div>
        <h3 className="section-label mb-3">Recent Context</h3>
        <div className="rounded-xl border border-dashed border-border/60 bg-card/30 overflow-hidden divide-y divide-border/30">
          {/* Ghost rows that match ContextRow shape: left border, title, metadata line */}
          <GhostContextRow title="Your context pages will appear here" sub="ticket · time · sources" />
          <GhostContextRow title="Each row shows a generated context page" sub="ticket · time · sources" />
        </div>
      </div>

    </div>
  )
}

function GhostContextRow({ title, sub }: { title: string; sub: string }) {
  return (
    <div className="w-full text-left px-4 py-3 border-l-[3px] border-l-transparent opacity-40">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm text-muted-foreground/70">{title}</span>
        <span className="shrink-0 h-2 w-2 rounded-full bg-muted-foreground/20" />
      </div>
      <div className="flex items-center gap-2 mt-0.5">
        <span className="text-xs text-muted-foreground/40">{sub}</span>
      </div>
    </div>
  )
}
