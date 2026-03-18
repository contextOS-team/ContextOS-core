'use client'

import { useMemo } from 'react'
import { Lightbulb } from 'lucide-react'
import Link from 'next/link'
import type { ApiNode, LensGraphResponse } from '@/components/graph/types'
import { formatRelativeTime } from '@/lib/utils'

interface DecisionDisplay {
  id: string
  text: string
  participants: string[]
  sourceChannel: string | null
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
    date: (props.date as string) ?? null,
  }
}

interface RecentDecisionsProps {
  data: LensGraphResponse | null
}

export function RecentDecisions({ data }: RecentDecisionsProps) {
  const decisions = useMemo(() => {
    if (!data) return null
    return data.all_nodes
      .filter((n) => n.entity_type === 'Decision')
      .sort((a, b) => {
        const dateA = (a.properties?.date as string) ?? ''
        const dateB = (b.properties?.date as string) ?? ''
        return dateB.localeCompare(dateA)
      })
      .slice(0, 3)
      .map(parseDecisionNode)
  }, [data])

  // data is null only on API error — parent handles loading state
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

      <div className="widget-card rounded-xl">
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
