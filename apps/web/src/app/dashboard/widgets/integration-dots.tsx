import type { IntegrationStatusResponse } from '@/lib/api'

const INTEGRATIONS = [
  { key: 'linear' as const, name: 'Linear' },
  { key: 'slack' as const, name: 'Slack' },
  { key: 'fathom' as const, name: 'Fathom' },
  { key: 'github' as const, name: 'GitHub' },
  { key: 'notion' as const, name: 'Notion' },
  { key: 'gitlab' as const, name: 'GitLab' },
  { key: 'telegram' as const, name: 'Telegram' },
  { key: 'jira' as const, name: 'Jira' },
]

interface IntegrationDotsProps {
  statuses: IntegrationStatusResponse
}

export function IntegrationDots({ statuses }: IntegrationDotsProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {INTEGRATIONS.map((integration) => {
        const status = statuses[integration.key]
        const isConnected = status?.status === 'connected'
        const isError = status?.status === 'error'

        const dotClass = isConnected
          ? 'bg-emerald-500'
          : isError
            ? 'bg-red-500'
            : 'border border-muted-foreground/30'

        const tooltip = isConnected
          ? `${integration.name}: connected`
          : isError
            ? `${integration.name}: error`
            : `${integration.name}: disconnected`

        return (
          <div
            key={integration.key}
            className="flex items-center gap-1.5 text-xs text-muted-foreground"
            title={tooltip}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full shrink-0 ${dotClass}`}
            />
            <span>{integration.name}</span>
          </div>
        )
      })}
    </div>
  )
}
