'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { GraphNodeData } from '../types'
import { ENTITY_COLORS } from '../constants'

type CompactPillNodeType = Node<GraphNodeData, 'compact'>

function CompactPillNodeInner({ data }: NodeProps<CompactPillNodeType>) {
  const color = ENTITY_COLORS[data.entityType] ?? 'var(--muted-foreground)'
  const label = data.name.length > 15 ? data.name.slice(0, 14) + '\u2026' : data.name

  return (
    <div
      className="relative transition-opacity duration-300"
      style={{ opacity: data.isDimmed ? 0.3 : 1 }}
    >
      <div
        className="flex items-center gap-1.5 rounded-full border border-[var(--border)] px-2.5 py-1"
        style={{
          width: 120,
          height: 32,
          background: 'var(--elevated)',
        }}
      >
        {/* Colored dot */}
        <span
          className="shrink-0 rounded-full"
          style={{
            width: 8,
            height: 8,
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
