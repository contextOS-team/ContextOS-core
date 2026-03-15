import type { DaySummary } from '@/lib/api'
import { formatDayLabel } from '../activity/formatters'

interface ThisWeekProps {
  days: DaySummary[]
}

export function ThisWeek({ days }: ThisWeekProps) {
  // Filter out days with all-zero counts
  const activeDays = days.filter(
    (d) => d.activity_count > 0 || d.contexts_updated > 0 || d.prs_merged > 0
  )

  if (activeDays.length === 0) return null

  return (
    <div>
      <h3 className="section-label mb-3">This Week</h3>
      <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
        {activeDays.map((day) => {
          const parts: string[] = []
          if (day.contexts_updated > 0)
            parts.push(`${day.contexts_updated} context${day.contexts_updated === 1 ? '' : 's'} updated`)
          if (day.prs_merged > 0)
            parts.push(`${day.prs_merged} PR${day.prs_merged === 1 ? '' : 's'} merged`)
          if (parts.length === 0 && day.activity_count > 0)
            parts.push(`${day.activity_count} event${day.activity_count === 1 ? '' : 's'}`)

          return (
            <div
              key={day.date}
              className="flex items-center gap-4 px-4 py-2.5"
            >
              <span className="text-xs font-medium text-muted-foreground w-24 shrink-0 uppercase">
                {formatDayLabel(day.date)}
              </span>
              <span className="text-sm text-foreground">
                {parts.join(', ')}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
