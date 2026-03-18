/**
 * Pure logic extracted from graph-thumbnail.tsx for testability.
 *
 * No React, no JSX — just data transformations and layout math.
 */

import type { ApiNode, ApiEdge } from '@/components/graph/types'

/* ── types ────────────────────────────────────────────────── */

export interface Pos {
  x: number
  y: number
}

/* ── deterministic hash for seeded jitter ─────────────────── */

function hashCode(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0
  }
  return h
}

/* ── force-directed layout ────────────────────────────────── */

export function forceLayout(
  nodes: ApiNode[],
  edges: ApiEdge[],
  width: number,
  height: number,
): Map<string, Pos> {
  // Clamp to 80 nodes — O(n²) simulation is ~6400 pairs at 80, ~250K at 500
  const MAX_NODES = 80
  const clamped = nodes.length > MAX_NODES ? nodes.slice(0, MAX_NODES) : nodes
  const n = clamped.length
  if (n === 0) return new Map()

  // Single node: place at center
  if (n === 1) {
    const result = new Map<string, Pos>()
    result.set(clamped[0].id, { x: width / 2, y: height / 2 })
    return result
  }

  const cx = width / 2
  const cy = height / 2

  // Initialize in a seeded circle for deterministic results
  const pos: { x: number; y: number }[] = clamped.map((node, i) => {
    const angle = (2 * Math.PI * i) / n
    const h = hashCode(node.id)
    const jx = ((h & 0xff) / 255 - 0.5) * 20
    const jy = (((h >> 8) & 0xff) / 255 - 0.5) * 20
    return {
      x: cx + Math.cos(angle) * Math.min(width, height) * 0.3 + jx,
      y: cy + Math.sin(angle) * Math.min(width, height) * 0.3 + jy,
    }
  })

  // Build index lookup
  const idx = new Map<string, number>()
  clamped.forEach((node, i) => idx.set(node.id, i))

  // Parse edges into index pairs
  const edgeIdx = edges
    .map((e) => [idx.get(e.source), idx.get(e.target)] as const)
    .filter((pair): pair is [number, number] => pair[0] !== undefined && pair[1] !== undefined)

  // Spring simulation — O(n²) per iteration, clamped to 80 nodes max
  const repulsion = 4000
  const attraction = 0.02
  const damping = 0.85
  const iterations = 80
  const vx = new Float64Array(n)
  const vy = new Float64Array(n)

  for (let iter = 0; iter < iterations; iter++) {
    // Repulsion between all pairs
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = pos[i].x - pos[j].x
        let dy = pos[i].y - pos[j].y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = repulsion / (dist * dist)
        dx = (dx / dist) * force
        dy = (dy / dist) * force
        vx[i] += dx
        vy[i] += dy
        vx[j] -= dx
        vy[j] -= dy
      }
    }

    // Attraction along edges
    for (const [a, b] of edgeIdx) {
      const dx = pos[b].x - pos[a].x
      const dy = pos[b].y - pos[a].y
      const fx = dx * attraction
      const fy = dy * attraction
      vx[a] += fx
      vy[a] += fy
      vx[b] -= fx
      vy[b] -= fy
    }

    // Centering force
    for (let i = 0; i < n; i++) {
      vx[i] += (cx - pos[i].x) * 0.01
      vy[i] += (cy - pos[i].y) * 0.01
    }

    // Apply velocities with damping
    for (let i = 0; i < n; i++) {
      vx[i] *= damping
      vy[i] *= damping
      pos[i].x += vx[i]
      pos[i].y += vy[i]
    }
  }

  // Fit to viewport with generous padding for labels
  const padX = 45
  const padY = 25
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  for (const p of pos) {
    if (p.x < minX) minX = p.x
    if (p.x > maxX) maxX = p.x
    if (p.y < minY) minY = p.y
    if (p.y > maxY) maxY = p.y
  }
  const rangeX = maxX - minX || 1
  const rangeY = maxY - minY || 1
  const scaleX = (width - padX * 2) / rangeX
  const scaleY = (height - padY * 2) / rangeY
  const scale = Math.min(scaleX, scaleY)

  const result = new Map<string, Pos>()
  const offsetX = (width - rangeX * scale) / 2
  const offsetY = (height - rangeY * scale) / 2
  clamped.forEach((node, i) => {
    result.set(node.id, {
      x: (pos[i].x - minX) * scale + offsetX,
      y: (pos[i].y - minY) * scale + offsetY,
    })
  })

  return result
}

/* ── dynamic SVG height ───────────────────────────────────── */

export function getSvgHeight(nodeCount: number): number {
  if (nodeCount <= 5) return 160
  if (nodeCount <= 10) return 200
  if (nodeCount <= 20) return 240
  return 280
}

/* ── Person node filtering ────────────────────────────────── */

/**
 * Keep only the current user's Person node — drop other people and their edges.
 *
 * Identification strategy:
 * 1. If `userName` is provided, match by name (case-insensitive substring)
 * 2. Fall back to most-connected Person node
 */
export function filterToUserPerson(
  nodes: ApiNode[],
  edges: ApiEdge[],
  userName?: string,
): { nodes: ApiNode[]; edges: ApiEdge[] } {
  const personNodes = nodes.filter((n) => n.entity_type === 'Person')
  if (personNodes.length <= 1) return { nodes, edges }

  let userPerson: ApiNode | undefined

  // Strategy 1: match by name
  if (userName) {
    const lower = userName.toLowerCase()
    userPerson = personNodes.find((n) => n.name.toLowerCase().includes(lower))
      ?? personNodes.find((n) => lower.includes(n.name.toLowerCase()))
  }

  // Strategy 2: fall back to most-connected
  if (!userPerson) {
    const counts = countConnections(edges)
    userPerson = personNodes.reduce((best, n) =>
      (counts.get(n.id) ?? 0) > (counts.get(best.id) ?? 0) ? n : best
    )
  }

  const dropIds = new Set(personNodes.filter((n) => n.id !== userPerson!.id).map((n) => n.id))
  return {
    nodes: nodes.filter((n) => !dropIds.has(n.id)),
    edges: edges.filter((e) => !dropIds.has(e.source) && !dropIds.has(e.target)),
  }
}

/* ── label collision detection ────────────────────────────── */

/**
 * Given node positions and labels, returns a Set of node IDs whose labels
 * should be visible (no overlap). Hub label always wins. Uses a greedy
 * approach: process hub first, then by connection count descending.
 */
export function resolveVisibleLabels(
  nodes: ApiNode[],
  positions: Map<string, Pos>,
  connectionCounts: Map<string, number>,
  hubId: string | null,
  fontSize: number = 9,
): Set<string> {
  // Approximate label bounding box: width ≈ charCount * fontSize * 0.55, height ≈ fontSize * 1.4
  const charWidth = fontSize * 0.55
  const labelHeight = fontSize * 1.4
  const yOffset = 15 // labels are rendered below nodes

  interface Rect { x1: number; y1: number; x2: number; y2: number }

  function getLabelRect(nodeId: string, label: string): Rect | null {
    const pos = positions.get(nodeId)
    if (!pos) return null
    const w = label.length * charWidth
    const cy = pos.y + yOffset
    return { x1: pos.x - w / 2, y1: cy - labelHeight / 2, x2: pos.x + w / 2, y2: cy + labelHeight / 2 }
  }

  function overlaps(a: Rect, b: Rect): boolean {
    return a.x1 < b.x2 && a.x2 > b.x1 && a.y1 < b.y2 && a.y2 > b.y1
  }

  // Sort: hub first, then by connection count descending
  const sorted = [...nodes].sort((a, b) => {
    if (a.id === hubId) return -1
    if (b.id === hubId) return 1
    return (connectionCounts.get(b.id) ?? 0) - (connectionCounts.get(a.id) ?? 0)
  })

  const visible = new Set<string>()
  const placed: Rect[] = []

  for (const node of sorted) {
    const label = getNodeLabel(node)
    const rect = getLabelRect(node.id, label)
    if (!rect) continue
    if (placed.some((p) => overlaps(rect, p))) continue
    visible.add(node.id)
    placed.push(rect)
  }

  return visible
}

/* ── human-readable footer stats ──────────────────────────── */

const ENTITY_LABELS: Record<string, string> = {
  Ticket: 'ticket',
  Person: 'person',
  Decision: 'decision',
  PR: 'PR',
  Message: 'message',
  Code: 'file',
  CodeChunk: 'file',
  NotionPage: 'page',
  SlackThread: 'thread',
  Meeting: 'meeting',
}

const IRREGULAR_PLURALS: Record<string, string> = {
  person: 'people',
}

const NO_PLURAL = new Set(['PR'])

export function buildFooterText(nodes: ApiNode[]): string {
  const counts = new Map<string, number>()
  for (const node of nodes) {
    const label = ENTITY_LABELS[node.entity_type] ?? node.entity_type.toLowerCase()
    counts.set(label, (counts.get(label) ?? 0) + 1)
  }
  // Top 3 by count
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3)
  return sorted
    .map(([label, count]) => {
      if (count === 1) return `${count} ${label}`
      if (NO_PLURAL.has(label)) return `${count} ${label}`
      if (IRREGULAR_PLURALS[label]) return `${count} ${IRREGULAR_PLURALS[label]}`
      return `${count} ${label}s`
    })
    .join(' · ')
}

/* ── node label extraction ────────────────────────────────── */

export function getNodeLabel(node: ApiNode, maxLen: number = 18): string {
  const props = node.properties as Record<string, unknown>
  const identifier = typeof props?.identifier === 'string' ? props.identifier : null
  const raw = identifier ?? node.name
  return raw.length > maxLen ? raw.slice(0, maxLen - 2) + '…' : raw
}

/* ── connection counting + hub detection ──────────────────── */

/** Count how many edges touch each node. */
export function countConnections(edges: ApiEdge[]): Map<string, number> {
  const counts = new Map<string, number>()
  for (const edge of edges) {
    counts.set(edge.source, (counts.get(edge.source) ?? 0) + 1)
    counts.set(edge.target, (counts.get(edge.target) ?? 0) + 1)
  }
  return counts
}

export function analyzeConnections(edges: ApiEdge[]): {
  counts: Map<string, number>
  hubId: string | null
} {
  const counts = countConnections(edges)

  let maxCount = 0
  let maxId: string | null = null
  for (const [id, count] of counts) {
    if (count > maxCount) {
      maxCount = count
      maxId = id
    }
  }

  return {
    counts,
    hubId: maxCount >= 3 ? maxId : null,
  }
}
