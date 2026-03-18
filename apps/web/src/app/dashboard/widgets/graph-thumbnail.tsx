'use client'

import { useMemo } from 'react'
import Link from 'next/link'
import type { EntityType, LensGraphResponse } from '@/components/graph/types'
import {
  forceLayout,
  getSvgHeight,
  filterToUserPerson,
  buildFooterText,
  getNodeLabel,
  analyzeConnections,
  resolveVisibleLabels,
} from './graph-thumbnail-logic'

/**
 * SVG fill colors as hex — ENTITY_COLORS from constants uses OKLCH which older
 * browsers don't support in SVG fill attributes. These are hex approximations.
 */
const SVG_NODE_COLORS: Record<EntityType, string> = {
  Ticket: '#8b5cf6',     // violet
  Person: '#ec4899',     // pink/rose
  Decision: '#eab308',   // amber
  PR: '#22c55e',         // green
  Message: '#3b82f6',    // blue
  Code: '#14b8a6',       // teal
  CodeChunk: '#0d9488',  // teal muted
  NotionPage: '#6b7280', // cool gray
  SlackThread: '#d946ef',// magenta
  Meeting: '#f97316',    // orange
}
const DEFAULT_SVG_COLOR = '#64748b'

/* ── node shapes by entity type ───────────────────────────── */

function NodeShape({
  entityType,
  x,
  y,
  r,
  fill,
  opacity,
  isHub,
}: {
  entityType: EntityType
  x: number
  y: number
  r: number
  fill: string
  opacity: number
  isHub: boolean
}) {
  const glow = isHub ? (
    <circle cx={x} cy={y} r={r * 2.5} fill={fill} opacity={0.12} />
  ) : null

  switch (entityType) {
    // Tickets → rounded square
    case 'Ticket': {
      const s = r * 1.6
      return (
        <>
          {glow}
          <rect
            x={x - s / 2}
            y={y - s / 2}
            width={s}
            height={s}
            rx={s * 0.2}
            fill={fill}
            opacity={opacity}
          />
        </>
      )
    }
    // Decisions → diamond
    case 'Decision': {
      const d = r * 1.4
      return (
        <>
          {glow}
          <polygon
            points={`${x},${y - d} ${x + d},${y} ${x},${y + d} ${x - d},${y}`}
            fill={fill}
            opacity={opacity}
          />
        </>
      )
    }
    // PRs → triangle
    case 'PR': {
      const d = r * 1.5
      return (
        <>
          {glow}
          <polygon
            points={`${x},${y - d} ${x + d * 0.87},${y + d * 0.5} ${x - d * 0.87},${y + d * 0.5}`}
            fill={fill}
            opacity={opacity}
          />
        </>
      )
    }
    // People, messages, code, etc → circle
    default:
      return (
        <>
          {glow}
          <circle cx={x} cy={y} r={r} fill={fill} opacity={opacity} />
        </>
      )
  }
}

/* ── main widget ──────────────────────────────────────────── */

const SVG_WIDTH = 400

// Stable empty array to avoid re-creating on every render when data is null
const EMPTY_EDGES: never[] = []

interface GraphThumbnailProps {
  data: LensGraphResponse | null
  userName?: string
}

export function GraphThumbnail({ data, userName }: GraphThumbnailProps) {
  const allNodes = data?.all_nodes ?? null
  // FIX: stable reference for empty edges — avoids memo invalidation every render
  const allEdges = data?.all_edges ?? EMPTY_EDGES

  // Keep only the current user's Person node — match by name, fall back to most-connected
  const { nodes, edges } = useMemo(() => {
    if (!allNodes || allNodes.length === 0) return { nodes: null, edges: allEdges }
    return filterToUserPerson(allNodes, allEdges, userName)
  }, [allNodes, allEdges, userName])

  const { positions, hubId, connectionCounts, svgHeight } = useMemo(() => {
    if (!nodes || nodes.length === 0) {
      return { positions: null, hubId: null, connectionCounts: new Map<string, number>(), svgHeight: 160 }
    }

    const { counts, hubId } = analyzeConnections(edges)
    const svgH = getSvgHeight(nodes.length)

    return {
      positions: forceLayout(nodes, edges, SVG_WIDTH, svgH),
      hubId,
      connectionCounts: counts,
      svgHeight: svgH,
    }
  }, [nodes, edges])

  // Determine which labels are visible (no overlap)
  const visibleLabels = useMemo(() => {
    if (!nodes || !positions) return new Set<string>()
    return resolveVisibleLabels(nodes, positions, connectionCounts, hubId)
  }, [nodes, positions, connectionCounts, hubId])

  if (!data || !nodes || nodes.length === 0 || !positions) return null

  return (
    <Link href="/dashboard/graph" className="block group">
      <div className="widget-card rounded-xl transition-[box-shadow] duration-200 group-hover:shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_2px_4px_rgba(0,0,0,0.3),0_4px_12px_rgba(0,0,0,0.18)]">
        {/* header */}
        <div className="px-4 pt-3 pb-2 flex items-center justify-between">
          <span className="section-label">My Work</span>
          <span className="text-xs text-muted-foreground group-hover:text-foreground transition-colors">
            View graph&nbsp;&rarr;
          </span>
        </div>

        {/* mini graph */}
        <svg
          viewBox={`0 0 ${SVG_WIDTH} ${svgHeight}`}
          className="w-full"
          style={{ height: svgHeight }}
          aria-hidden="true"
        >
          {/* edges — hub edges slightly brighter */}
          {edges.map((edge, i) => {
            const src = positions.get(edge.source)
            const tgt = positions.get(edge.target)
            if (!src || !tgt) return null
            const touchesHub = edge.source === hubId || edge.target === hubId
            return (
              <line
                key={`${edge.source}::${edge.target}::${i}`}
                x1={src.x}
                y1={src.y}
                x2={tgt.x}
                y2={tgt.y}
                stroke={touchesHub ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.10)'}
                strokeWidth={1}
              />
            )
          })}

          {/* nodes — shape varies by entity type */}
          {nodes.map((node) => {
            const pos = positions.get(node.id)
            if (!pos) return null
            const isHub = node.id === hubId
            const count = connectionCounts.get(node.id) ?? 0
            const r = isHub ? 9 : count >= 2 ? 6.5 : 5
            return (
              <NodeShape
                key={node.id}
                entityType={(node.entity_type as EntityType)}
                x={pos.x}
                y={pos.y}
                r={r}
                fill={SVG_NODE_COLORS[node.entity_type as EntityType] ?? DEFAULT_SVG_COLOR}
                opacity={isHub ? 1 : 0.85}
                isHub={isHub}
              />
            )
          })}

          {/* node labels — only rendered where they don't overlap */}
          {nodes.map((node) => {
            if (!visibleLabels.has(node.id)) return null
            const pos = positions.get(node.id)
            if (!pos) return null
            const isHub = node.id === hubId
            return (
              <text
                key={`lbl-${node.id}`}
                x={pos.x}
                y={pos.y + (isHub ? 18 : 15)}
                textAnchor="middle"
                fill={isHub ? 'rgba(255,255,255,0.45)' : 'rgba(255,255,255,0.28)'}
                fontSize={isHub ? 10 : 9}
                fontFamily="system-ui, sans-serif"
              >
                {getNodeLabel(node)}
              </text>
            )
          })}
        </svg>

        {/* footer — human-readable entity counts */}
        <div className="px-4 py-2.5 border-t border-border/50">
          <span className="text-xs text-muted-foreground">
            {buildFooterText(nodes.filter((n) => positions.has(n.id)))}
          </span>
        </div>
      </div>
    </Link>
  )
}
