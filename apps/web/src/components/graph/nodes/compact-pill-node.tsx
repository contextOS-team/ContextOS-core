'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { EntityType, GraphNodeData } from '../types'
import { ENTITY_COLORS, ENTITY_ICONS } from '../constants'
import { ENTITY_SHAPE, getShapeStyle, HIDDEN_NODE_PROPERTIES } from '../utils'

type CompactPillNodeType = Node<GraphNodeData, 'compact'>

const SHAPE_SIZES: Record<EntityType, number> = {
  Ticket: 44, Person: 40, Decision: 42, PR: 40, Message: 38,
  SlackThread: 38, Code: 36, CodeChunk: 36, NotionPage: 38, Meeting: 42,
}

const SUBTITLE_KEYS = ['state', 'title', 'description', 'label', 'summary']

/** Derive a subtitle from node properties — prefer known keys, skip internal metadata. */
function getSubtitle(data: GraphNodeData): string | null {
  const p = data.properties
  // Try preferred keys first
  for (const key of SUBTITLE_KEYS) {
    const val = p[key]
    if (val != null && typeof val === 'string' && val.length > 0 && val.length < 50) {
      return val
    }
  }
  // Fallback: first non-hidden string property
  for (const [key, val] of Object.entries(p)) {
    if (HIDDEN_NODE_PROPERTIES.has(key)) continue
    if (SUBTITLE_KEYS.includes(key)) continue  // already checked
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
  const shape = ENTITY_SHAPE[data.entityType] ?? 'circle'
  const size = SHAPE_SIZES[data.entityType] ?? 38
  const shapeStyle = getShapeStyle(shape, size)

  const isSelected = data.isSelected ?? false
  const isHovered = data.isHovered ?? false
  const connectedCount = data.connectedCount ?? 0

  // Show identifier prefix (e.g. "CON-50") or truncated name
  const identifierMatch = data.name.match(/^([A-Z][A-Z0-9]+-\d+)/)
  const maxChars = 16
  const label = identifierMatch
    ? identifierMatch[1]
    : data.name.length > maxChars ? data.name.slice(0, maxChars - 1) + '\u2026' : data.name
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
          border: shape === 'diamond' || shape === 'hexagon'
            ? 'none'
            : `${borderWidth}px solid ${borderColor}`,
          boxShadow: glowShadow,
        }}
      >
        {/* For clip-path shapes, render border via an outline wrapper */}
        {(shape === 'diamond' || shape === 'hexagon') && (
          <div
            className="absolute inset-0 -z-10"
            style={{
              ...getShapeStyle(shape, size + (isSelected ? 4 : 2)),
              background: borderColor,
              top: isSelected ? -2 : -1,
              left: isSelected ? -2 : -1,
            }}
          />
        )}

        {/* Entity icon */}
        {Icon && (
          <Icon
            size={size * 0.42}
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
