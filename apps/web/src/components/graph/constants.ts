/**
 * Graph visualization constants.
 *
 * Entity colors (OKLCH), icons (Lucide), edge styles, zoom thresholds,
 * and node dimensions for each zoom tier.
 */

import type { EntityType } from './types'
import {
  CheckCircle2,
  User,
  Lightbulb,
  GitPullRequest,
  MessageSquare,
  Code2,
  FileText,
  Video,
  Hash,
  Puzzle,
  type LucideIcon,
} from 'lucide-react'

// ---------------------------------------------------------------------------
// Entity colors — OKLCH tuned for equal perceptual brightness on dark bg
// Hue separation >= 40 degrees between adjacent types
// ---------------------------------------------------------------------------

export const ENTITY_COLORS: Record<EntityType, string> = {
  Ticket: 'oklch(0.72 0.18 280)',      // violet
  Person: 'oklch(0.72 0.18 350)',      // pink/rose
  Decision: 'oklch(0.72 0.18 85)',     // amber
  PR: 'oklch(0.72 0.18 145)',          // green
  Message: 'oklch(0.72 0.18 240)',     // blue
  Code: 'oklch(0.72 0.18 185)',        // teal
  CodeChunk: 'oklch(0.72 0.14 185)',   // teal (slightly muted)
  NotionPage: 'oklch(0.72 0.10 240)',  // cool gray-blue (lower chroma)
  SlackThread: 'oklch(0.72 0.16 320)', // magenta
  Meeting: 'oklch(0.72 0.18 55)',      // orange
}

// ---------------------------------------------------------------------------
// Entity icons — Lucide components matching SOURCE_TYPE_CONFIG patterns
// ---------------------------------------------------------------------------

export const ENTITY_ICONS: Record<EntityType, LucideIcon> = {
  Ticket: CheckCircle2,
  Person: User,
  Decision: Lightbulb,
  PR: GitPullRequest,
  Message: MessageSquare,
  Code: Code2,
  CodeChunk: Puzzle,
  NotionPage: FileText,
  SlackThread: Hash,
  Meeting: Video,
}

// ---------------------------------------------------------------------------
// Edge styles — keyed by relationship type pattern
// ---------------------------------------------------------------------------

export interface EdgeStyleConfig {
  strokeDasharray: string
  strokeWidth: number
  color: string
  hasArrow: boolean
}

export const EDGE_STYLES: Record<string, EdgeStyleConfig> = {
  authored: {
    strokeDasharray: 'none',
    strokeWidth: 1.5,
    color: 'var(--muted-foreground)',
    hasArrow: true,
  },
  created: {
    strokeDasharray: 'none',
    strokeWidth: 1.5,
    color: 'var(--muted-foreground)',
    hasArrow: true,
  },
  mentions: {
    strokeDasharray: '6 3',
    strokeWidth: 1.5,
    color: 'var(--muted-foreground)',
    hasArrow: true,
  },
  references: {
    strokeDasharray: '6 3',
    strokeWidth: 1.5,
    color: 'var(--muted-foreground)',
    hasArrow: true,
  },
  blocks: {
    strokeDasharray: 'none',
    strokeWidth: 2.5,
    color: 'oklch(0.65 0.18 25)',
    hasArrow: true,
  },
  depends_on: {
    strokeDasharray: 'none',
    strokeWidth: 2.5,
    color: 'oklch(0.65 0.18 25)',
    hasArrow: true,
  },
  default: {
    strokeDasharray: 'none',
    strokeWidth: 1,
    color: 'var(--border)',
    hasArrow: false,
  },
}

/**
 * Resolve an edge style from a relationship type string.
 * Matches via includes() against known patterns, falling back to default.
 */
export function getEdgeStyle(relationshipType: string): EdgeStyleConfig {
  const lower = relationshipType.toLowerCase()
  if (lower.includes('authored') || lower.includes('created'))
    return EDGE_STYLES.authored
  if (lower.includes('mention') || lower.includes('reference'))
    return EDGE_STYLES.mentions
  if (lower.includes('block') || lower.includes('depends'))
    return EDGE_STYLES.blocks
  return EDGE_STYLES.default
}

// ---------------------------------------------------------------------------
// Zoom thresholds
// ---------------------------------------------------------------------------

export const ZOOM_THRESHOLDS = {
  full: 1.5,
  compact: 0.6,
} as const

// ---------------------------------------------------------------------------
// Node dimensions per zoom tier
// ---------------------------------------------------------------------------

export const NODE_DIMENSIONS = {
  full: { width: 220, height: 80 },
  compact: { width: 120, height: 32 },
  dot: { width: 24, height: 24 },
} as const
