import type { EntityType, GraphNodeData } from './types'

// ---------------------------------------------------------------------------
// Hidden properties — internal metadata never shown to users
// ---------------------------------------------------------------------------

export const HIDDEN_NODE_PROPERTIES = new Set([
  'status', 'platform', 'username', 'team_prefix', 'identifier',
  'source_type', 'source_id', 'fingerprint', 'workspace_id',
  'resolved_from', 'sha', 'short_sha',
])

// ---------------------------------------------------------------------------
// Shape system — shared across all node zoom tiers
// ---------------------------------------------------------------------------

export type ShapeKind = 'diamond' | 'circle' | 'rounded-rect' | 'hexagon'

export const ENTITY_SHAPE: Record<EntityType, ShapeKind> = {
  Ticket: 'diamond',
  Person: 'circle',
  Decision: 'hexagon',
  PR: 'rounded-rect',
  Message: 'rounded-rect',
  SlackThread: 'rounded-rect',
  Code: 'rounded-rect',
  CodeChunk: 'rounded-rect',
  NotionPage: 'rounded-rect',
  Meeting: 'circle',
}

export function getShapeStyle(shape: ShapeKind, size: number): React.CSSProperties {
  const base: React.CSSProperties = { width: size, height: size }
  switch (shape) {
    case 'circle':
      return { ...base, borderRadius: '50%' }
    case 'diamond':
      return { ...base, clipPath: 'polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)' }
    case 'hexagon':
      return { ...base, clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)' }
    case 'rounded-rect':
      return { ...base, borderRadius: 8 }
  }
}

// ---------------------------------------------------------------------------
// External URLs
// ---------------------------------------------------------------------------

export function getEntityExternalUrl(node: GraphNodeData): string | null {
  const p = node.properties

  if (node.entityType === 'Ticket') {
    const identifier = (p.identifier as string) || node.name
    if (identifier && /^[A-Z]+-\d+$/.test(identifier)) {
      return `https://linear.app/issue/${identifier}`
    }
  }

  if (node.entityType === 'PR') {
    if (p.url && typeof p.url === 'string') return p.url
    if (p.html_url && typeof p.html_url === 'string') return p.html_url
  }

  if (node.entityType === 'NotionPage') {
    if (p.url && typeof p.url === 'string') return p.url
    if (p.notion_url && typeof p.notion_url === 'string') return p.notion_url
  }

  if (node.entityType === 'SlackThread') {
    if (p.permalink && typeof p.permalink === 'string') return p.permalink
  }

  return null
}
