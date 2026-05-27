'use client'

import { useState } from 'react'
import { BadgeCheck, ChevronDown, Clock3, Network } from 'lucide-react'
import { cn } from '@/lib/utils'
import type {
  ContextPageSource,
  ContextPageSourceFeatures,
  ContextPageSourceGraphPathStep,
} from '@/lib/api'

const TARGET_LABELS: Record<string, string> = {
  decision_receipts: 'decision receipt',
  source_evidence: 'source evidence',
  graph_neighborhood: 'graph path',
  related_work: 'related work',
}

const SIGNAL_LABELS: Record<string, string> = {
  explicit_link: 'source evidence',
  explicit_reference: 'source evidence',
  hybrid_search: 'related work',
  reranked: 'reranked',
  rerank: 'reranked',
}

const SOURCE_ORIGINALITY_LABELS: Record<string, string> = {
  source_of_record: 'primary evidence',
  generated_context: 'generated context',
}

function text(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function features(source: ContextPageSource): ContextPageSourceFeatures {
  return source.features ?? source.retrieval_features ?? {}
}

function unique(values: Array<string | null>): string[] {
  return Array.from(new Set(values.filter((value): value is string => Boolean(value))))
}

export function formatRetrievalSignal(signal: string | null | undefined): string | null {
  const value = text(signal)
  if (!value) return null
  if (value.startsWith('graph:')) return 'graph path'
  return SIGNAL_LABELS[value] ?? null
}

export function formatRetrievalTarget(target: string | null | undefined): string | null {
  const value = text(target)
  if (!value) return null
  return TARGET_LABELS[value] ?? null
}

export function formatFreshnessLabel(value: unknown): string | null {
  switch (text(value)) {
    case 'fresh':
      return 'fresh source'
    case 'stale':
      return 'stale source'
    case 'superseded':
      return 'superseded source'
    case 'source_of_record':
      return 'confirmed source of record'
    case 'unknown':
      return 'unknown freshness'
    default:
      return null
  }
}

export function formatVerificationLabel(value: unknown): string | null {
  switch (text(value)) {
    case 'confirmed_decision':
      return 'confirmed decision'
    case 'source_backed_candidate':
      return 'source-backed candidate'
    case 'source_evidence':
      return 'source evidence'
    case 'generated_context':
      return 'generated context'
    case 'unknown':
      return 'unknown verification'
    default:
      return null
  }
}

export function graphPathSteps(
  source: ContextPageSource
): ContextPageSourceGraphPathStep[] {
  const direct = source.graph_path
  if (Array.isArray(direct) && direct.length > 0) return direct
  const nested = features(source).graph_path
  return Array.isArray(nested) ? nested : []
}

export function formatGraphPathStep(
  step: ContextPageSourceGraphPathStep
): string | null {
  return text(step.title) ?? text(step.entity_type) ?? text(step.node_id)
}

export function formatGraphPath(
  source: ContextPageSource
): string | null {
  const labels = graphPathSteps(source)
    .map(formatGraphPathStep)
    .filter((value): value is string => Boolean(value))
  return labels.length > 0 ? labels.join(' -> ') : null
}

export function formatGraphDepthLabel(source: ContextPageSource): string | null {
  const depth = features(source).graph_depth
  return typeof depth === 'number' ? `graph depth ${depth}` : null
}

export function getSourceSignalLabels(source: ContextPageSource): string[] {
  const sourceFeatures = features(source)
  return unique([
    ...(source.retrieval_targets ?? source.targets ?? []).map(formatRetrievalTarget),
    ...(source.retrieval_signals ?? []).map(formatRetrievalSignal),
    formatFreshnessLabel(source.freshness ?? sourceFeatures.freshness_state),
    formatVerificationLabel(source.verification_state ?? sourceFeatures.verification_state),
    SOURCE_ORIGINALITY_LABELS[text(source.source_originality ?? sourceFeatures.source_originality) ?? ''] ?? null,
    formatGraphDepthLabel(source),
  ])
}

export function hasSourceExplanation(source: ContextPageSource): boolean {
  return hasSourcePathDetails(source)
}

export function hasSourcePathDetails(source: ContextPageSource): boolean {
  const sourceFeatures = features(source)
  return Boolean(
    text(source.why_selected) ||
      text(source.suppress_reason) ||
      text(source.route_omission_reason) ||
      text(source.source_explanation) ||
      graphPathSteps(source).length > 0 ||
      formatFreshnessLabel(source.freshness ?? sourceFeatures.freshness_state) ||
      formatVerificationLabel(
        source.verification_state ?? sourceFeatures.verification_state
      )
  )
}

export function sourceDisclosureId(
  prefix: string,
  groupName: string,
  index: number
): string {
  const group = groupName.toLowerCase().replace(/[^a-z0-9_-]+/g, '-')
  return `${prefix}-${group}-${index}`
}

export function RetrievalSignalChip({ label }: { label: string }) {
  return (
    <span className="inline-flex min-h-5 items-center rounded-md border border-border/70 bg-muted/30 px-1.5 py-0.5 text-[11px] font-normal leading-tight text-muted-foreground">
      {label}
    </span>
  )
}

export function FreshnessLabel({ source }: { source: ContextPageSource }) {
  const label = formatFreshnessLabel(
    source.freshness ?? features(source).freshness_state
  )
  if (!label) return null

  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <Clock3 className="h-3 w-3" aria-hidden="true" />
      {label}
    </span>
  )
}

export function VerificationLabel({ source }: { source: ContextPageSource }) {
  const label = formatVerificationLabel(
    source.verification_state ?? features(source).verification_state
  )
  if (!label) return null

  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
      <BadgeCheck className="h-3 w-3" aria-hidden="true" />
      {label}
    </span>
  )
}

export function GraphPathLine({ source }: { source: ContextPageSource }) {
  const path = formatGraphPath(source)
  if (!path) return null

  return (
    <div className="flex items-start gap-1.5 text-xs text-muted-foreground">
      <Network className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
      <span className="font-mono leading-relaxed text-foreground/75">{path}</span>
    </div>
  )
}

export function SourcePathDisclosure({
  source,
  disclosureId,
}: {
  source: ContextPageSource
  disclosureId: string
}) {
  const [open, setOpen] = useState(false)
  if (!hasSourcePathDetails(source)) return null

  const whySelected = text(source.why_selected)
  const suppressedBecause = text(source.suppress_reason ?? source.route_omission_reason)
  const explanation = text(source.source_explanation)

  return (
    <div className="mt-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={disclosureId}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex min-h-10 items-center gap-1.5 rounded-md px-0 text-xs font-medium text-primary outline-none transition-[color,transform] duration-150 ease-out hover:text-primary/85 active:scale-[0.96] focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        <ChevronDown
          className={cn(
            'h-3.5 w-3.5 transition-transform duration-150',
            open ? 'rotate-180' : 'rotate-0'
          )}
          aria-hidden="true"
        />
        Show source path
      </button>

      {open && (
        <div
          id={disclosureId}
          className="mt-1.5 space-y-2 rounded-md border border-border/70 bg-card/70 p-2.5 text-xs text-muted-foreground shadow-sm animate-in fade-in-0 slide-in-from-top-1 duration-150 motion-reduce:slide-in-from-top-0"
        >
          {whySelected && (
            <p className="text-foreground/80 text-wrap pretty">{whySelected}</p>
          )}
          {suppressedBecause && (
            <p>
              <span className="font-medium text-foreground/80">Not used</span>
              {`: ${suppressedBecause}`}
            </p>
          )}
          {!whySelected && explanation && (
            <p className="text-foreground/80 text-wrap pretty">{explanation}</p>
          )}
          <div className="flex flex-wrap gap-x-3 gap-y-1">
            <FreshnessLabel source={source} />
            <VerificationLabel source={source} />
          </div>
          <GraphPathLine source={source} />
        </div>
      )}
    </div>
  )
}
