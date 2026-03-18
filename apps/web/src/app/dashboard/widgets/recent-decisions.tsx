'use client'

import { useEffect, useState } from 'react'
import { Lightbulb } from 'lucide-react'
import Link from 'next/link'
import { fetchMyWorkGraph } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import type { ApiNode } from '@/components/graph/types'
import { formatRelativeTime } from '@/lib/utils'

interface DecisionDisplay {
  id: string
  text: string
  participants: string[]
  sourceChannel: string | null
  source: string | null
  date: string | null
}

function parseDecisionNode(node: ApiNode): DecisionDisplay {
  const props = node.properties ?? {}
  return {
    id: node.id,
    text: node.name,
    participants: Array.isArray(props.participants)
      ? (props.participants as string[])
      : [],
    sourceChannel: (props.source_channel as string) ?? null,
    source: (props.source as string) ?? null,
    date: (props.date as string) ?? null,
  }
}

export function RecentDecisions() {
  const [decisions, setDecisions] = useState<DecisionDisplay[] | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const data = await fetchMyWorkGraph()
        if (cancelled) return

        const decisionNodes = data.all_nodes
          .filter((n) => n.entity_type === 'Decision')
          .sort((a, b) => {
            const dateA = (a.properties?.date as string) ?? ''
            const dateB = (b.properties?.date as string) ?? ''
            return dateB.localeCompare(dateA)
          })
          .slice(0, 3)

        setDecisions(decisionNodes.map(parseDecisionNode))
      } catch {
        setDecisions([])
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  // Loading skeleton
  if (loading) {
    return (
      <div>
        <h3 className="section-label mb-3">Recent Decisions</h3>
        <div className="rounded-xl bg-card shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_1px_2px_rgba(0,0,0,0.2),0_2px_8px_rgba(0,0,0,0.12)] overflow-hidden divide-y divide-border/40">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="px-4 py-3 flex items-start gap-3">
              <Skeleton className="h-5 w-5 rounded shrink-0 mt-0.5" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3.5 w-full" />
                <Skeleton className="h-3.5 w-3/4" />
                <Skeleton className="h-2.5 w-24" />
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // No decisions — render nothing
  if (!decisions || decisions.length === 0) return null

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="section-label">Recent Decisions</h3>
        <Link
          href="/dashboard/activity"
          className="text-xs text-muted-foreground/60 hover:text-muted-foreground transition-colors"
        >
          View all
        </Link>
      </div>

      <div className="rounded-xl bg-card shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_1px_2px_rgba(0,0,0,0.2),0_2px_8px_rgba(0,0,0,0.12)] overflow-hidden">
        {decisions.map((decision, idx) => (
          <div
            key={decision.id}
            className={`px-4 py-3 transition-colors duration-150 hover:bg-muted/40${
              idx < decisions.length - 1 ? ' border-b border-border/40' : ''
            }`}
          >
            <div className="flex items-start gap-2.5">
              <Lightbulb className="h-4 w-4 text-amber-500/70 shrink-0 mt-0.5" />
              <div className="min-w-0 flex-1">
                <p className="text-sm text-foreground/80 leading-relaxed line-clamp-2">
                  &ldquo;{decision.text}&rdquo;
                </p>

                {decision.participants.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {decision.participants.map((name) => (
                      <span
                        key={name}
                        className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                )}

                <div className="flex items-center gap-1.5 mt-1.5 text-xs text-muted-foreground">
                  {decision.sourceChannel && (
                    <span>in {decision.sourceChannel}</span>
                  )}
                  {decision.sourceChannel && decision.date && (
                    <span className="text-muted-foreground/30">&middot;</span>
                  )}
                  {decision.date && (
                    <span className="font-mono">
                      {formatRelativeTime(decision.date)}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
