'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  MiniMap,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
  MarkerType,
  type Node,
  type Edge,
  type NodeMouseHandler,
  type Viewport,
  type NodeTypes,
  type EdgeTypes,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { cn } from '@/lib/utils'
import { Skeleton } from '@/components/ui/skeleton'
import { Button } from '@/components/ui/button'
import { fetchGraphNeighborhood, fetchWorkspaceGraph } from '@/lib/api'
import type {
  EntityType,
  GraphNodeData,
  GraphEdgeData,
  ZoomTier,
} from './types'
import { getZoomTier } from './types'
import { ENTITY_COLORS } from './constants'
import { computeElkLayout } from './elk-layout'
import { FullDetailNode } from './nodes/full-detail-node'
import { CompactPillNode } from './nodes/compact-pill-node'
import { GlowDotNode } from './nodes/glow-dot-node'
import { StyledEdge } from './edges/styled-edge'
import { GraphControls } from './graph-controls'
import { NodePopover } from './node-popover'
import { DetailSidebar, type ConnectionInfo } from './detail-sidebar'

// ---------------------------------------------------------------------------
// Node / edge type registries (stable references)
// ---------------------------------------------------------------------------

const NODE_TYPES: NodeTypes = {
  full: FullDetailNode,
  compact: CompactPillNode,
  dot: GlowDotNode,
}

const EDGE_TYPES: EdgeTypes = {
  default: StyledEdge,
}

// ---------------------------------------------------------------------------
// Inner component (needs ReactFlowProvider above it)
// ---------------------------------------------------------------------------

function GraphExplorerInner({
  ticketIdentifier,
  focusNodeId,
  className,
}: {
  ticketIdentifier?: string
  focusNodeId?: string
  className?: string
}) {
  const reactFlow = useReactFlow()

  // State
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<GraphNodeData>>([])
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge<GraphEdgeData>>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [popoverNodeId, setPopoverNodeId] = useState<string | null>(null)
  const [expandedNodeId, setExpandedNodeId] = useState<string | null>(null)
  const [popoverPosition, setPopoverPosition] = useState<{ x: number; y: number }>({ x: 0, y: 0 })
  const [zoomTier, setZoomTier] = useState<ZoomTier>('compact')
  const [hiddenEntityTypes, setHiddenEntityTypes] = useState<Set<EntityType>>(new Set())
  const [showMiniMap, setShowMiniMap] = useState(false)

  // Keep a mutable ref for edges so hover callbacks always have the latest
  const edgesRef = useRef(edges)
  edgesRef.current = edges
  const nodesRef = useRef(nodes)
  nodesRef.current = nodes

  // -----------------------------------------------------------------------
  // Data fetch + layout
  // -----------------------------------------------------------------------

  const transformAndLayout = useCallback(
    async (
      apiNodes: Array<{ id: string; entity_type: string; name: string; depth: number; properties: Record<string, unknown> }>,
      apiEdges: Array<{ source: string; target: string; relationship_type: string; properties: Record<string, unknown> }>,
      focusId?: string,
    ) => {
      // Transform API nodes -> React Flow nodes
      const rfNodes: Node<GraphNodeData>[] = apiNodes.map((n) => ({
        id: n.id,
        type: 'compact' as const,
        position: { x: 0, y: 0 },
        data: {
          id: n.id,
          entityType: n.entity_type as EntityType,
          name: n.name,
          depth: n.depth,
          properties: n.properties,
          isRoot: n.depth === 0,
          connectedCount: 0,
        },
      }))

      // Transform API edges -> React Flow edges
      const rfEdges: Edge<GraphEdgeData>[] = apiEdges.map((e, i) => ({
        id: `e-${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        type: 'default',
        markerEnd: { type: MarkerType.ArrowClosed, width: 16, height: 16 },
        data: {
          relationshipType: e.relationship_type,
          properties: e.properties,
        },
      }))

      // Compute connected counts
      const countMap = new Map<string, number>()
      for (const e of rfEdges) {
        countMap.set(e.source, (countMap.get(e.source) ?? 0) + 1)
        countMap.set(e.target, (countMap.get(e.target) ?? 0) + 1)
      }
      for (const n of rfNodes) {
        n.data.connectedCount = countMap.get(n.id) ?? 0
      }

      // Run ELK layout
      const positioned = await computeElkLayout(rfNodes, rfEdges, 'compact')
      setNodes(positioned)
      setEdges(rfEdges)

      // Fit view, then optionally focus on a specific node
      setTimeout(() => {
        reactFlow.fitView({ padding: 0.2 })
        if (focusId) {
          const target = positioned.find((n) => n.id === focusId)
          if (target) {
            setTimeout(() => {
              reactFlow.setCenter(
                target.position.x + (target.measured?.width ?? 60) / 2,
                target.position.y + (target.measured?.height ?? 30) / 2,
                { zoom: 1.2, duration: 500 }
              )
            }, 100)
          }
        }
      }, 50)
    },
    [reactFlow, setNodes, setEdges]
  )

  const fetchData = useCallback(
    async (identifier?: string, focusId?: string) => {
      setLoading(true)
      setError(null)
      try {
        if (identifier) {
          const data = await fetchGraphNeighborhood(identifier)
          await transformAndLayout(data.nodes, data.edges, focusId)
        } else {
          const data = await fetchWorkspaceGraph()
          await transformAndLayout(data.nodes, data.edges, focusId)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load graph')
      } finally {
        setLoading(false)
      }
    },
    [transformAndLayout]
  )

  useEffect(() => {
    fetchData(ticketIdentifier, focusNodeId)
  }, [ticketIdentifier, focusNodeId, fetchData])

  // -----------------------------------------------------------------------
  // Zoom tier tracking
  // -----------------------------------------------------------------------

  const handleViewportChange = useCallback(
    (viewport: Viewport) => {
      const newTier = getZoomTier(viewport.zoom)
      if (newTier !== zoomTier) {
        setZoomTier(newTier)
        // Update node types to match new tier
        setNodes((nds) =>
          nds.map((n) => ({
            ...n,
            type: newTier,
          }))
        )
      }
    },
    [zoomTier, setNodes]
  )

  // -----------------------------------------------------------------------
  // Hover interaction — dim unconnected, highlight connected edges
  // -----------------------------------------------------------------------

  const handleNodeMouseEnter: NodeMouseHandler<Node<GraphNodeData>> = useCallback(
    (_event, node) => {
      setHoveredNodeId(node.id)

      // Find connected node IDs
      const connectedNodeIds = new Set<string>()
      connectedNodeIds.add(node.id)
      for (const e of edgesRef.current) {
        if (e.source === node.id) connectedNodeIds.add(e.target)
        if (e.target === node.id) connectedNodeIds.add(e.source)
      }

      // Dim unconnected nodes
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: {
            ...n.data,
            isDimmed: !connectedNodeIds.has(n.id),
            isHovered: n.id === node.id,
          },
        }))
      )

      // Highlight connected edges
      setEdges((eds) =>
        eds.map((e) => ({
          ...e,
          data: {
            ...e.data!,
            isHighlighted: e.source === node.id || e.target === node.id,
          },
        }))
      )
    },
    [setNodes, setEdges]
  )

  const handleNodeMouseLeave: NodeMouseHandler<Node<GraphNodeData>> = useCallback(() => {
    setHoveredNodeId(null)

    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          isDimmed: false,
          isHovered: false,
        },
      }))
    )

    setEdges((eds) =>
      eds.map((e) => ({
        ...e,
        data: {
          ...e.data!,
          isHighlighted: false,
        },
      }))
    )
  }, [setNodes, setEdges])

  // -----------------------------------------------------------------------
  // Click interaction — popover + sidebar
  // -----------------------------------------------------------------------

  const handleNodeClick: NodeMouseHandler<Node<GraphNodeData>> = useCallback(
    (_event, node) => {
      setSelectedNodeId(node.id)
      setPopoverNodeId(node.id)

      // Compute screen position for popover
      const screenPos = reactFlow.flowToScreenPosition({
        x: node.position.x + (node.measured?.width ?? 60) / 2,
        y: node.position.y + (node.measured?.height ?? 30),
      })

      // Get the ReactFlow wrapper's bounding rect to make position relative
      const wrapper = document.querySelector('.react-flow')
      const rect = wrapper?.getBoundingClientRect()
      if (rect) {
        setPopoverPosition({
          x: screenPos.x - rect.left,
          y: screenPos.y - rect.top,
        })
      } else {
        setPopoverPosition(screenPos)
      }

      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: {
            ...n.data,
            isSelected: n.id === node.id,
          },
        }))
      )
    },
    [setNodes, reactFlow]
  )

  const handleClosePopover = useCallback(() => {
    setPopoverNodeId(null)
  }, [])

  const handleCloseSidebar = useCallback(() => {
    setExpandedNodeId(null)
  }, [])

  const handleExpand = useCallback(() => {
    setExpandedNodeId(selectedNodeId)
    setPopoverNodeId(null)
  }, [selectedNodeId])

  const handleNavigateToNode = useCallback(
    (nodeId: string) => {
      setSelectedNodeId(nodeId)
      setExpandedNodeId(nodeId)
      setPopoverNodeId(null)

      // Find the target node and pan to it
      const targetNode = nodesRef.current.find((n) => n.id === nodeId)
      if (targetNode) {
        reactFlow.setCenter(
          targetNode.position.x + (targetNode.measured?.width ?? 60) / 2,
          targetNode.position.y + (targetNode.measured?.height ?? 30) / 2,
          { zoom: 1.2, duration: 500 }
        )
      }

      // Update selection highlighting
      setNodes((nds) =>
        nds.map((n) => ({
          ...n,
          data: {
            ...n.data,
            isSelected: n.id === nodeId,
          },
        }))
      )
    },
    [reactFlow, setNodes]
  )

  const handlePaneClick = useCallback(() => {
    setPopoverNodeId(null)
    setExpandedNodeId(null)
    setSelectedNodeId(null)
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, isSelected: false },
      }))
    )
  }, [setNodes])

  // -----------------------------------------------------------------------
  // Compute connections for detail sidebar
  // -----------------------------------------------------------------------

  const getNodeData = useCallback(
    (nodeId: string): GraphNodeData | null => {
      const node = nodesRef.current.find((n) => n.id === nodeId)
      return node?.data ?? null
    },
    []
  )

  const getConnections = useCallback(
    (nodeId: string): ConnectionInfo[] => {
      const conns: ConnectionInfo[] = []
      for (const edge of edgesRef.current) {
        if (edge.source === nodeId) {
          const targetNode = nodesRef.current.find((n) => n.id === edge.target)
          if (targetNode) {
            conns.push({
              node: targetNode.data,
              edgeType: edge.data?.relationshipType ?? 'related',
              direction: 'outgoing',
            })
          }
        } else if (edge.target === nodeId) {
          const sourceNode = nodesRef.current.find((n) => n.id === edge.source)
          if (sourceNode) {
            conns.push({
              node: sourceNode.data,
              edgeType: edge.data?.relationshipType ?? 'related',
              direction: 'incoming',
            })
          }
        }
      }
      return conns
    },
    []
  )

  // -----------------------------------------------------------------------
  // Entity type filtering
  // -----------------------------------------------------------------------

  const visibleNodes = useMemo(() => {
    if (hiddenEntityTypes.size === 0) return nodes
    return nodes.map((n) => ({
      ...n,
      hidden: hiddenEntityTypes.has(n.data.entityType),
    }))
  }, [nodes, hiddenEntityTypes])

  const visibleEdges = useMemo(() => {
    if (hiddenEntityTypes.size === 0) return edges
    const hiddenNodeIds = new Set(
      nodes
        .filter((n) => hiddenEntityTypes.has(n.data.entityType))
        .map((n) => n.id)
    )
    return edges.filter(
      (e) => !hiddenNodeIds.has(e.source) && !hiddenNodeIds.has(e.target)
    )
  }, [edges, nodes, hiddenEntityTypes])

  // -----------------------------------------------------------------------
  // Entity counts for filter chips
  // -----------------------------------------------------------------------

  const entityCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const n of nodes) {
      const type = n.data.entityType
      counts[type] = (counts[type] ?? 0) + 1
    }
    return counts
  }, [nodes])

  // -----------------------------------------------------------------------
  // Current popover/sidebar node data
  // -----------------------------------------------------------------------

  const popoverNode = popoverNodeId ? getNodeData(popoverNodeId) : null
  const expandedNode = expandedNodeId ? getNodeData(expandedNodeId) : null
  const expandedConnections = expandedNodeId ? getConnections(expandedNodeId) : []

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <div className={cn('relative h-full w-full', className)}>
      <ReactFlow
        nodes={visibleNodes}
        edges={visibleEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={NODE_TYPES}
        edgeTypes={EDGE_TYPES}
        onViewportChange={handleViewportChange}
        onNodeMouseEnter={handleNodeMouseEnter}
        onNodeMouseLeave={handleNodeMouseLeave}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        fitView
        colorMode="dark"
        minZoom={0.1}
        maxZoom={4}
        proOptions={{ hideAttribution: true }}
      >
        {showMiniMap && (
          <MiniMap
            nodeColor={(node) => {
              const data = node.data as GraphNodeData
              return ENTITY_COLORS[data.entityType] ?? 'var(--muted-foreground)'
            }}
            maskColor="rgba(0,0,0,0.7)"
            style={{ background: 'var(--card)' }}
          />
        )}
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
      </ReactFlow>

      <GraphControls
        onZoomIn={() => reactFlow.zoomIn()}
        onZoomOut={() => reactFlow.zoomOut()}
        onFitView={() => reactFlow.fitView({ padding: 0.2 })}
        onToggleMiniMap={() => setShowMiniMap((prev) => !prev)}
        showMiniMap={showMiniMap}
        entityCounts={entityCounts}
        hiddenEntityTypes={hiddenEntityTypes}
        onFilterChange={setHiddenEntityTypes}
      />

      {/* Node popover */}
      {popoverNode && (
        <NodePopover
          node={popoverNode}
          position={popoverPosition}
          edges={edges}
          onClose={handleClosePopover}
          onExpand={handleExpand}
        />
      )}

      {/* Detail sidebar */}
      {expandedNode && (
        <DetailSidebar
          node={expandedNode}
          connections={expandedConnections}
          onClose={handleCloseSidebar}
          onNavigateToNode={handleNavigateToNode}
        />
      )}

      {/* Loading skeleton */}
      {loading && <GraphSkeleton />}

      {/* Error state */}
      {error && (
        <GraphError
          message={error}
          onRetry={() => fetchData(ticketIdentifier, focusNodeId)}
        />
      )}

      {/* Empty state */}
      {!loading && !error && nodes.length === 0 && <GraphEmpty />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components: Loading, Error, Empty states
// ---------------------------------------------------------------------------

function GraphSkeleton() {
  return (
    <div className="absolute inset-0 z-20 flex items-center justify-center bg-[var(--bg)]/80 backdrop-blur-sm">
      <div className="relative h-48 w-64">
        {/* Pulsing dots */}
        <Skeleton className="absolute left-1/2 top-8 h-6 w-6 -translate-x-1/2 rounded-full" />
        <Skeleton className="absolute left-8 top-24 h-4 w-4 rounded-full" />
        <Skeleton className="absolute right-8 top-20 h-4 w-4 rounded-full" />
        <Skeleton className="absolute left-16 bottom-4 h-3 w-3 rounded-full" />
        <Skeleton className="absolute right-16 bottom-8 h-3 w-3 rounded-full" />
        {/* Connecting lines */}
        <svg className="absolute inset-0 h-full w-full opacity-20">
          <line x1="128" y1="44" x2="40" y2="104" stroke="var(--border)" strokeWidth="1" />
          <line x1="128" y1="44" x2="216" y2="96" stroke="var(--border)" strokeWidth="1" />
          <line x1="40" y1="104" x2="72" y2="172" stroke="var(--border)" strokeWidth="1" />
          <line x1="216" y1="96" x2="184" y2="160" stroke="var(--border)" strokeWidth="1" />
        </svg>
        <p
          className="absolute -bottom-8 left-1/2 -translate-x-1/2 text-xs whitespace-nowrap"
          style={{ color: 'var(--muted-foreground)' }}
        >
          Loading graph...
        </p>
      </div>
    </div>
  )
}

function GraphError({
  message,
  onRetry,
}: {
  message: string
  onRetry: () => void
}) {
  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-3 bg-[var(--bg)]/80 backdrop-blur-sm">
      <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
        {message}
      </p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Retry
      </Button>
    </div>
  )
}

function GraphEmpty() {
  return (
    <div className="absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 bg-[var(--bg)]/80 backdrop-blur-sm">
      <p className="text-sm" style={{ color: 'var(--muted-foreground)' }}>
        No graph data yet.
      </p>
      <p className="text-xs" style={{ color: 'var(--muted-foreground)', opacity: 0.6 }}>
        Generate context pages to build the knowledge graph.
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Public export — wraps with ReactFlowProvider
// ---------------------------------------------------------------------------

export function GraphExplorer({
  ticketIdentifier,
  focusNodeId,
  className,
}: {
  ticketIdentifier?: string
  focusNodeId?: string
  className?: string
}) {
  return (
    <ReactFlowProvider>
      <GraphExplorerInner
        ticketIdentifier={ticketIdentifier}
        focusNodeId={focusNodeId}
        className={className}
      />
    </ReactFlowProvider>
  )
}
