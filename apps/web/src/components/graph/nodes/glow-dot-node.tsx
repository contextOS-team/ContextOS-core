'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { GraphNodeData } from '../types'
import { ENTITY_COLORS } from '../constants'

type GlowDotNodeType = Node<GraphNodeData, 'dot'>

function GlowDotNodeInner({ data }: NodeProps<GlowDotNodeType>) {
  const color = ENTITY_COLORS[data.entityType] ?? 'var(--muted-foreground)'

  const glowRadius = data.isRoot ? '0 0 16px 4px' : '0 0 8px 2px'
  const glowColor = `color-mix(in oklch, ${color} 50%, transparent)`

  return (
    <div
      className="relative transition-opacity duration-300"
      style={{ opacity: data.isDimmed ? 0.3 : 1 }}
      title={data.name}
    >
      <div
        className="rounded-full"
        style={{
          width: 24,
          height: 24,
          background: color,
          boxShadow: `${glowRadius} ${glowColor}`,
        }}
      />

      <Handle type="target" position={Position.Top} className="!opacity-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0 !w-0 !h-0" />
    </div>
  )
}

export const GlowDotNode = memo(GlowDotNodeInner)
