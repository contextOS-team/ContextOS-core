/**
 * ELK force-directed layout engine.
 *
 * Converts React Flow nodes/edges into an ELK graph, runs the force layout,
 * and maps computed positions back. Uses dynamic import for tree-shaking.
 */

import type { Node, Edge } from '@xyflow/react'
import { NODE_DIMENSIONS } from './constants'
import type { ZoomTier } from './types'

/**
 * Compute node positions using ELK's force-directed algorithm.
 *
 * @param nodes - React Flow nodes (positions will be overwritten)
 * @param edges - React Flow edges (used for layout constraints)
 * @param tier  - Current zoom tier (determines node dimensions)
 * @returns Nodes with computed x/y positions
 */
export async function computeElkLayout<N extends Node = Node>(
  nodes: N[],
  edges: Edge[],
  tier: ZoomTier = 'compact'
): Promise<N[]> {
  // Dynamic import for tree-shaking — ELK is ~200 KB
  const ELK = (await import('elkjs/lib/elk.bundled.js')).default
  const elk = new ELK()

  const dims = NODE_DIMENSIONS[tier]

  const elkGraph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'org.eclipse.elk.force',
      'elk.force.temperature': '0.001',
      'elk.spacing.nodeNode': '80',
    },
    children: nodes.map((node) => ({
      id: node.id,
      width: dims.width,
      height: dims.height,
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  }

  const layoutResult = await elk.layout(elkGraph)

  const positionMap = new Map<string, { x: number; y: number }>()
  for (const child of layoutResult.children ?? []) {
    positionMap.set(child.id, { x: child.x ?? 0, y: child.y ?? 0 })
  }

  return nodes.map((node): N => {
    const pos = positionMap.get(node.id)
    return {
      ...node,
      position: pos ?? node.position,
    }
  })
}
