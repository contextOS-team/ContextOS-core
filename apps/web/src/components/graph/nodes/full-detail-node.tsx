'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { GraphNodeData } from '../types'
import { ENTITY_COLORS, ENTITY_ICONS } from '../constants'

type FullDetailNodeType = Node<GraphNodeData, 'full'>

/** Derive node dimensions from connection count. */
function getFullSizeFromConnections(count: number) {
  if (count >= 5) return { width: 280, height: 95, borderWidth: 5 }
  if (count >= 2) return { width: 240, height: 85, borderWidth: 4 }
  return { width: 200, height: 70, borderWidth: 4 }
}

function FullDetailNodeInner({ data }: NodeProps<FullDetailNodeType>) {
  const color = ENTITY_COLORS[data.entityType] ?? 'var(--muted-foreground)'
  const Icon = ENTITY_ICONS[data.entityType]
  const property = data.properties?.identifier ?? data.properties?.number ?? ''
  const { width, height, borderWidth } = getFullSizeFromConnections(data.connectedCount ?? 0)

  const glowStyle = data.isRoot
    ? { boxShadow: `0 0 20px 6px color-mix(in oklch, ${color} 40%, transparent)` }
    : data.isHovered
      ? { boxShadow: `0 0 12px 3px color-mix(in oklch, ${color} 20%, transparent)` }
      : undefined

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
          borderLeft: `${borderWidth}px solid ${color}`,
          ...glowStyle,
        }}
      >
        {/* Top row: icon + name */}
        <div className="flex items-center gap-2 px-3 pt-2.5">
          {Icon && (
            <Icon
              size={16}
              style={{ color, flexShrink: 0 }}
            />
          )}
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
      {data.isSelected && (
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
