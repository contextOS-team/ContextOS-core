import { Skeleton } from '@/components/ui/skeleton'

export default function ActivityPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="section-label mb-2">Activity</p>
        <h1 className="text-2xl font-semibold tracking-[-0.03em] text-foreground">
          Activity Timeline
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Workspace events will appear here
        </p>
      </div>

      {/* Skeleton preview of what the timeline will look like */}
      <div className="space-y-6">
        {/* Day group */}
        <div className="space-y-3">
          <Skeleton className="h-4 w-24" />
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg border border-border p-3">
                <Skeleton className="h-8 w-8 rounded-full shrink-0" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-3/4" />
                  <Skeleton className="h-3 w-1/3" />
                </div>
                <Skeleton className="h-3 w-16 shrink-0" />
              </div>
            ))}
          </div>
        </div>
        {/* Second day group */}
        <div className="space-y-3">
          <Skeleton className="h-4 w-20" />
          <div className="space-y-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg border border-border p-3">
                <Skeleton className="h-8 w-8 rounded-full shrink-0" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-2/3" />
                  <Skeleton className="h-3 w-1/4" />
                </div>
                <Skeleton className="h-3 w-16 shrink-0" />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Empty state message */}
      <div className="rounded-xl border border-dashed border-border bg-card p-8 text-center">
        <p className="text-sm text-muted-foreground">
          Activity timeline coming soon. Sync events, context generation, and integration activity will appear here.
        </p>
      </div>
    </div>
  )
}
