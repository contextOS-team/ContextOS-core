'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { EntityType, GraphNodeData } from '../types'
import { ENTITY_COLORS, ENTITY_ICONS } from '../constants'

type FullDetailNodeType = Node<GraphNodeData, 'full'>

// ---------------------------------------------------------------------------
// Shape-icon header — mini version of compact node shapes
// ---------------------------------------------------------------------------

type ShapeKind = 'diamond' | 'circle' | 'rounded-rect' | 'hexagon'

const HEADER_SHAPE: Record<EntityType, ShapeKind> = {
  Ticket: 'diamond',
  Person: 'circle',
  Decision: 'hexagon',
  PR: 'rounded-rect',
  Message: 'rounded-rect',
  SlackThread: 'rounded-rect',
  Code: 'rounded-rect',
  CodeChunk: 'rounded-rect',
  NotionPage: 'rounded-rect',
  Meeting: 'circle',
}

function getHeaderShapeStyle(shape: ShapeKind): React.CSSProperties {
  const size = 28
  const base: React.CSSProperties = { width: size, height: size, flexShrink: 0 }
  switch (shape) {
    case 'circle':
      return { ...base, borderRadius: '50%' }
    case 'diamond':
      return { ...base, clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)' }
    case 'hexagon':
      return { ...base, clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }
    case 'rounded-rect':
      return { ...base, borderRadius: 6 }
  }
}

/** Derive node dimensions from connection count. */
function getFullSizeFromConnections(count: number) {
  if (count >= 5) return { width: 280, height: 95 }
  if (count >= 2) return { width: 240, height: 85 }
  return { width: 200, height: 70 }
}

function FullDetailNodeInner({ data }: NodeProps<FullDetailNodeType>) {
  const color = ENTITY_COLORS[data.entityType] ?? 'var(--muted-foreground)'
  const Icon = ENTITY_ICONS[data.entityType]
  const property = data.properties?.identifier ?? data.properties?.number ?? ''
  const { width, height } = getFullSizeFromConnections(data.connectedCount ?? 0)
  const shape = HEADER_SHAPE[data.entityType] ?? 'circle'

  const isSelected = data.isSelected ?? false
  const isHovered = data.isHovered ?? false

  const glowShadow = data.isRoot
    ? `0 0 20px 6px color-mix(in oklch, ${color} 40%, transparent)`
    : isSelected
      ? `0 0 16px 5px color-mix(in oklch, ${color} 35%, transparent)`
      : isHovered
        ? `0 0 12px 3px color-mix(in oklch, ${color} 20%, transparent)`
        : 'none'

  return (
    <div
      className="relative transition-all duration-200"
      style={{ opacity: data.isDimmed ? 0.3 : 1 }}
    >
      <div
        className="rounded-xl border border-[var(--border)] overflow-hidden"
        style={{
          width,
          height,
          background: 'var(--elevated)',
          borderLeft: `4px solid ${color}`,
          boxShadow: glowShadow,
          transition: 'box-shadow 0.3s ease',
        }}
      >
        {/* Top row: shape-icon + name */}
        <div className="flex items-center gap-2 px-3 pt-2.5">
          {/* Shape container with icon inside */}
          <div
            className="flex items-center justify-center"
            style={{
              ...getHeaderShapeStyle(shape),
              background: `color-mix(in oklch, ${color} 15%, transparent)`,
            }}
          >
            {Icon && (
              <Icon
                size={14}
                style={{ color, flexShrink: 0 }}
                strokeWidth={1.8}
              />
            )}
          </div>
          <span
            className="text-sm font-medium truncate"
            style={{ color: 'var(--foreground)' }}
          >
            {data.name}
          </span>
        </div>

        {/* Bottom row: type badge + key property */}
        <div className="flex items-center gap-2 px-3 pt-1.5">
          <span
            className="text-[10px] font-medium px-1.5 py-0.5 rounded-full"
            style={{
              background: `color-mix(in oklch, ${color} 15%, transparent)`,
              color,
            }}
          >
            {data.entityType}
          </span>
          {property && (
            <span
              className="text-[11px] truncate"
              style={{ color: 'var(--muted-foreground)' }}
            >
              {String(property)}
            </span>
          )}
        </div>
      </div>

      {/* Selected: pulse ring */}
      {isSelected && (
        <div
          className="absolute inset-0 rounded-xl pointer-events-none"
          style={{
            animation: 'pulse-ring 2s cubic-bezier(0.34, 1.56, 0.64, 1) infinite',
            boxShadow: `0 0 0 2px ${color}`,
          }}
        />
      )}

      <Handle type="target" position={Position.Top} className="!opacity-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0 !w-0 !h-0" />
    </div>
  )
}

export const FullDetailNode = memo(FullDetailNodeInner)
