// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { MissedDecisionScanStatus } from '@/lib/api'
import { DecisionScanProgress } from './decision-scan-progress'

function scan(
  overrides: Partial<MissedDecisionScanStatus> = {}
): MissedDecisionScanStatus {
  return {
    id: 'scan-1',
    source_type: 'slack_message',
    status: 'running',
    sources_scanned: 4,
    sources_total: 10,
    progress_percent: 40,
    candidates_created: 0,
    review_candidates: 0,
    auto_saved: 0,
    suppressed: 0,
    source_resource_id: null,
    source_window_start: '2026-05-25T08:00:00Z',
    source_window_end: '2026-05-25T09:00:00Z',
    started_at: '2026-05-25T09:00:00Z',
    completed_at: null,
    error_message: null,
    ...overrides,
  }
}

describe('DecisionScanProgress', () => {
  it('renders nothing when there are no active or recent scans', () => {
    const { container } = render(<DecisionScanProgress scans={[]} />)

    expect(container.textContent).toBe('')
  })

  it('renders queued and determinate running scan states', () => {
    const { rerender } = render(
      <DecisionScanProgress scans={[scan({ status: 'queued' })]} />
    )

    expect(screen.getByText('Waiting to scan Slack for missed decisions')).toBeTruthy()

    rerender(<DecisionScanProgress scans={[scan()]} />)

    expect(screen.getByText('Scanning Slack for missed decisions')).toBeTruthy()
    expect(screen.getByText('4 of 10 messages checked · 0 need review')).toBeTruthy()
    expect(screen.getByRole('progressbar').getAttribute('aria-valuenow')).toBe('40')
  })

  it('shows candidates found during an active scan', () => {
    render(
      <DecisionScanProgress scans={[scan({
        candidates_created: 4,
        review_candidates: 2,
        auto_saved: 1,
        suppressed: 1,
      })]} />
    )

    expect(screen.getByText('4 candidates found · 2 need review · 1 auto-saved · 1 suppressed')).toBeTruthy()
  })

  it('renders candidate and empty completed states', () => {
    const { rerender } = render(
      <DecisionScanProgress
        scans={[scan({ status: 'succeeded', candidates_created: 3, review_candidates: 2, auto_saved: 1 })]}
      />
    )

    expect(screen.getByText('Found 3 candidates')).toBeTruthy()
    expect(screen.getByText('3 candidates found · 2 need review · 1 auto-saved')).toBeTruthy()

    rerender(
      <DecisionScanProgress
        scans={[scan({ status: 'succeeded', candidates_created: 0 })]}
      />
    )

    expect(screen.getByText('No missed decisions in this scan')).toBeTruthy()
  })

  it('renders failed scans with short error copy', () => {
    render(
      <DecisionScanProgress
        scans={[
          scan({
            status: 'failed',
            error_message: 'Extractor timeout after Slack source batch finished',
          }),
        ]}
      />
    )

    expect(screen.getByText('Scan paused')).toBeTruthy()
    expect(screen.getByText('Extractor timeout after Slack source batch finished')).toBeTruthy()
  })
})
