import type { SprintData } from '@/lib/api'

interface SprintBadgeProps {
  sprint: SprintData | null
}

export function SprintBadge({ sprint }: SprintBadgeProps) {
  if (!sprint) return null

  const endsAt = new Date(sprint.ends_at)
  const now = new Date()
  const diffMs = endsAt.getTime() - now.getTime()
  const daysRemaining = Math.max(0, Math.ceil(diffMs / 86_400_000))

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span>
        {sprint.cycle_name || `Cycle ${sprint.cycle_number}`}
      </span>
      <span className="font-mono tabular-nums text-teal-500">
        {sprint.completed}/{sprint.total}
      </span>
      <span className="text-muted-foreground/60 tabular-nums">
        {daysRemaining === 0
          ? 'ends today'
          : daysRemaining === 1
            ? '1 day left'
            : `${daysRemaining} days left`}
      </span>
    </div>
  )
}
