'use client'

import { memo, useState } from 'react'
import {
  BaseEdge,
  getBezierPath,
  EdgeLabelRenderer,
  type EdgeProps,
  type Edge,
} from '@xyflow/react'
import type { GraphEdgeData } from '../types'
import { getEdgeStyle } from '../constants'

type StyledEdgeType = Edge<GraphEdgeData, 'default'>

function StyledEdgeInner({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: EdgeProps<StyledEdgeType>) {
  const [hovered, setHovered] = useState(false)
  const relationshipType = data?.relationshipType ?? 'related_to'
  const style = getEdgeStyle(relationshipType)
  const isHighlighted = data?.isHighlighted ?? false

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  })

  const effectiveOpacity = isHighlighted || hovered ? 1 : 0.3
  const effectiveWidth = isHighlighted || hovered ? style.strokeWidth + 0.5 : style.strokeWidth

  // Build marker end — use provided one if hasArrow, otherwise none
  const effectiveMarkerEnd = style.hasArrow ? markerEnd : undefined

  return (
    <>
      {/* Invisible wider path for hover detection */}
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={20}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      />
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: style.color,
          strokeWidth: effectiveWidth,
          strokeDasharray: style.strokeDasharray === 'none' ? undefined : style.strokeDasharray,
          opacity: effectiveOpacity,
          transition: 'opacity 0.2s, stroke-width 0.2s',
        }}
        markerEnd={effectiveMarkerEnd}
      />
      {/* Floating label on hover */}
      {hovered && (
        <EdgeLabelRenderer>
          <div
            className="pointer-events-none rounded px-1.5 py-0.5 text-[10px] font-medium"
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              background: 'var(--card)',
              color: 'var(--muted-foreground)',
              border: '1px solid var(--border)',
            }}
          >
            {relationshipType}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}

export const StyledEdge = memo(StyledEdgeInner)
