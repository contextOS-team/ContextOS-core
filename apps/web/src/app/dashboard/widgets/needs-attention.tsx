import Link from 'next/link'
import { AlertCircle, GitPullRequest } from 'lucide-react'
import type { AttentionItem } from '@/lib/api'

interface NeedsAttentionProps {
  items: AttentionItem[]
}

export function NeedsAttention({ items }: NeedsAttentionProps) {
  if (items.length === 0) return null

  return (
    <div>
      <h3 className="section-label mb-3">
        Needs Attention ({items.length})
      </h3>
      <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
        {items.map((item) => {
          const isPR = item.type === 'pr_review' || item.type === 'mr_review'
          const href =
            item.type === 'stale_context' || item.type === 'no_sources'
              ? `/dashboard/context/${item.id}`
              : undefined

          const content = (
            <div className="flex items-center gap-3 px-4 py-3 transition-colors duration-150 hover:bg-muted/40">
              <div className="shrink-0 text-muted-foreground">
                {isPR ? (
                  <GitPullRequest className="h-4 w-4" />
                ) : (
                  <AlertCircle className="h-4 w-4" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">
                  {item.title}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  {item.ticket_identifier && (
                    <span className="text-xs font-mono text-muted-foreground">
                      {item.ticket_identifier}
                    </span>
                  )}
                  {isPR && item.repo_full_name && (
                    <span className="text-xs font-mono text-muted-foreground">
                      {item.repo_full_name}#{item.number}
                    </span>
                  )}
                  {item.author && (
                    <span className="text-xs text-muted-foreground">
                      by {item.author}
                    </span>
                  )}
                </div>
              </div>
              {item.age && (
                <span className="shrink-0 text-xs text-muted-foreground font-mono">
                  {item.age}
                </span>
              )}
            </div>
          )

          if (href) {
            return (
              <Link key={item.id} href={href} className="block">
                {content}
              </Link>
            )
          }

          return <div key={item.id}>{content}</div>
        })}
      </div>
    </div>
  )
}
