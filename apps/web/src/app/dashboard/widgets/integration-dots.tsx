import Link from 'next/link'
import { Plus } from 'lucide-react'
import type { IntegrationStatusResponse } from '@/lib/api'

const INTEGRATIONS = [
  { key: 'linear' as const, name: 'Linear', rival: 'jira' as const },
  { key: 'jira' as const, name: 'Jira', rival: 'linear' as const },
  { key: 'github' as const, name: 'GitHub', rival: 'gitlab' as const },
  { key: 'gitlab' as const, name: 'GitLab', rival: 'github' as const },
  { key: 'slack' as const, name: 'Slack', rival: 'telegram' as const },
  { key: 'telegram' as const, name: 'Telegram', rival: 'slack' as const },
  { key: 'notion' as const, name: 'Notion' },
  { key: 'fathom' as const, name: 'Fathom' },
] as const

interface IntegrationDotsProps {
  statuses: IntegrationStatusResponse
}

export function IntegrationDots({ statuses }: IntegrationDotsProps) {
  const isConnected = (key: keyof IntegrationStatusResponse) =>
    statuses[key]?.status === 'connected'

  const visible = INTEGRATIONS.filter((i) => {
    // Hide disconnected integration if its rival is connected
    if ('rival' in i && i.rival && !isConnected(i.key) && isConnected(i.rival)) {
      return false
    }
    return true
  })

  // Sort: connected first, then alphabetical
  const sorted = [...visible].sort((a, b) => {
    const aConn = isConnected(a.key) ? 0 : 1
    const bConn = isConnected(b.key) ? 0 : 1
    if (aConn !== bConn) return aConn - bConn
    return a.name.localeCompare(b.name)
  })

  const disconnectedCount = visible.filter((i) => !isConnected(i.key)).length

  return (
    <div className="flex flex-wrap items-center gap-3">
      {sorted.map((integration) => {
        const status = statuses[integration.key]
        const connected = status?.status === 'connected'
        const isError = status?.status === 'error'

        const dotClass = connected
          ? 'bg-emerald-500'
          : isError
            ? 'bg-red-500'
            : 'bg-muted-foreground/20'

        const tooltip = connected
          ? `${integration.name}: connected`
          : isError
            ? `${integration.name}: error`
            : `${integration.name}: disconnected`

        return (
          <div
            key={integration.key}
            className="relative flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-default py-1 px-1 -mx-1 rounded before:absolute before:inset-x-0 before:-inset-y-2 before:content-['']"
            title={tooltip}
          >
            <span
              className={`h-2 w-2 rounded-full shrink-0 ${dotClass}`}
            />
            <span>{integration.name}</span>
          </div>
        )
      })}
      {disconnectedCount > 0 && (
        <Link
          href="/dashboard/settings"
          className="flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground hover:border-muted-foreground/40 transition-colors ml-1"
          title="Connect more integrations"
        >
          <Plus className="h-3 w-3" />
          <span>Add</span>
        </Link>
      )}
    </div>
  )
}
