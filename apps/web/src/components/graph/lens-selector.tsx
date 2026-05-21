'use client'

import { cn } from '@/lib/utils'
import type { GraphLens } from './types'

interface LensSelectorProps {
  activeLens: GraphLens
  onLensChange: (lens: GraphLens) => void
  sprintDisabled?: boolean
  sprintTooltip?: string
}

const LENSES: Array<{ id: GraphLens; label: string }> = [
  { id: 'my_work', label: 'My Work' },
  { id: 'sprint', label: 'Sprint' },
  { id: 'blocked', label: 'Blocked' },
  { id: 'browse', label: 'Browse' },
]

export function LensSelector({
  activeLens,
  onLensChange,
  sprintDisabled,
  sprintTooltip,
}: LensSelectorProps) {
  return (
    <div className="dashboard-segmented">
      {LENSES.map(({ id, label }) => {
        const isActive = activeLens === id
        const isDisabled = id === 'sprint' && sprintDisabled

        return (
          <button
            key={id}
            onClick={() => !isDisabled && onLensChange(id)}
            disabled={isDisabled}
            title={isDisabled ? sprintTooltip : undefined}
            className={cn(
              'dashboard-segmented-item',
              isActive
                ? 'dashboard-segmented-item--active'
                : '',
              isDisabled && 'cursor-not-allowed opacity-40',
            )}
          >
            {label}
          </button>
        )
      })}
    </div>
  )
}
