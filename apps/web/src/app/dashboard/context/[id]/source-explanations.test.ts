import { describe, expect, it } from 'vitest'
import type { ContextPageSource } from '@/lib/api'
import {
  formatFreshnessLabel,
  formatGraphPath,
  formatRetrievalSignal,
  formatRetrievalTarget,
  formatVerificationLabel,
  getSourceSignalLabels,
  hasSourceExplanation,
} from './source-explanations'

function source(overrides: Partial<ContextPageSource> = {}): ContextPageSource {
  return {
    type: 'slack_message',
    id: 'message-1',
    title: 'Decision thread',
    relevance_score: 0.91,
    ...overrides,
  }
}

describe('source explanation helpers', () => {
  it('keeps legacy context page sources free of placeholder metadata', () => {
    const legacy = source()

    expect(hasSourceExplanation(legacy)).toBe(false)
    expect(getSourceSignalLabels(legacy)).toEqual([])
  })

  it('maps retrieval targets and signals to UI-spec labels', () => {
    const enriched = source({
      retrieval_targets: ['decision_receipts', 'source_evidence', 'related_work'],
      retrieval_signals: [
        'graph:Decision(decided_in,d=1)',
        'explicit_reference',
        'hybrid_search',
        'unknown_signal',
      ],
      freshness: 'fresh',
      verification_state: 'confirmed_decision',
    })

    expect(getSourceSignalLabels(enriched)).toEqual([
      'decision receipt',
      'source evidence',
      'related work',
      'graph path',
      'fresh source',
      'confirmed decision',
    ])
    expect(formatRetrievalTarget('graph_neighborhood')).toBe('graph path')
    expect(formatRetrievalSignal('unknown_signal')).toBeNull()
  })

  it('formats freshness and verification labels without absent-field fallbacks', () => {
    expect(formatFreshnessLabel('fresh')).toBe('fresh source')
    expect(formatFreshnessLabel('stale')).toBe('stale source')
    expect(formatFreshnessLabel('unknown')).toBe('unknown freshness')
    expect(formatFreshnessLabel(undefined)).toBeNull()

    expect(formatVerificationLabel('confirmed_decision')).toBe(
      'confirmed decision'
    )
    expect(formatVerificationLabel('source_backed_candidate')).toBe(
      'source-backed candidate'
    )
    expect(formatVerificationLabel('generated_context')).toBe(
      'generated context'
    )
    expect(formatVerificationLabel(undefined)).toBeNull()
  })

  it('formats graph paths from direct or nested backend feature fields', () => {
    expect(
      formatGraphPath(
        source({
          graph_path: [
            { node_id: 'RD-973', entity_type: 'Ticket', title: 'RD-973' },
            {
              node_id: 'slack-1',
              entity_type: 'SlackThread',
              title: 'Slack thread',
              relationship: 'discussed_in',
            },
            {
              node_id: 'decision-1',
              entity_type: 'Decision',
              title: 'Decision',
              relationship: 'decided_in',
            },
          ],
        })
      )
    ).toBe('RD-973 -> Slack thread -> Decision')

    expect(
      formatGraphPath(
        source({
          features: {
            graph_path: [
              { node_id: 'decision-1', entity_type: 'Decision' },
              { node_id: 'source-1', entity_type: 'SlackMessage' },
            ],
          },
        })
      )
    ).toBe('Decision -> SlackMessage')
  })

  it('detects explanation availability from selected or suppressed reasons', () => {
    expect(hasSourceExplanation(source({ why_selected: 'Confirmed source.' }))).toBe(
      true
    )
    expect(hasSourceExplanation(source({ suppress_reason: 'stale duplicate' }))).toBe(
      true
    )
  })
})
