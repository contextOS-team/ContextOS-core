import { afterEach, describe, expect, it, vi } from 'vitest'
import { computeHeadline } from '../headline-rules'
import type { Delta, TopUrgentItem } from '../types'

function delta(overrides: Partial<Delta> = {}): Delta {
  return {
    decisions: { count: 0, items: [] },
    sources: { count: 0, items: [] },
    needsYou: { topUrgentItem: null, items: [] },
    ...overrides,
  }
}

function deltaWithTopUrgent(overrides: Partial<TopUrgentItem> = {}): Delta {
  return delta({
    decisions: { count: 1, items: [{ id: 'decision-1', createdAt: '2026-05-20T12:00:00Z' }] },
    sources: { count: 0, items: [] },
    needsYou: {
      topUrgentItem: {
        person: overrides.person ?? 'Vasiliy',
        ticketId: overrides.ticketId ?? 'RD-786',
        sinceDay: overrides.sinceDay ?? 'Tuesday',
      },
      items: [],
    },
  })
}

describe('computeHeadline', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  function setNow() {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-05-20T14:00:00Z'))
  }

  it('uses the single-item-dominant headline with a full weekday sinceDay', () => {
    setNow()
    const result = computeHeadline(
      deltaWithTopUrgent({ sinceDay: 'Tuesday', person: 'Vasiliy', ticketId: 'RD-786' }),
      new Date('2026-05-20T00:00:00Z')
    )

    expect(result.headline).toContain('since Tuesday')
    expect(result).toEqual({
      headline: 'Vasiliy is waiting on RD-786 since Tuesday.',
      subtext: '0 new sources since you last looked, 14 hours ago.',
    })
  })

  it('passes Wednesday and absolute dates through without reformatting sinceDay', () => {
    setNow()

    expect(
      computeHeadline(deltaWithTopUrgent({ sinceDay: 'Wednesday' }), new Date('2026-05-20T00:00:00Z'))
        .headline
    ).toBe('Vasiliy is waiting on RD-786 since Wednesday.')
    expect(
      computeHeadline(deltaWithTopUrgent({ sinceDay: 'May 12' }), new Date('2026-05-20T00:00:00Z'))
        .headline
    ).toBe('Vasiliy is waiting on RD-786 since May 12.')
  })

  it('subtracts the dominant item from decision remainder copy', () => {
    setNow()
    const result = computeHeadline(
      delta({
        decisions: { count: 5, items: [] },
        sources: { count: 30, items: [] },
        needsYou: {
          topUrgentItem: { person: 'Vasiliy', ticketId: 'RD-786', sinceDay: 'Tuesday' },
          items: [],
        },
      }),
      new Date('2026-05-20T00:00:00Z')
    )

    expect(result).toEqual({
      headline: 'Vasiliy is waiting on RD-786 since Tuesday.',
      subtext: '4 more decisions and 30 new sources since you last looked, 14 hours ago.',
    })
  })

  it('omits the decision remainder clause when only sources remain', () => {
    setNow()
    const result = computeHeadline(
      delta({
        decisions: { count: 0, items: [] },
        sources: { count: 12, items: [] },
        needsYou: {
          topUrgentItem: { person: 'Vasiliy', ticketId: 'RD-786', sinceDay: 'Tuesday' },
          items: [],
        },
      }),
      new Date('2026-05-20T00:00:00Z')
    )

    expect(result).toEqual({
      headline: 'Vasiliy is waiting on RD-786 since Tuesday.',
      subtext: '12 new sources since you last looked, 14 hours ago.',
    })
  })

  it('uses the bucket headline when no single item dominates', () => {
    setNow()
    const result = computeHeadline(
      delta({
        decisions: { count: 3, items: [] },
        sources: { count: 30, items: [] },
      }),
      new Date('2026-05-20T00:00:00Z')
    )

    expect(result).toEqual({
      headline: '3 decisions and 30 sources of new context since you last looked.',
      subtext: 'Since you last looked, 14 hours ago.',
    })
  })

  it('singularizes the bucket headline', () => {
    setNow()
    const result = computeHeadline(
      delta({
        decisions: { count: 1, items: [] },
        sources: { count: 1, items: [] },
      }),
      new Date('2026-05-20T00:00:00Z')
    )

    expect(result.headline).toBe('1 decision and 1 source of new context since you last looked.')
  })

  it('uses Quiet day when nothing is new', () => {
    setNow()
    expect(computeHeadline(delta(), new Date('2026-05-20T12:00:00Z'))).toEqual({
      headline: 'Quiet day.',
      subtext: 'Nothing new since you last looked, 2 hours ago.',
    })
  })

  it('uses first visit when lastVisitedAt is missing', () => {
    setNow()
    expect(computeHeadline(delta(), null)).toEqual({
      headline: 'Quiet day.',
      subtext: 'Nothing new since you last looked, first visit.',
    })
  })

  it('handles pluralization edge cases', () => {
    setNow()

    expect(
      computeHeadline(
        delta({
          decisions: { count: 0, items: [] },
          sources: { count: 1, items: [] },
        }),
        new Date('2026-05-20T00:00:00Z')
      ).headline
    ).toBe('0 decisions and 1 source of new context since you last looked.')

    expect(
      computeHeadline(
        delta({
          decisions: { count: 2, items: [] },
          sources: { count: 1, items: [] },
          needsYou: {
            topUrgentItem: { person: 'Vasiliy', ticketId: 'RD-786', sinceDay: 'Tuesday' },
            items: [],
          },
        }),
        new Date('2026-05-20T00:00:00Z')
      ).subtext
    ).toBe('1 more decision and 1 new source since you last looked, 14 hours ago.')
  })
})
