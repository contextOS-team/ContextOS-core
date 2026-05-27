// @vitest-environment jsdom

import { createElement } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
  sourceDisclosureId,
  SourcePathDisclosure,
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
    expect(formatFreshnessLabel('superseded')).toBe('superseded source')
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

  it('does not treat signal chips alone as source path disclosure data', () => {
    const signalOnly = source({ retrieval_signals: ['hybrid_search'] })

    expect(getSourceSignalLabels(signalOnly)).toEqual(['related work'])
    expect(hasSourceExplanation(signalOnly)).toBe(false)
  })

  it('generates stable source disclosure ids per viewport', () => {
    expect(sourceDisclosureId('context-source-desktop', 'Related Work', 2)).toBe(
      'context-source-desktop-related-work-2'
    )
    expect(sourceDisclosureId('context-source-desktop', 'Slack', 0)).not.toBe(
      sourceDisclosureId('context-source-mobile', 'Slack', 0)
    )
  })

  it('renders an accessible disclosure only when path details exist', async () => {
    render(
      createElement(SourcePathDisclosure, {
        source: source({ why_selected: 'Selected through a linked decision.' }),
        disclosureId: 'source-path-test',
      })
    )

    const button = screen.getByRole('button', { name: 'Show source path' })
    expect(button.getAttribute('aria-expanded')).toBe('false')
    expect(button.getAttribute('aria-controls')).toBe('source-path-test')
    expect(screen.queryByText('Selected through a linked decision.')).toBeNull()

    await userEvent.click(button)

    expect(button.getAttribute('aria-expanded')).toBe('true')
    expect(screen.getByText('Selected through a linked decision.')).toBeTruthy()
    expect(document.getElementById('source-path-test')).not.toBeNull()
  })
})
