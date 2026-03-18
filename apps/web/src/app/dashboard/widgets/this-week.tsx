'use client'

import type { DaySummary } from '@/lib/api'

interface ThisWeekProps {
  days: DaySummary[]
}

const DAY_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']

function getDayOfWeekIndex(dateStr: string): number {
  // dateStr is "YYYY-MM-DD"; JS Date months are 0-based
  const [y, m, d] = dateStr.split('-').map(Number)
  const jsDay = new Date(y, m - 1, d).getDay() // 0=Sun
  return jsDay === 0 ? 6 : jsDay - 1 // convert to 0=Mon
}

function isToday(dateStr: string): boolean {
  const now = new Date()
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
  return dateStr === today
}

export function ThisWeek({ days }: ThisWeekProps) {
  // Build a 7-slot array (Mon-Sun) with totals
  const slots = Array.from({ length: 7 }, () => 0)

  for (const d of days) {
    const total = d.activity_count + d.contexts_updated + d.prs_merged
    const idx = getDayOfWeekIndex(d.date)
    if (idx >= 0 && idx < 7) slots[idx] += total
  }

  const grandTotal = slots.reduce((a, b) => a + b, 0)
  if (grandTotal === 0) return null

  const max = Math.max(...slots)

  // Build a date lookup for tooltips
  const dateByIdx: Record<number, string> = {}
  for (const d of days) {
    const idx = getDayOfWeekIndex(d.date)
    if (idx >= 0 && idx < 7) dateByIdx[idx] = d.date
  }

  return (
    <div className="rounded-xl bg-card shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_1px_2px_rgba(0,0,0,0.2),0_2px_8px_rgba(0,0,0,0.12)] overflow-hidden">
      <div className="px-4 py-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h3 className="section-label">This Week</h3>
          <span className="text-xs text-muted-foreground font-mono tabular-nums">
            {grandTotal} event{grandTotal === 1 ? '' : 's'}
          </span>
        </div>

        {/* Bars */}
        <div className="flex items-end justify-between gap-2 h-12 mt-3">
          {slots.map((count, i) => {
            const pct = max > 0 && count > 0 ? Math.max((count / max) * 100, 8) : 0
            const today = dateByIdx[i] ? isToday(dateByIdx[i]) : false

            let barClass: string
            if (count === 0) {
              barClass = 'bg-muted-foreground/10'
            } else if (today) {
              barClass = 'bg-emerald-500'
            } else {
              barClass = 'bg-emerald-500/30'
            }

            return (
              <div
                key={i}
                className="flex-1 flex items-end justify-center h-full"
              >
                <div
                  className={`w-full rounded-t-sm ${barClass}`}
                  style={{ height: count === 0 ? '2px' : `${pct}%` }}
                  title={`${DAY_LABELS[i]}: ${count} event${count === 1 ? '' : 's'}`}
                />
              </div>
            )
          })}
        </div>

        {/* Day labels */}
        <div className="flex justify-between mt-1.5">
          {DAY_LABELS.map((label, i) => (
            <span
              key={i}
              className="flex-1 text-center text-[10px] text-muted-foreground/60 uppercase"
            >
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
