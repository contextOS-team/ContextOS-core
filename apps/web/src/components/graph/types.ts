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
  | 'CodeChunk'
  | 'NotionPage'
  | 'SlackThread'
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
// Shared API element types (snake_case, mirrors backend response shapes)
// ---------------------------------------------------------------------------

export interface ApiNode {
  id: string
  entity_type: string
  name: string
  depth: number
  properties: Record<string, unknown>
  created_at?: string | null
  updated_at?: string | null
}

export interface ApiEdge {
  source: string
  target: string
  relationship_type: string
  properties: Record<string, unknown>
}

// ---------------------------------------------------------------------------
// API response (mirrors backend GraphNeighborhoodResponse)
// ---------------------------------------------------------------------------

export interface GraphNeighborhoodResponse {
  ticket_identifier: string
  depth: number
  node_count: number
  edge_count: number
  truncated: boolean
  total_available: number | null
  nodes: ApiNode[]
  edges: ApiEdge[]
}

export interface WorkspaceGraphResponse {
  node_count: number
  edge_count: number
  truncated: boolean
  total_available: number
  nodes: ApiNode[]
  edges: ApiEdge[]
}

// ---------------------------------------------------------------------------
// Lens types
// ---------------------------------------------------------------------------

export type GraphLens = 'my_work' | 'sprint' | 'blocked' | 'browse'

export interface TicketCluster {
  ticket_identifier: string
  ticket_node_id: string
  ticket_name: string
  ticket_state: string | null
  ticket_priority: number | null
  nodes: ApiNode[]
  edges: ApiEdge[]
}

export interface LensGraphResponse {
  lens: 'my_work' | 'sprint' | 'blocked'
  clusters: TicketCluster[]
  all_nodes: ApiNode[]
  all_edges: ApiEdge[]
  node_count: number
  edge_count: number
  truncated: boolean
  sprint_name?: string | null
  sprint_progress?: number | null
}
