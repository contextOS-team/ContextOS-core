'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { GraphNodeData } from '../types'
import { ENTITY_COLORS } from '../constants'

type CompactPillNodeType = Node<GraphNodeData, 'compact'>

/** Derive node width and dot size from connection count. */
function getSizeFromConnections(count: number) {
  if (count >= 5) return { width: 170, dotSize: 10 }
  if (count >= 2) return { width: 140, dotSize: 8 }
  return { width: 110, dotSize: 8 }
}

function CompactPillNodeInner({ data }: NodeProps<CompactPillNodeType>) {
  const color = ENTITY_COLORS[data.entityType] ?? 'var(--muted-foreground)'
  const { width, dotSize } = getSizeFromConnections(data.connectedCount ?? 0)
  const maxChars = width >= 170 ? 20 : width >= 140 ? 17 : 13
  const label = data.name.length > maxChars ? data.name.slice(0, maxChars - 1) + '\u2026' : data.name

  return (
    <div
      className="relative transition-all duration-200"
      style={{ opacity: data.isDimmed ? 0.3 : 1 }}
    >
      <div
        className="flex items-center gap-1.5 rounded-full border border-[var(--border)] px-2.5 py-1"
        style={{
          width,
          height: 32,
          background: `color-mix(in oklch, ${color} 3%, var(--elevated))`,
          borderLeft: `2px solid color-mix(in oklch, ${color} 60%, transparent)`,
        }}
      >
        {/* Colored dot */}
        <span
          className="shrink-0 rounded-full"
          style={{
            width: dotSize,
            height: dotSize,
            background: color,
          }}
        />
        {/* Label */}
        <span
          className="text-[11px] font-medium truncate"
          style={{ color: 'var(--foreground)' }}
        >
          {label}
        </span>
      </div>

      <Handle type="target" position={Position.Top} className="!opacity-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0 !w-0 !h-0" />
    </div>
  )
}

export const CompactPillNode = memo(CompactPillNodeInner)
