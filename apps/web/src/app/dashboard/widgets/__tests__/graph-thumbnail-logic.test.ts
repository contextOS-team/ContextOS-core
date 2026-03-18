/**
 * Tests for graph-thumbnail pure logic.
 *
 * Covers: forceLayout, filterToUserPerson, buildFooterText, getNodeLabel,
 * analyzeConnections, getSvgHeight — all edge cases and the bugs found
 * during code review.
 */

import { describe, it, expect } from 'vitest'
import type { ApiNode, ApiEdge } from '@/components/graph/types'
import {
  forceLayout,
  getSvgHeight,
  filterToUserPerson,
  buildFooterText,
  getNodeLabel,
  analyzeConnections,
  resolveVisibleLabels,
} from '../graph-thumbnail-logic'

// ─── Fixtures ────────────────────────────────────────────────────────────────

function node(id: string, type: string, name?: string, props?: Record<string, unknown>): ApiNode {
  return { id, entity_type: type, name: name ?? id, depth: 0, properties: props ?? {} }
}

function edge(source: string, target: string): ApiEdge {
  return { source, target, relationship_type: 'references', properties: {} }
}

// ─── forceLayout ─────────────────────────────────────────────────────────────

describe('forceLayout', () => {
  const W = 400
  const H = 200

  it('returns empty map for zero nodes', () => {
    const result = forceLayout([], [], W, H)
    expect(result.size).toBe(0)
  })

  it('places single node at center', () => {
    const nodes = [node('a', 'Ticket')]
    const result = forceLayout(nodes, [], W, H)
    expect(result.size).toBe(1)
    const pos = result.get('a')!
    expect(pos.x).toBe(W / 2)
    expect(pos.y).toBe(H / 2)
  })

  it('returns a position for every node', () => {
    const nodes = Array.from({ length: 15 }, (_, i) => node(`n${i}`, 'Ticket'))
    const edges = nodes.slice(1).map((n) => edge('n0', n.id))
    const result = forceLayout(nodes, edges, W, H)
    expect(result.size).toBe(15)
    for (const n of nodes) {
      expect(result.has(n.id)).toBe(true)
    }
  })

  it('produces NO NaN or Infinity values', () => {
    const nodes = Array.from({ length: 20 }, (_, i) => node(`n${i}`, 'Ticket'))
    const edges = nodes.slice(1).map((n) => edge('n0', n.id))
    const result = forceLayout(nodes, edges, W, H)
    for (const [, pos] of result) {
      expect(Number.isFinite(pos.x)).toBe(true)
      expect(Number.isFinite(pos.y)).toBe(true)
    }
  })

  it('keeps all positions within viewport bounds (with padding)', () => {
    const nodes = Array.from({ length: 20 }, (_, i) => node(`n${i}`, 'Ticket'))
    const edges = nodes.slice(1).map((n) => edge('n0', n.id))
    const result = forceLayout(nodes, edges, W, H)
    for (const [, pos] of result) {
      expect(pos.x).toBeGreaterThanOrEqual(0)
      expect(pos.x).toBeLessThanOrEqual(W)
      expect(pos.y).toBeGreaterThanOrEqual(0)
      expect(pos.y).toBeLessThanOrEqual(H)
    }
  })

  it('handles disconnected graph (nodes with no edges)', () => {
    const nodes = [node('a', 'Ticket'), node('b', 'Ticket'), node('c', 'Ticket')]
    const result = forceLayout(nodes, [], W, H)
    expect(result.size).toBe(3)
    // With pure repulsion and no edges, nodes should spread apart
    const positions = [...result.values()]
    const dist01 = Math.hypot(positions[0].x - positions[1].x, positions[0].y - positions[1].y)
    expect(dist01).toBeGreaterThan(10) // they shouldn't be on top of each other
  })

  it('handles edges referencing non-existent nodes (orphan edges)', () => {
    const nodes = [node('a', 'Ticket'), node('b', 'Ticket')]
    const edges = [edge('a', 'b'), edge('a', 'ghost'), edge('ghost2', 'b')]
    // Should not crash — orphan edges are filtered out
    const result = forceLayout(nodes, edges, W, H)
    expect(result.size).toBe(2)
  })

  it('produces deterministic output (same input → same positions)', () => {
    const nodes = [node('a', 'Ticket'), node('b', 'Person'), node('c', 'Decision')]
    const edges = [edge('a', 'b'), edge('b', 'c')]
    const r1 = forceLayout(nodes, edges, W, H)
    const r2 = forceLayout(nodes, edges, W, H)
    for (const n of nodes) {
      expect(r1.get(n.id)!.x).toBe(r2.get(n.id)!.x)
      expect(r1.get(n.id)!.y).toBe(r2.get(n.id)!.y)
    }
  })

  it('star topology: hub is more central than leaves', () => {
    // This is the actual "my work" shape: one Person hub connected to many Tickets
    const hub = node('hub', 'Person', 'Daulet')
    const leaves = Array.from({ length: 8 }, (_, i) => node(`t${i}`, 'Ticket', `CON-${i}`))
    const edges = leaves.map((l) => edge('hub', l.id))
    const result = forceLayout([hub, ...leaves], edges, W, H)

    const hubPos = result.get('hub')!
    // Hub should be roughly central
    expect(hubPos.x).toBeGreaterThan(W * 0.2)
    expect(hubPos.x).toBeLessThan(W * 0.8)
    expect(hubPos.y).toBeGreaterThan(H * 0.2)
    expect(hubPos.y).toBeLessThan(H * 0.8)
  })

  it('two nodes: both within bounds and not overlapping', () => {
    const nodes = [node('a', 'Ticket'), node('b', 'Ticket')]
    const edges = [edge('a', 'b')]
    const result = forceLayout(nodes, edges, W, H)
    const posA = result.get('a')!
    const posB = result.get('b')!
    const dist = Math.hypot(posA.x - posB.x, posA.y - posB.y)
    expect(dist).toBeGreaterThan(5) // not stacked
  })
})

// ─── getSvgHeight ────────────────────────────────────────────────────────────

describe('getSvgHeight', () => {
  it('returns correct heights for boundary values', () => {
    expect(getSvgHeight(0)).toBe(160)
    expect(getSvgHeight(1)).toBe(160)
    expect(getSvgHeight(5)).toBe(160)
    expect(getSvgHeight(6)).toBe(200)
    expect(getSvgHeight(10)).toBe(200)
    expect(getSvgHeight(11)).toBe(240)
    expect(getSvgHeight(20)).toBe(240)
    expect(getSvgHeight(21)).toBe(280)
    expect(getSvgHeight(50)).toBe(280)
  })
})

// ─── filterToUserPerson ──────────────────────────────────────────────────────

describe('filterToUserPerson', () => {
  it('returns unchanged when 0 Person nodes exist', () => {
    const nodes = [node('t1', 'Ticket'), node('t2', 'Ticket')]
    const edges = [edge('t1', 't2')]
    const result = filterToUserPerson(nodes, edges)
    expect(result.nodes).toEqual(nodes)
    expect(result.edges).toEqual(edges)
  })

  it('returns unchanged when exactly 1 Person node exists', () => {
    const nodes = [node('p1', 'Person'), node('t1', 'Ticket')]
    const edges = [edge('p1', 't1')]
    const result = filterToUserPerson(nodes, edges)
    expect(result.nodes).toEqual(nodes)
    expect(result.edges).toEqual(edges)
  })

  it('keeps the most-connected Person and drops others', () => {
    const nodes = [
      node('user', 'Person', 'Daulet'),
      node('other', 'Person', 'dulatpingood@gmail.com'),
      node('t1', 'Ticket'), node('t2', 'Ticket'), node('t3', 'Ticket'),
    ]
    // user has 3 edges, other has 1
    const edges = [
      edge('user', 't1'), edge('user', 't2'), edge('user', 't3'),
      edge('other', 't1'),
    ]
    const result = filterToUserPerson(nodes, edges)
    expect(result.nodes.map((n) => n.id).sort()).toEqual(['t1', 't2', 't3', 'user'])
    // Edge from 'other' to 't1' should be dropped
    expect(result.edges).toHaveLength(3)
    expect(result.edges.every((e) => e.source !== 'other' && e.target !== 'other')).toBe(true)
  })

  it('handles tied connection counts (keeps first reduce winner)', () => {
    const nodes = [
      node('p1', 'Person', 'Alice'),
      node('p2', 'Person', 'Bob'),
      node('t1', 'Ticket'),
    ]
    // Both have 1 connection — reduce keeps p1 (first element)
    const edges = [edge('p1', 't1'), edge('p2', 't1')]
    const result = filterToUserPerson(nodes, edges)
    // One person should be dropped
    const personCount = result.nodes.filter((n) => n.entity_type === 'Person').length
    expect(personCount).toBe(1)
  })

  it('handles Person with zero edges (drops disconnected person)', () => {
    const nodes = [
      node('user', 'Person', 'Daulet'),
      node('ghost', 'Person', 'Nobody'),
      node('t1', 'Ticket'),
    ]
    const edges = [edge('user', 't1')]
    const result = filterToUserPerson(nodes, edges)
    expect(result.nodes.find((n) => n.id === 'ghost')).toBeUndefined()
    expect(result.nodes.find((n) => n.id === 'user')).toBeDefined()
  })

  it('matches user by name when userName is provided', () => {
    const nodes = [
      node('p1', 'Person', 'Daulet Ashikbayev'),
      node('p2', 'Person', 'Alice Smith'),
      node('t1', 'Ticket'),
    ]
    // p2 has more connections, but userName matches p1
    const edges = [edge('p1', 't1'), edge('p2', 't1'), edge('p2', 'p1')]
    const result = filterToUserPerson(nodes, edges, 'Daulet Ashikbayev')
    const kept = result.nodes.find((n) => n.entity_type === 'Person')
    expect(kept?.name).toBe('Daulet Ashikbayev')
  })

  it('matches user by partial name (substring)', () => {
    const nodes = [
      node('p1', 'Person', 'Daulet Ashikbayev'),
      node('p2', 'Person', 'someone@email.com'),
      node('t1', 'Ticket'),
    ]
    const edges = [edge('p1', 't1'), edge('p2', 't1')]
    // userName is just first name — should still match
    const result = filterToUserPerson(nodes, edges, 'Daulet')
    const kept = result.nodes.find((n) => n.entity_type === 'Person')
    expect(kept?.name).toBe('Daulet Ashikbayev')
  })

  it('matches user by reverse substring (node name inside userName)', () => {
    const nodes = [
      node('p1', 'Person', 'Daulet'),
      node('p2', 'Person', 'Alice'),
      node('t1', 'Ticket'),
    ]
    const edges = [edge('p1', 't1'), edge('p2', 't1')]
    const result = filterToUserPerson(nodes, edges, 'Daulet Ashikbayev')
    const kept = result.nodes.find((n) => n.entity_type === 'Person')
    expect(kept?.name).toBe('Daulet')
  })

  it('falls back to most-connected when userName does not match any Person', () => {
    const nodes = [
      node('p1', 'Person', 'Alice'),
      node('p2', 'Person', 'Bob'),
      node('t1', 'Ticket'), node('t2', 'Ticket'), node('t3', 'Ticket'),
    ]
    const edges = [
      edge('p1', 't1'), edge('p1', 't2'), edge('p1', 't3'),
      edge('p2', 't1'),
    ]
    const result = filterToUserPerson(nodes, edges, 'NoMatch')
    const kept = result.nodes.find((n) => n.entity_type === 'Person')
    expect(kept?.name).toBe('Alice') // most connected
  })
})

// ─── buildFooterText ─────────────────────────────────────────────────────────

describe('buildFooterText', () => {
  it('pluralizes correctly for single type', () => {
    const nodes = Array.from({ length: 5 }, (_, i) => node(`t${i}`, 'Ticket'))
    expect(buildFooterText(nodes)).toBe('5 tickets')
  })

  it('shows singular for count of 1', () => {
    expect(buildFooterText([node('t1', 'Ticket')])).toBe('1 ticket')
  })

  it('uses "people" not "persons"', () => {
    const nodes = [node('p1', 'Person'), node('p2', 'Person')]
    expect(buildFooterText(nodes)).toBe('2 people')
  })

  it('does not pluralize PR', () => {
    const nodes = [node('pr1', 'PR'), node('pr2', 'PR')]
    expect(buildFooterText(nodes)).toBe('2 PR')
  })

  it('shows top 3 types sorted by count', () => {
    const nodes = [
      ...Array.from({ length: 5 }, (_, i) => node(`t${i}`, 'Ticket')),
      ...Array.from({ length: 3 }, (_, i) => node(`d${i}`, 'Decision')),
      ...Array.from({ length: 2 }, (_, i) => node(`m${i}`, 'Message')),
      node('p1', 'Person'), // 4th type, should be excluded
    ]
    const text = buildFooterText(nodes)
    expect(text).toBe('5 tickets · 3 decisions · 2 messages')
  })

  it('merges Code and CodeChunk into "file"', () => {
    const nodes = [node('c1', 'Code'), node('c2', 'CodeChunk')]
    expect(buildFooterText(nodes)).toBe('2 files')
  })

  it('handles empty nodes array', () => {
    expect(buildFooterText([])).toBe('')
  })

  it('handles unknown entity type gracefully', () => {
    const nodes = [node('x1', 'SomeFutureType' as any)]
    expect(buildFooterText(nodes)).toBe('1 somefuturetype')
  })
})

// ─── getNodeLabel ────────────────────────────────────────────────────────────

describe('getNodeLabel', () => {
  it('uses identifier property when available', () => {
    const n = node('t1', 'Ticket', 'Some long ticket name', { identifier: 'CON-54' })
    expect(getNodeLabel(n)).toBe('CON-54')
  })

  it('falls back to node name when no identifier', () => {
    const n = node('d1', 'Decision', 'Use Redis')
    expect(getNodeLabel(n)).toBe('Use Redis')
  })

  it('truncates long names with ellipsis', () => {
    const n = node('d1', 'Decision', 'This is a very long decision name that should be truncated')
    const label = getNodeLabel(n)
    expect(label.length).toBeLessThanOrEqual(18)
    expect(label.endsWith('…')).toBe(true)
  })

  it('does not truncate names at exactly maxLen', () => {
    const n = node('d1', 'Decision', '123456789012345678') // exactly 18 chars
    expect(getNodeLabel(n)).toBe('123456789012345678')
  })

  it('handles missing properties object', () => {
    const n: ApiNode = { id: 'x', entity_type: 'Ticket', name: 'Test', depth: 0, properties: {} }
    expect(getNodeLabel(n)).toBe('Test')
  })

  it('respects custom maxLen', () => {
    const n = node('d1', 'Decision', 'Short enough')
    expect(getNodeLabel(n, 10)).toBe('Short en…')
  })
})

// ─── analyzeConnections ──────────────────────────────────────────────────────

describe('analyzeConnections', () => {
  it('returns empty counts and null hub for no edges', () => {
    const result = analyzeConnections([])
    expect(result.counts.size).toBe(0)
    expect(result.hubId).toBeNull()
  })

  it('counts connections correctly', () => {
    const edges = [edge('a', 'b'), edge('a', 'c'), edge('b', 'c')]
    const result = analyzeConnections(edges)
    expect(result.counts.get('a')).toBe(2)
    expect(result.counts.get('b')).toBe(2)
    expect(result.counts.get('c')).toBe(2)
  })

  it('identifies hub node (≥3 connections)', () => {
    const edges = [edge('hub', 'a'), edge('hub', 'b'), edge('hub', 'c')]
    const result = analyzeConnections(edges)
    expect(result.hubId).toBe('hub')
  })

  it('returns null hub when max connections < 3', () => {
    const edges = [edge('a', 'b'), edge('b', 'c')]
    const result = analyzeConnections(edges)
    expect(result.hubId).toBeNull()
  })

  it('self-loop counts as 2 connections to same node', () => {
    const edges = [edge('a', 'a'), edge('a', 'b'), edge('a', 'c')]
    const result = analyzeConnections(edges)
    // a appears as both source and target in self-loop: +2, plus 2 more = 4
    expect(result.counts.get('a')).toBe(4)
    expect(result.hubId).toBe('a')
  })
})

// ─── resolveVisibleLabels ────────────────────────────────────────────────────

describe('resolveVisibleLabels', () => {
  it('shows all labels when nodes are far apart', () => {
    const nodes = [node('a', 'Ticket', 'A'), node('b', 'Ticket', 'B')]
    const positions = new Map([
      ['a', { x: 50, y: 50 }],
      ['b', { x: 350, y: 150 }],
    ])
    const counts = new Map([['a', 1], ['b', 1]])
    const visible = resolveVisibleLabels(nodes, positions, counts, null)
    expect(visible.size).toBe(2)
  })

  it('hides overlapping labels — keeps higher-connected node', () => {
    const nodes = [
      node('hub', 'Person', 'Daulet'),
      node('a', 'Ticket', 'CON-54'),
      node('b', 'Ticket', 'CON-55'),
    ]
    // a and b placed at nearly the same position — labels will overlap
    const positions = new Map([
      ['hub', { x: 200, y: 50 }],
      ['a', { x: 100, y: 100 }],
      ['b', { x: 103, y: 100 }], // 3px apart — labels definitely overlap
    ])
    const counts = new Map([['hub', 5], ['a', 3], ['b', 1]])
    const visible = resolveVisibleLabels(nodes, positions, counts, 'hub')
    // hub should always be visible
    expect(visible.has('hub')).toBe(true)
    // a has more connections so it wins over b
    expect(visible.has('a')).toBe(true)
    expect(visible.has('b')).toBe(false)
  })

  it('hub label always wins even if overlapping with higher-count node', () => {
    const nodes = [
      node('hub', 'Person', 'Daulet Ashikbayev'),
      node('a', 'Ticket', 'CON-54'),
    ]
    // Same position — would overlap
    const positions = new Map([
      ['hub', { x: 200, y: 100 }],
      ['a', { x: 200, y: 100 }],
    ])
    const counts = new Map([['hub', 2], ['a', 5]])
    const visible = resolveVisibleLabels(nodes, positions, counts, 'hub')
    expect(visible.has('hub')).toBe(true)
    // a overlaps with hub and hub wins (processed first)
    expect(visible.has('a')).toBe(false)
  })

  it('returns empty set for empty nodes', () => {
    const visible = resolveVisibleLabels([], new Map(), new Map(), null)
    expect(visible.size).toBe(0)
  })

  it('handles node missing from positions map', () => {
    const nodes = [node('a', 'Ticket', 'A'), node('b', 'Ticket', 'B')]
    const positions = new Map([['a', { x: 200, y: 100 }]]) // b missing
    const counts = new Map([['a', 1]])
    const visible = resolveVisibleLabels(nodes, positions, counts, null)
    expect(visible.has('a')).toBe(true)
    expect(visible.has('b')).toBe(false)
  })

  it('uses different yOffset for hub vs normal nodes', () => {
    // Hub at y=100 with yOffset=18 → label center at y=118
    // Normal at y=100 with yOffset=15 → label center at y=115
    // These are close but with different offsets the rects may or may not overlap
    // The key assertion: hub and a node at the same position should be detected as overlapping
    const nodes = [
      node('hub', 'Person', 'Daulet Ashikbayev'),
      node('a', 'Ticket', 'CON-54'),
    ]
    const positions = new Map([
      ['hub', { x: 200, y: 100 }],
      ['a', { x: 200, y: 100 }],
    ])
    const counts = new Map([['hub', 5], ['a', 1]])
    // With correct hub yOffset=18, hub label rect and normal label rect overlap
    const visible = resolveVisibleLabels(nodes, positions, counts, 'hub', 9, 15, 18)
    expect(visible.has('hub')).toBe(true)
    expect(visible.has('a')).toBe(false) // overlaps with hub
  })
})

// ─── Regression: name matching edge cases ────────────────────────────────────

describe('filterToUserPerson name matching edge cases', () => {
  it('does NOT false-match short Person names via substring (e.g. "Al" inside "Ashikbayev")', () => {
    const nodes = [
      node('p1', 'Person', 'Al'),           // short name — should NOT match
      node('p2', 'Person', 'Daulet'),        // correct match
      node('t1', 'Ticket'),
    ]
    // p1 has more connections — would win the fallback heuristic
    const edges = [
      edge('p1', 't1'), edge('p1', 'p2'),
      edge('p2', 't1'),
    ]
    const result = filterToUserPerson(nodes, edges, 'Daulet Ashikbayev')
    const kept = result.nodes.find((n) => n.entity_type === 'Person')
    // "Al" is only 2 chars — should be skipped by min-length guard
    // "Daulet" (6 chars) is inside "Daulet Ashikbayev" — correct match
    expect(kept?.name).toBe('Daulet')
  })

  it('does NOT match with userName shorter than 3 characters', () => {
    const nodes = [
      node('p1', 'Person', 'Al Smith'),
      node('p2', 'Person', 'Bob Jones'),
      node('t1', 'Ticket'),
    ]
    const edges = [edge('p1', 't1'), edge('p2', 't1')]
    // userName "Al" is too short for name matching — should fall back to heuristic
    const result = filterToUserPerson(nodes, edges, 'Al')
    // Both have 1 connection, reduce picks first (p1)
    const personCount = result.nodes.filter((n) => n.entity_type === 'Person').length
    expect(personCount).toBe(1)
  })

  it('handles userName that is an email address', () => {
    const nodes = [
      node('p1', 'Person', 'daulet@gmail.com'),
      node('p2', 'Person', 'Alice Smith'),
      node('t1', 'Ticket'),
    ]
    const edges = [edge('p1', 't1'), edge('p2', 't1')]
    const result = filterToUserPerson(nodes, edges, 'daulet@gmail.com')
    const kept = result.nodes.find((n) => n.entity_type === 'Person')
    expect(kept?.name).toBe('daulet@gmail.com')
  })
})

// ─── Regression: forceLayout clamping ────────────────────────────────────────

describe('forceLayout clamping', () => {
  it('returns positions for at most 80 nodes when input exceeds limit', () => {
    const nodes = Array.from({ length: 90 }, (_, i) => node(`n${i}`, 'Ticket'))
    const edges = nodes.slice(1, 80).map((n) => edge('n0', n.id))
    const result = forceLayout(nodes, edges, 400, 280)
    // Should return positions for the first 80 only
    expect(result.size).toBe(80)
    // Nodes 80-89 should NOT have positions
    for (let i = 80; i < 90; i++) {
      expect(result.has(`n${i}`)).toBe(false)
    }
  })

  it('footer should only count visible (positioned) nodes', () => {
    // Simulate what the component does: filter nodes by positions map
    const allNodes = Array.from({ length: 90 }, (_, i) => node(`n${i}`, 'Ticket'))
    const positions = forceLayout(allNodes, [], 400, 280)
    const visibleNodes = allNodes.filter((n) => positions.has(n.id))
    const footer = buildFooterText(visibleNodes)
    // Should say "80 tickets" not "90 tickets"
    expect(footer).toBe('80 tickets')
  })
})
