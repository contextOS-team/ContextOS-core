/**
 * Graph visualization type contracts.
 *
 * Defines node/edge data shapes, entity type enums, and zoom tier helpers
 * consumed by all graph components.
 */

// ---------------------------------------------------------------------------
// Entity types
// ---------------------------------------------------------------------------

export type EntityType =
  | 'Ticket'
  | 'Person'
  | 'Decision'
  | 'PR'
  | 'Message'
  | 'Code'
  | 'NotionPage'
  | 'Meeting'

// ---------------------------------------------------------------------------
// Zoom tiers
// ---------------------------------------------------------------------------

export type ZoomTier = 'full' | 'compact' | 'dot'

/** Determine the visual zoom tier from the current viewport zoom level. */
export function getZoomTier(zoom: number): ZoomTier {
  if (zoom > 1.5) return 'full'
  if (zoom >= 0.6) return 'compact'
  return 'dot'
}

// ---------------------------------------------------------------------------
// Node data
// ---------------------------------------------------------------------------

export interface GraphNodeData {
  id: string
  entityType: EntityType
  name: string
  depth: number
  properties: Record<string, unknown>
  /** True for the depth-0 root ticket node */
  isRoot?: boolean
  isSelected?: boolean
  isHovered?: boolean
  /** True when another node is hovered and this node is NOT connected */
  isDimmed?: boolean
  /** Number of edges touching this node */
  connectedCount?: number
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// Edge data
// ---------------------------------------------------------------------------

export interface GraphEdgeData {
  relationshipType: string
  properties: Record<string, unknown>
  isHighlighted?: boolean
  [key: string]: unknown
}

// ---------------------------------------------------------------------------
// API response (mirrors backend GraphNeighborhoodResponse, snake_case)
// ---------------------------------------------------------------------------

export interface GraphNeighborhoodResponse {
  ticket_identifier: string
  depth: number
  node_count: number
  edge_count: number
  truncated: boolean
  total_available: number | null
  nodes: Array<{
    id: string
    entity_type: string
    name: string
    depth: number
    properties: Record<string, unknown>
  }>
  edges: Array<{
    source: string
    target: string
    relationship_type: string
    properties: Record<string, unknown>
  }>
}

export interface WorkspaceGraphResponse {
  node_count: number
  edge_count: number
  truncated: boolean
  total_available: number
  nodes: Array<{
    id: string
    entity_type: string
    name: string
    depth: number
    properties: Record<string, unknown>
  }>
  edges: Array<{
    source: string
    target: string
    relationship_type: string
    properties: Record<string, unknown>
  }>
}
