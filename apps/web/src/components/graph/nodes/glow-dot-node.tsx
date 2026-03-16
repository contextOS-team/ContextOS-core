'use client'

import { memo } from 'react'
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react'
import type { EntityType, GraphNodeData } from '../types'
import { ENTITY_COLORS } from '../constants'

type GlowDotNodeType = Node<GraphNodeData, 'dot'>

// ---------------------------------------------------------------------------
// Shape-aware dot styles — diamonds get a rotated square, circles stay round
// ---------------------------------------------------------------------------

type DotShape = 'circle' | 'diamond'

const DOT_SHAPE: Partial<Record<EntityType, DotShape>> = {
  Ticket: 'diamond',
}

/** Derive dot size and glow intensity from connection count. */
function getDotSizeFromConnections(count: number) {
  if (count >= 5) return { size: 32, glowSpread: '0 0 20px 6px', glowOpacity: 60 }
  if (count >= 2) return { size: 24, glowSpread: '0 0 12px 3px', glowOpacity: 50 }
  return { size: 16, glowSpread: '0 0 8px 2px', glowOpacity: 40 }
}

function GlowDotNodeInner({ data }: NodeProps<GlowDotNodeType>) {
  const color = ENTITY_COLORS[data.entityType] ?? 'var(--muted-foreground)'
  const connCount = data.connectedCount ?? 0
  const { size, glowSpread, glowOpacity } = getDotSizeFromConnections(connCount)
  const isHovered = data.isHovered ?? false

  const rootGlow = data.isRoot ? '0 0 24px 8px' : glowSpread
  const glowColor = `color-mix(in oklch, ${color} ${data.isRoot ? 70 : glowOpacity}%, transparent)`

  // Pulse on hover — wider glow
  const hoverGlowColor = `color-mix(in oklch, ${color} ${Math.min((data.isRoot ? 70 : glowOpacity) + 15, 85)}%, transparent)`
  const boxShadow = isHovered
    ? `${rootGlow} ${glowColor}, 0 0 28px 10px ${hoverGlowColor}`
    : `${rootGlow} ${glowColor}`

  const dotShape = DOT_SHAPE[data.entityType] ?? 'circle'
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

      {/* Keyframes injected once via style tag — React deduplicates by content */}
      <style>{`
        @keyframes glow-dot-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
      `}</style>
    </div>
  )
}

export const GlowDotNode = memo(GlowDotNodeInner)
