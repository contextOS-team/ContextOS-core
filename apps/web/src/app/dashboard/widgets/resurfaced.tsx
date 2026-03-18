import type { ResurfacedItem } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'

interface ResurfacedProps {
  items: ResurfacedItem[]
}

export function Resurfaced({ items }: ResurfacedProps) {
  if (items.length === 0) return null

  return (
    <div>
      <h3 className="section-label mb-3">Resurfaced</h3>
      <div className="rounded-xl bg-card shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_1px_2px_rgba(0,0,0,0.2),0_2px_8px_rgba(0,0,0,0.12)] overflow-hidden divide-y divide-border/50">
        {items.map((item) => (
          <div
            key={item.id}
            className="px-4 py-3 transition-colors duration-150 hover:bg-muted/40"
          >
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
              {item.user_name && (
                <span className="font-medium text-foreground">
                  @{item.user_name}
                </span>
              )}
              {item.channel_name && (
                <span>
                  in #{item.channel_name}
                </span>
              )}
              <span className="font-mono">{formatRelativeTime(item.created_at)}</span>
            </div>
            <p className="text-sm text-foreground/80 leading-relaxed">
              &ldquo;{item.text}&rdquo;
            </p>
            <p className="text-xs text-muted-foreground/60 mt-1">
              No ticket created
            </p>
          </div>
        ))}
      </div>
    </div>
  )
}
