'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { GraphNodeData } from '../types'
import { ENTITY_COLORS } from '../constants'
import { ENTITY_SHAPE } from '../utils'

type GlowDotNodeType = Node<GraphNodeData, 'dot'>

/** Derive dot size and glow intensity from connection count. */
function getDotSizeFromConnections(count: number, entityType?: string) {
  // Person nodes are hubs — render them significantly larger
  if (entityType === 'Person') {
    if (count >= 10) return { size: 48, glowSpread: '0 0 32px 10px', glowOpacity: 65 }
    if (count >= 3) return { size: 40, glowSpread: '0 0 24px 8px', glowOpacity: 60 }
    return { size: 32, glowSpread: '0 0 16px 5px', glowOpacity: 55 }
  }
  if (count >= 8) return { size: 28, glowSpread: '0 0 18px 5px', glowOpacity: 55 }
  if (count >= 3) return { size: 22, glowSpread: '0 0 12px 3px', glowOpacity: 48 }
  return { size: 16, glowSpread: '0 0 8px 2px', glowOpacity: 40 }
}

function GlowDotNodeInner({ data }: NodeProps<GlowDotNodeType>) {
  const color = ENTITY_COLORS[data.entityType] ?? 'var(--muted-foreground)'
  const connCount = data.connectedCount ?? 0
  const { size, glowSpread, glowOpacity } = getDotSizeFromConnections(connCount, data.entityType)
  const isHovered = data.isHovered ?? false

  const rootGlow = data.isRoot ? '0 0 24px 8px' : glowSpread
  const glowColor = `color-mix(in oklch, ${color} ${data.isRoot ? 70 : glowOpacity}%, transparent)`

  // Pulse on hover — wider glow
  const hoverGlowColor = `color-mix(in oklch, ${color} ${Math.min((data.isRoot ? 70 : glowOpacity) + 15, 85)}%, transparent)`
  const boxShadow = isHovered
    ? `${rootGlow} ${glowColor}, 0 0 28px 10px ${hoverGlowColor}`
    : `${rootGlow} ${glowColor}`

  const dotShape = ENTITY_SHAPE[data.entityType] === 'diamond' ? 'diamond' : 'circle'
  const isDiamond = dotShape === 'diamond'

  return (
    <div
      className="relative transition-all duration-200"
      style={{ opacity: data.isDimmed ? 0.3 : 1 }}
      title={data.name}
    >
      <div
        className="transition-shadow duration-700 ease-in-out"
        style={{
          width: size,
          height: size,
          background: color,
          boxShadow,
          borderRadius: isDiamond ? 2 : '50%',
          transform: isDiamond ? 'rotate(45deg)' : undefined,
          // Subtle pulse animation on hover
          animation: isHovered ? 'glow-dot-pulse 1.8s ease-in-out infinite' : undefined,
        }}
      />

      <Handle type="target" position={Position.Top} className="!opacity-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0 !w-0 !h-0" />
    </div>
  )
}

export const GlowDotNode = memo(GlowDotNodeInner)
