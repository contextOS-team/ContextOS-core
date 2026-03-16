'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { EntityType, GraphNodeData } from '../types'
import { ENTITY_COLORS, ENTITY_ICONS } from '../constants'

type CompactPillNodeType = Node<GraphNodeData, 'compact'>

// ---------------------------------------------------------------------------
// Shape configuration per entity type
// ---------------------------------------------------------------------------

type ShapeKind = 'diamond' | 'circle' | 'rounded-rect' | 'hexagon'

interface ShapeConfig {
  shape: ShapeKind
  size: number
}

const SHAPE_CONFIG: Record<EntityType, ShapeConfig> = {
  Ticket: { shape: 'diamond', size: 44 },
  Person: { shape: 'circle', size: 40 },
  Decision: { shape: 'hexagon', size: 42 },
  PR: { shape: 'rounded-rect', size: 40 },
  Message: { shape: 'rounded-rect', size: 38 },
  SlackThread: { shape: 'rounded-rect', size: 38 },
  Code: { shape: 'rounded-rect', size: 36 },
  CodeChunk: { shape: 'rounded-rect', size: 36 },
  NotionPage: { shape: 'rounded-rect', size: 38 },
  Meeting: { shape: 'circle', size: 42 },
}

/** CSS properties that give each shape its distinct silhouette. */
function getShapeStyle(shape: ShapeKind, size: number): React.CSSProperties {
  const base: React.CSSProperties = { width: size, height: size }
  switch (shape) {
    case 'circle':
      return { ...base, borderRadius: '50%' }
    case 'diamond':
      return { ...base, clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)' }
    case 'hexagon':
      return { ...base, clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }
    case 'rounded-rect':
      return { ...base, borderRadius: 8 }
  }
}

/** Properties to never show as subtitle. */
const HIDDEN_PROPS = new Set([
  'status', 'platform', 'username', 'team_prefix', 'identifier',
  'source_type', 'source_id', 'fingerprint', 'workspace_id',
  'resolved_from', 'sha', 'short_sha',
])

/** Derive a subtitle from node properties — skip internal metadata. */
function getSubtitle(data: GraphNodeData): string | null {
  const p = data.properties
  for (const [key, val] of Object.entries(p)) {
    if (HIDDEN_PROPS.has(key)) continue
    if (val != null && typeof val === 'string' && val.length > 0 && val.length < 50) {
      return val
    }
  }
  return null
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

function CompactPillNodeInner({ data }: NodeProps<CompactPillNodeType>) {
  const color = ENTITY_COLORS[data.entityType] ?? 'var(--muted-foreground)'
  const Icon = ENTITY_ICONS[data.entityType]
  const cfg = SHAPE_CONFIG[data.entityType] ?? { shape: 'circle' as const, size: 38 }
  const shapeStyle = getShapeStyle(cfg.shape, cfg.size)

  const isSelected = data.isSelected ?? false
  const isHovered = data.isHovered ?? false
  const connectedCount = data.connectedCount ?? 0

  const maxChars = 14
  const label =
    data.name.length > maxChars ? data.name.slice(0, maxChars - 1) + '\u2026' : data.name
  const subtitle = getSubtitle(data)

  // Glow ring via box-shadow
  const glowShadow = isSelected
    ? `0 0 16px 5px color-mix(in oklch, ${color} 50%, transparent), 0 0 2px 1px color-mix(in oklch, ${color} 70%, transparent)`
    : isHovered
      ? `0 0 12px 4px color-mix(in oklch, ${color} 35%, transparent)`
      : 'none'

  // Border changes with state
  const borderColor = isSelected
    ? color
    : `color-mix(in oklch, ${color} 30%, transparent)`
  const borderWidth = isSelected ? 2 : 1

  return (
    <div
      className="relative flex flex-col items-center transition-all duration-200"
      style={{ opacity: data.isDimmed ? 0.25 : 1, width: 100 }}
    >
      {/* Shape container */}
      <div
        className="relative flex items-center justify-center transition-shadow duration-300 ease-out"
        style={{
          ...shapeStyle,
          background: '#14141c',
          border: cfg.shape === 'diamond' || cfg.shape === 'hexagon'
            ? 'none'
            : `${borderWidth}px solid ${borderColor}`,
          boxShadow: glowShadow,
        }}
      >
        {/* For clip-path shapes, render border via an outline wrapper */}
        {(cfg.shape === 'diamond' || cfg.shape === 'hexagon') && (
          <div
            className="absolute inset-0 -z-10"
            style={{
              ...getShapeStyle(cfg.shape, cfg.size + (isSelected ? 4 : 2)),
              background: borderColor,
              top: isSelected ? -2 : -1,
              left: isSelected ? -2 : -1,
            }}
          />
        )}

        {/* Entity icon */}
        {Icon && (
          <Icon
            size={cfg.size * 0.42}
            style={{ color, flexShrink: 0 }}
            strokeWidth={1.8}
          />
        )}

        {/* Connection count badge — shown on hover */}
        {isHovered && connectedCount > 0 && (
          <div
            className="absolute -top-1.5 -right-1.5 flex items-center justify-center rounded-full text-[8px] font-bold"
            style={{
              width: 16,
              height: 16,
              background: color,
              color: '#09090d',
            }}
          >
            {connectedCount}
          </div>
        )}
      </div>

      {/* Label below shape */}
      <span
        className="mt-1 text-center text-[11px] font-medium leading-tight truncate"
        style={{ color: 'var(--foreground)', maxWidth: 96 }}
      >
        {label}
      </span>

      {/* Subtitle */}
      {subtitle && (
        <span
          className="text-center text-[9.5px] leading-tight truncate"
          style={{ color: 'var(--muted-foreground)', maxWidth: 96 }}
        >
          {subtitle}
        </span>
      )}

      <Handle type="target" position={Position.Top} className="!opacity-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0 !w-0 !h-0" />
    </div>
  )
}

export const CompactPillNode = memo(CompactPillNodeInner)
