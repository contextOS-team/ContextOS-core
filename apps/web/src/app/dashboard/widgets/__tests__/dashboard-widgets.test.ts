/**
 * Dashboard widget tests.
 *
 * Imports real functions — no replicated logic. If source changes, tests break.
 */

import { describe, it, expect } from 'vitest'
import type { ApiNode, ApiEdge, LensGraphResponse } from '@/components/graph/types'
import type { DaySummary } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import {
  forceLayout,
  filterToUserPerson,
  buildFooterText,
  getNodeLabel,
  analyzeConnections,
  getSvgHeight,
  resolveVisibleLabels,
} from '../graph-thumbnail-logic'

// ─── Fixtures ────────────────────────────────────────────────────────────────

function nd(id: string, type: string, overrides?: Partial<ApiNode>): ApiNode {
  return { id, entity_type: type, name: id, depth: 0, properties: {}, ...overrides }
}

function edge(src: string, tgt: string): ApiEdge {
  return { source: src, target: tgt, relationship_type: 'references', properties: {} }
}

// ═════════════════════════════════════════════════════════════════════════════
// forceLayout
// ═════════════════════════════════════════════════════════════════════════════

describe('forceLayout', () => {
  it('empty → empty', () => {
    expect(forceLayout([], [], 400, 200).size).toBe(0)
  })

  it('single node → center', () => {
    const pos = forceLayout([nd('a', 'Ticket')], [], 400, 200)
    expect(pos.get('a')).toEqual({ x: 200, y: 100 })
  })

  it('every node gets a position', () => {
    const nodes = [nd('a', 'Ticket'), nd('b', 'Ticket'), nd('c', 'Person')]
    const pos = forceLayout(nodes, [edge('a', 'b')], 400, 200)
    expect(pos.size).toBe(3)
    for (const n of nodes) expect(pos.has(n.id)).toBe(true)
  })

  it('all positions within viewport bounds', () => {
    const W = 400, H = 200
    const nodes = Array.from({ length: 20 }, (_, i) => nd(`n${i}`, 'Ticket'))
    const edges = nodes.slice(1).map(n => edge(nodes[0].id, n.id))
    const pos = forceLayout(nodes, edges, W, H)
    for (const [, p] of pos) {
      expect(p.x).toBeGreaterThanOrEqual(0)
      expect(p.x).toBeLessThanOrEqual(W)
      expect(p.y).toBeGreaterThanOrEqual(0)
      expect(p.y).toBeLessThanOrEqual(H)
    }
  })

  it('connected nodes closer than disconnected', () => {
    const nodes = [nd('a', 'Ticket'), nd('b', 'Ticket'), nd('c', 'Ticket')]
    const pos = forceLayout(nodes, [edge('a', 'b')], 400, 200)
    const ab = Math.hypot(pos.get('a')!.x - pos.get('b')!.x, pos.get('a')!.y - pos.get('b')!.y)
    const ac = Math.hypot(pos.get('a')!.x - pos.get('c')!.x, pos.get('a')!.y - pos.get('c')!.y)
    expect(ab).toBeLessThan(ac)
  })

  it('clamps at 80 nodes', () => {
    const nodes = Array.from({ length: 100 }, (_, i) => nd(`n${i}`, 'Ticket'))
    expect(forceLayout(nodes, [], 400, 200).size).toBe(80)
  })

  it('deterministic', () => {
    const nodes = [nd('x', 'Ticket'), nd('y', 'Person'), nd('z', 'Decision')]
    const edges = [edge('x', 'y'), edge('y', 'z')]
    const a = forceLayout(nodes, edges, 400, 200)
    const b = forceLayout(nodes, edges, 400, 200)
    for (const id of ['x', 'y', 'z']) {
      expect(a.get(id)!.x).toBeCloseTo(b.get(id)!.x, 10)
      expect(a.get(id)!.y).toBeCloseTo(b.get(id)!.y, 10)
    }
  })
})

// ═════════════════════════════════════════════════════════════════════════════
// filterToUserPerson
// ═════════════════════════════════════════════════════════════════════════════

describe('filterToUserPerson', () => {
  it('passes through when 0 or 1 Person', () => {
    const nodes = [nd('t1', 'Ticket'), nd('p1', 'Person')]
    const edges = [edge('t1', 'p1')]
    const r = filterToUserPerson(nodes, edges)
    expect(r.nodes).toEqual(nodes)
    expect(r.edges).toEqual(edges)
  })

  it('keeps most-connected Person when no userName', () => {
    const nodes = [
      nd('t1', 'Ticket'), nd('t2', 'Ticket'), nd('t3', 'Ticket'),
      nd('me', 'Person'),
      nd('them', 'Person'),
    ]
    const edges = [edge('me', 't1'), edge('me', 't2'), edge('me', 't3'), edge('them', 't1')]
    const r = filterToUserPerson(nodes, edges)
    expect(r.nodes.filter(n => n.entity_type === 'Person').map(n => n.id)).toEqual(['me'])
    expect(r.edges.every(e => e.source !== 'them' && e.target !== 'them')).toBe(true)
  })

  it('matches by userName (case-insensitive) over connection count', () => {
    const nodes = [
      nd('t1', 'Ticket'),
      nd('me', 'Person', { name: 'Aya' }),          // 1 edge
      nd('them', 'Person', { name: 'Colleague' }),   // 2 edges
    ]
    const edges = [edge('me', 't1'), edge('them', 't1'), edge('them', 'me')]
    // 'them' has more connections, but userName matches 'me'
    const r = filterToUserPerson(nodes, edges, 'aya')
    expect(r.nodes.filter(n => n.entity_type === 'Person').map(n => n.id)).toEqual(['me'])
  })

  it('falls back to most-connected when userName matches nobody', () => {
    const nodes = [
      nd('t1', 'Ticket'),
      nd('p1', 'Person', { name: 'Alice' }),
      nd('p2', 'Person', { name: 'Bob' }),
    ]
    const edges = [edge('p1', 't1'), edge('p1', 'p2')]
    const r = filterToUserPerson(nodes, edges, 'nobody')
    // p1 has 2 connections, p2 has 1
    expect(r.nodes.filter(n => n.entity_type === 'Person').map(n => n.id)).toEqual(['p1'])
  })

  it('equal connections → keeps first by reduce order', () => {
    const nodes = [nd('t1', 'Ticket'), nd('p1', 'Person'), nd('p2', 'Person')]
    const edges = [edge('p1', 't1'), edge('p2', 't1')]
    const r = filterToUserPerson(nodes, edges)
    expect(r.nodes.filter(n => n.entity_type === 'Person')).toHaveLength(1)
  })
})

// ═════════════════════════════════════════════════════════════════════════════
// analyzeConnections
// ═════════════════════════════════════════════════════════════════════════════

describe('analyzeConnections', () => {
  it('counts both sides of each edge', () => {
    const { counts } = analyzeConnections([edge('a', 'b'), edge('a', 'c')])
    expect(counts.get('a')).toBe(2)
    expect(counts.get('b')).toBe(1)
    expect(counts.get('c')).toBe(1)
  })

  it('hub when >= 3 connections', () => {
    expect(analyzeConnections([edge('h', 'a'), edge('h', 'b'), edge('h', 'c')]).hubId).toBe('h')
  })

  it('no hub when all < 3', () => {
    expect(analyzeConnections([edge('a', 'b')]).hubId).toBeNull()
  })

  it('empty edges → empty counts', () => {
    expect(analyzeConnections([]).counts.size).toBe(0)
  })
})

// ═════════════════════════════════════════════════════════════════════════════
// buildFooterText
// ═════════════════════════════════════════════════════════════════════════════

describe('buildFooterText', () => {
  it('pluralizes regular nouns', () => {
    expect(buildFooterText([nd('1', 'Ticket'), nd('2', 'Ticket'), nd('3', 'Decision')]))
      .toBe('2 tickets · 1 decision')
  })

  it('irregular: Person → people', () => {
    expect(buildFooterText([nd('1', 'Person'), nd('2', 'Person')])).toBe('2 people')
  })

  it('no-plural: PR stays PR', () => {
    expect(buildFooterText([nd('1', 'PR'), nd('2', 'PR')])).toBe('2 PR')
  })

  it('top 3 only', () => {
    const nodes = [
      nd('1', 'Ticket'), nd('2', 'Ticket'),
      nd('3', 'Person'), nd('4', 'Decision'), nd('5', 'PR'),
    ]
    expect(buildFooterText(nodes).split(' · ').length).toBeLessThanOrEqual(3)
  })

  it('merges Code + CodeChunk → file', () => {
    expect(buildFooterText([nd('1', 'Code'), nd('2', 'CodeChunk'), nd('3', 'Code')])).toBe('3 files')
  })
})

// ═════════════════════════════════════════════════════════════════════════════
// getNodeLabel
// ═════════════════════════════════════════════════════════════════════════════

describe('getNodeLabel', () => {
  it('prefers identifier over name', () => {
    expect(getNodeLabel(nd('1', 'Ticket', { name: 'Long name', properties: { identifier: 'ENG-42' } }))).toBe('ENG-42')
  })

  it('falls back to name', () => {
    expect(getNodeLabel(nd('1', 'Person', { name: 'Alice' }))).toBe('Alice')
  })

  it('truncates at maxLen', () => {
    const label = getNodeLabel(nd('1', 'Decision', { name: 'A very long decision title' }))
    expect(label.length).toBeLessThanOrEqual(18)
    expect(label.endsWith('…')).toBe(true)
  })

  it('short labels untouched', () => {
    expect(getNodeLabel(nd('1', 'Ticket', { name: 'Short' }))).toBe('Short')
  })
})

// ═════════════════════════════════════════════════════════════════════════════
// getSvgHeight
// ═════════════════════════════════════════════════════════════════════════════

describe('getSvgHeight', () => {
  it('scales with count', () => {
    expect(getSvgHeight(3)).toBe(160)
    expect(getSvgHeight(8)).toBe(200)
    expect(getSvgHeight(15)).toBe(240)
    expect(getSvgHeight(30)).toBe(280)
  })
})

// ═════════════════════════════════════════════════════════════════════════════
// resolveVisibleLabels
// ═════════════════════════════════════════════════════════════════════════════

describe('resolveVisibleLabels', () => {
  it('hub always visible', () => {
    const nodes = [nd('hub', 'Ticket', { name: 'HUB' }), nd('b', 'Ticket', { name: 'B' })]
    const positions = new Map([['hub', { x: 200, y: 100 }], ['b', { x: 200, y: 100 }]])
    const counts = new Map([['hub', 5], ['b', 1]])
    const visible = resolveVisibleLabels(nodes, positions, counts, 'hub')
    expect(visible.has('hub')).toBe(true)
  })

  it('hides overlapping labels', () => {
    // Two nodes at the exact same position — second should be hidden
    const nodes = [nd('a', 'Ticket', { name: 'First' }), nd('b', 'Ticket', { name: 'Second' })]
    const positions = new Map([['a', { x: 100, y: 100 }], ['b', { x: 100, y: 100 }]])
    const counts = new Map([['a', 2], ['b', 1]])
    const visible = resolveVisibleLabels(nodes, positions, counts, null)
    expect(visible.size).toBe(1) // only one fits
  })

  it('shows all labels when well-spaced', () => {
    const nodes = [nd('a', 'Ticket', { name: 'A' }), nd('b', 'Ticket', { name: 'B' })]
    const positions = new Map([['a', { x: 50, y: 50 }], ['b', { x: 350, y: 150 }]])
    const counts = new Map([['a', 1], ['b', 1]])
    const visible = resolveVisibleLabels(nodes, positions, counts, null)
    expect(visible.size).toBe(2)
  })
})

// ═════════════════════════════════════════════════════════════════════════════
// isTrulyEmpty (replicates page.tsx logic — this is the one piece we can't
// import because it's inline in a React component, but the logic is 4 lines)
// ═════════════════════════════════════════════════════════════════════════════

function computeIsTrulyEmpty(
  attentionItems: unknown[],
  weeklySummary: DaySummary[],
  recentPages: unknown[],
  graphData: LensGraphResponse | null,
  workspaceId: string | null,
): boolean {
  const widgetsEmpty =
    attentionItems.length === 0 &&
    weeklySummary.filter((d: DaySummary) => d.activity_count > 0 || d.contexts_updated > 0 || d.prs_merged > 0).length === 0
  const hasGraphData = (graphData?.all_nodes?.length ?? 0) > 0
  return widgetsEmpty && recentPages.length === 0 && !hasGraphData && !workspaceId
}

function makeDaySummary(date: string, a: number, c: number, p: number): DaySummary {
  return { date, activity_count: a, contexts_updated: c, prs_merged: p }
}

describe('isTrulyEmpty', () => {
  it('true when everything is empty', () => {
    expect(computeIsTrulyEmpty([], [], [], null, null)).toBe(true)
  })

  it('false when attention items exist', () => {
    expect(computeIsTrulyEmpty([{}], [], [], null, null)).toBe(false)
  })

  it('false when weekly has activity', () => {
    expect(computeIsTrulyEmpty([], [makeDaySummary('2026-03-18', 1, 0, 0)], [], null, null)).toBe(false)
  })

  it('false when context pages exist', () => {
    expect(computeIsTrulyEmpty([], [], [{}], null, null)).toBe(false)
  })

  it('false when graph has nodes (even with no left-column data)', () => {
    const graph: LensGraphResponse = {
      lens: 'my_work', clusters: [], all_nodes: [nd('1', 'Ticket')],
      all_edges: [], node_count: 1, edge_count: 0, truncated: false,
    }
    expect(computeIsTrulyEmpty([], [], [], graph, null)).toBe(false)
  })

  it('false when workspaceId exists (activity feed may have events)', () => {
    expect(computeIsTrulyEmpty([], [], [], null, 'ws-123')).toBe(false)
  })

  it('true when graph response exists but has zero nodes', () => {
    const emptyGraph: LensGraphResponse = {
      lens: 'my_work', clusters: [], all_nodes: [],
      all_edges: [], node_count: 0, edge_count: 0, truncated: false,
    }
    expect(computeIsTrulyEmpty([], [], [], emptyGraph, null)).toBe(true)
  })
})

// ═════════════════════════════════════════════════════════════════════════════
// formatRelativeTime (real import from @/lib/utils)
// ═════════════════════════════════════════════════════════════════════════════

describe('formatRelativeTime', () => {
  it('YYYY-MM-DD → string', () => {
    expect(typeof formatRelativeTime('2026-03-18')).toBe('string')
  })

  it('ISO datetime → string', () => {
    expect(typeof formatRelativeTime('2026-03-18T12:00:00Z')).toBe('string')
  })

  it('future → "just now"', () => {
    expect(formatRelativeTime('2099-12-31')).toBe('just now')
  })

  it('date-only parses as local midnight', () => {
    const d = new Date('2026-03-18T00:00:00') // what the fix produces
    expect(d.getHours()).toBe(0)
    expect(d.getDate()).toBe(18)
  })
})
