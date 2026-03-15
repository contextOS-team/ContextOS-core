'use client'

import Link from 'next/link'
import { ArrowRight, Layers, AlertCircle, CalendarDays, Zap } from 'lucide-react'
import type { IntegrationStatusResponse } from '@/lib/api'

interface EmptyStateProps {
  statuses: IntegrationStatusResponse | null
  firstName: string
}

const PROVIDER_LABELS: Record<string, string> = {
  linear: 'Linear',
  jira: 'Jira',
  github: 'GitHub',
  gitlab: 'GitLab',
  slack: 'Slack',
  telegram: 'Telegram',
  notion: 'Notion',
  fathom: 'Fathom',
}

export function EmptyState({ statuses, firstName }: EmptyStateProps) {
  const connected = statuses
    ? Object.entries(statuses).filter(([, v]) => v?.status === 'connected')
    : []
  const disconnected = statuses
    ? Object.entries(statuses).filter(([, v]) => v?.status !== 'connected')
    : []

  return (
    <div className="space-y-6">
      {/* Welcome message */}
      <div>
        <p className="text-sm text-foreground/60">
          {connected.length > 0
            ? `Your tools are connected. Generate a context page to see your dashboard come alive.`
            : `Connect your work tools to get started.`}
        </p>
      </div>

      {/* Primary CTA */}
      <Link
        href={connected.length > 0 ? '/dashboard/context/generate' : '/dashboard/settings'}
        className="group flex items-center gap-4 rounded-xl border border-primary/20 bg-primary/5 px-5 py-4 transition-all duration-200 hover:border-primary/40 hover:bg-primary/10"
      >
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
          {connected.length > 0 ? <Zap className="h-4 w-4" /> : <Layers className="h-4 w-4" />}
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium text-foreground">
            {connected.length > 0 ? 'Generate your first context' : 'Connect your tools'}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {connected.length > 0
              ? 'Pick a ticket and ContextOS will gather everything related to it'
              : 'Link Linear, GitHub, Slack, and more to start building context'}
          </p>
        </div>
        <ArrowRight className="h-4 w-4 text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-foreground" />
      </Link>

      {/* Preview cards — ghost versions of what the dashboard will show */}
      <div className="space-y-4">
        <GhostCard
          icon={<AlertCircle className="h-3.5 w-3.5" />}
          label="Needs Attention"
          lines={[
            { title: 'Stale contexts and open reviews appear here', sub: 'Updated automatically from your tools' },
          ]}
        />
        <GhostCard
          icon={<CalendarDays className="h-3.5 w-3.5" />}
          label="This Week"
          lines={[
            { title: 'Daily activity summary shows up here', sub: 'Contexts updated, PRs merged, and more' },
          ]}
        />
        <GhostCard
          icon={<Layers className="h-3.5 w-3.5" />}
          label="Recent Context"
          lines={[
            { title: 'Your generated context pages will appear here', sub: 'Quick access to your latest work' },
          ]}
        />
      </div>

      {/* Integration status — actionable */}
      {statuses && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="section-label">Integrations</h3>
            <Link
              href="/dashboard/settings"
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Manage
            </Link>
          </div>
          <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
            {connected.map(([key, status]) => (
              <div key={key} className="flex items-center gap-3 px-4 py-2.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500 shrink-0" />
                <span className="text-sm text-foreground flex-1">
                  {PROVIDER_LABELS[key] ?? key}
                </span>
                {status.last_sync_at && (
                  <span className="text-xs text-muted-foreground">
                    Synced
                  </span>
                )}
              </div>
            ))}
            {disconnected.length > 0 && (
              <Link
                href="/dashboard/settings"
                className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-muted/40"
              >
                <span className="h-2 w-2 rounded-full bg-muted-foreground/20 shrink-0" />
                <span className="text-sm text-muted-foreground flex-1">
                  {disconnected.length} more available
                </span>
                <ArrowRight className="h-3 w-3 text-muted-foreground" />
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function GhostCard({
  icon,
  label,
  lines,
}: {
  icon: React.ReactNode
  label: string
  lines: { title: string; sub: string }[]
}) {
  return (
    <div className="opacity-50">
      <h3 className="section-label mb-3">{label}</h3>
      <div className="rounded-xl border border-dashed border-border bg-card/50 overflow-hidden divide-y divide-border/50">
        {lines.map((line) => (
          <div key={line.title} className="flex items-center gap-3 px-4 py-3">
            <div className="shrink-0 text-muted-foreground/50">{icon}</div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-muted-foreground/70">{line.title}</p>
              <p className="text-xs text-muted-foreground/40 mt-0.5">{line.sub}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
