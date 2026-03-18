'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { fetchMyWorkGraph } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import type { ApiNode, ApiEdge } from '@/components/graph/types'

/* ── colour map by entity type ─────────────────────────────── */

const NODE_COLORS: Record<string, string> = {
  Ticket: '#10b981',
  Person: '#6366f1',
  Decision: '#f59e0b',
}
const DEFAULT_NODE_COLOR = '#64748b'

function nodeColor(entityType: string): string {
  return NODE_COLORS[entityType] ?? DEFAULT_NODE_COLOR
}

/* ── deterministic hash for seeded positioning ─────────────── */

function hashCode(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0
  }
  return h
}

/* ── simple circular layout with per-node jitter ───────────── */

interface Pos {
  x: number
  y: number
}

function layoutNodes(nodes: ApiNode[], width: number, height: number): Map<string, Pos> {
  const positions = new Map<string, Pos>()
  const cx = width / 2
  const cy = height / 2
  const rx = width * 0.38
  const ry = height * 0.36
  const count = nodes.length

  nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / count
    const h = hashCode(node.id)
    // jitter ±12 % of radius
    const jx = ((h & 0xff) / 255 - 0.5) * rx * 0.24
    const jy = (((h >> 8) & 0xff) / 255 - 0.5) * ry * 0.24
    positions.set(node.id, {
      x: cx + Math.cos(angle) * rx + jx,
      y: cy + Math.sin(angle) * ry + jy,
    })
  })

  return positions
}

/* ── loading skeleton ──────────────────────────────────────── */

function ThumbnailSkeleton() {
  return (
    <div className="rounded-xl bg-card shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_1px_2px_rgba(0,0,0,0.2),0_2px_8px_rgba(0,0,0,0.12)] overflow-hidden">
      <div className="px-4 pt-3 pb-2 flex items-center justify-between">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 w-20" />
      </div>
      <div className="relative w-full" style={{ height: 180 }}>
        <Skeleton className="absolute left-1/2 top-6 h-3 w-3 -translate-x-1/2 rounded-full" />
        <Skeleton className="absolute left-6 top-16 h-2.5 w-2.5 rounded-full" />
        <Skeleton className="absolute right-8 top-12 h-2.5 w-2.5 rounded-full" />
        <Skeleton className="absolute left-12 bottom-6 h-2 w-2 rounded-full" />
        <Skeleton className="absolute right-12 bottom-10 h-2 w-2 rounded-full" />
      </div>
      <div className="px-4 py-2.5 border-t border-border/50">
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
  )
}

/* ── main widget ───────────────────────────────────────────── */

const SVG_WIDTH = 400
const SVG_HEIGHT = 180

export function GraphThumbnail() {
  const [nodes, setNodes] = useState<ApiNode[] | null>(null)
  const [edges, setEdges] = useState<ApiEdge[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    fetchMyWorkGraph()
      .then((res) => {
        if (cancelled) return
        setNodes(res.all_nodes)
        setEdges(res.all_edges)
      })
      .catch(() => {
        if (!cancelled) setNodes([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  if (loading) return <ThumbnailSkeleton />
  if (!nodes || nodes.length === 0) return null

  const positions = layoutNodes(nodes, SVG_WIDTH, SVG_HEIGHT)

  return (
    <Link href="/dashboard/graph" className="block group">
      <div className="rounded-xl bg-card shadow-[0_0_0_1px_rgba(255,255,255,0.04),0_1px_2px_rgba(0,0,0,0.2),0_2px_8px_rgba(0,0,0,0.12)] overflow-hidden transition-shadow duration-150 group-hover:shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_2px_4px_rgba(0,0,0,0.3),0_4px_12px_rgba(0,0,0,0.18)]">
        {/* header */}
        <div className="px-4 pt-3 pb-2 flex items-center justify-between">
          <span className="section-label">My Work</span>
          <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
            View graph&nbsp;&rarr;
          </span>
        </div>

        {/* mini graph */}
        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
          className="w-full"
          style={{ height: 180 }}
          aria-hidden="true"
        >
          {/* edges */}
          {edges.map((edge, i) => {
            const src = positions.get(edge.source)
            const tgt = positions.get(edge.target)
            if (!src || !tgt) return null
            return (
              <line
                key={i}
                x1={src.x}
                y1={src.y}
                x2={tgt.x}
                y2={tgt.y}
                stroke="rgba(255,255,255,0.06)"
                strokeWidth={1}
              />
            )
          })}
          {/* nodes */}
          {nodes.map((node) => {
            const pos = positions.get(node.id)
            if (!pos) return null
            const r = node.entity_type === 'Ticket' ? 4.5 : node.entity_type === 'Person' ? 4 : 3
            return (
              <circle
                key={node.id}
                cx={pos.x}
                cy={pos.y}
                r={r}
                fill={nodeColor(node.entity_type)}
                opacity={0.85}
              />
            )
          })}
        </svg>

        {/* footer */}
        <div className="px-4 py-2.5 border-t border-border/50">
          <span className="text-xs text-muted-foreground">
            {nodes.length} node{nodes.length !== 1 ? 's' : ''} &middot;{' '}
            {edges.length} edge{edges.length !== 1 ? 's' : ''}
          </span>
        </div>
      </div>
    </Link>
  )
}
