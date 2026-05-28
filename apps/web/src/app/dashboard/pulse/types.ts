import type { MissedDecisionReviewSuggestion, MissedDecisionScanStatus } from '@/lib/api'

export interface NeedsYouItem {
  id: string
  ticketId: string
  person: string
  sinceDay: string
  assignedToCurrentUser: boolean
  ageMs: number
}

export interface TopUrgentItem {
  person: string
  ticketId: string
  sinceDay: string
}

export interface Delta {
  decisions: {
    count: number
    items: ReadonlyArray<{ id: string; createdAt: string }>
  }
  sources: {
    count: number
    items: ReadonlyArray<SourceUpdateItem>
  }
  needsYou: {
    topUrgentItem: TopUrgentItem | null
    items: ReadonlyArray<NeedsYouItem>
  }
}

export interface SourceUpdateItem {
  id: string
  eventType: string
  createdAt: string
  metadata: Record<string, unknown>
}

export interface HeadlineCopy {
  headline: string
  subtext: string
}

export interface WorkspaceFreshness {
  lastUpdatedAt: Date | null
}

export interface MissedDecisionReviewActions {
  saveAsNewDecision: (candidateId: string) => Promise<void>
  addAsEvidence: (candidateId: string) => Promise<void>
  defer: (candidateId: string) => Promise<void>
  dismiss: (candidateId: string) => Promise<void>
  ignoreDuplicate: (candidateId: string) => Promise<void>
}

export interface NeedsReviewSuggestionsState {
  needsReviewSuggestions: MissedDecisionReviewSuggestion[]
  needsReviewError: string | null
  missedDecisionScans: MissedDecisionScanStatus[]
}

export interface WorkspaceSnapshotItem {
  id: string
  label: string
  value: string
  detail: string
  href?: string
}
