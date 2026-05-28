import type { ApiNode } from '@/components/graph/types'

export interface DecisionNodeView {
  id: string
  title: string
  rationale: string | null
  sourceQuote: string | null
  sourceLink: string | null
  sourceChannel: string | null
  authorName: string | null
  participants: string[]
  date: string | null
  capturedAt: string | null
  confidence: number | null
}

export function formatDecisionChannels(value: string | null): string[] {
  if (!value) return []
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => `#${item.replace(/^#+/, '')}`)
}

export function getDecisionPeople(decision: Pick<DecisionNodeView, 'participants' | 'authorName'>): string[] {
  const names = decision.participants.length > 0
    ? decision.participants
    : decision.authorName
      ? [decision.authorName]
      : []

  return Array.from(new Set(names.map((name) => name.trim()).filter(Boolean)))
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value
      .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      .map((item) => item.trim())
    : []
}

export function toDecisionView(node: ApiNode): DecisionNodeView {
  const props = node.properties ?? {}
  const participants = asStringArray(props.participants)

  return {
    id: node.id,
    title: asString(props.description) ?? node.name,
    rationale: asString(props.rationale),
    sourceQuote: asString(props.source_quote),
    sourceLink: asString(props.source_link),
    sourceChannel: asString(props.source_channel),
    authorName: asString(props.author_name) ?? asString(props.person_name) ?? participants[0] ?? null,
    participants,
    date: asString(props.date),
    capturedAt: asString(node.created_at),
    confidence: asNumber(props.confidence),
  }
}

export function getDecisionRecencyDate(
  decision: Pick<DecisionNodeView, 'capturedAt' | 'date'>
): string | null {
  return decision.capturedAt ?? decision.date
}

export function sortDecisions(a: DecisionNodeView, b: DecisionNodeView): number {
  return (getDecisionRecencyDate(b) ?? '').localeCompare(getDecisionRecencyDate(a) ?? '')
}
