import type { ApiNode } from '@/components/graph/types'

export interface DecisionNodeView {
  id: string
  title: string
  rationale: string | null
  sourceQuote: string | null
  sourceChannel: string | null
  authorName: string | null
  participants: string[]
  date: string | null
  confidence: number | null
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
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
    sourceChannel: asString(props.source_channel),
    authorName: asString(props.author_name) ?? asString(props.person_name) ?? participants[0] ?? null,
    participants,
    date: asString(props.date),
    confidence: asNumber(props.confidence),
  }
}

export function sortDecisions(a: DecisionNodeView, b: DecisionNodeView): number {
  return (b.date ?? '').localeCompare(a.date ?? '')
}
