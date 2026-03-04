/**
 * Shared types, data fetching, and utility functions for the context feed.
 *
 * Consumed by the feed list (Plan 02) and detail view (Plan 03).
 */

import { createClient } from '@/lib/supabase/client'
import { toast } from 'sonner'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ContextPageRow {
  id: string
  title: string
  ticket_identifier: string | null
  status: 'draft' | 'generating' | 'ready' | 'stale' | 'error'
  sources: Array<{ type: string; id: string; title: string; relevance_score: number }>
  updated_at: string
  generated_at: string | null
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const STATUS_COLORS: Record<string, { dot: string; border: string }> = {
  ready: { dot: 'bg-emerald-500', border: 'border-l-emerald-500' },
  generating: { dot: 'bg-amber-500', border: 'border-l-amber-500' },
  stale: { dot: 'bg-orange-500', border: 'border-l-orange-500' },
  error: { dot: 'bg-red-500', border: 'border-l-red-500' },
  draft: { dot: 'bg-muted-foreground/30', border: 'border-l-transparent' },
}

export const FILTER_OPTIONS = ['all', 'ready', 'generating', 'stale', 'error'] as const
export type StatusFilter = (typeof FILTER_OPTIONS)[number]

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------

/**
 * Fetch all non-deleted context pages ordered by most recently updated.
 * Selects only the columns needed for the feed listing.
 */
export async function fetchContextPages(): Promise<ContextPageRow[]> {
  const supabase = createClient()

  const { data, error } = await supabase
    .from('context_pages')
    .select('id, title, ticket_identifier, status, sources, updated_at, generated_at')
    .is('deleted_at', null)
    .order('updated_at', { ascending: false })

  if (error) throw error
  return (data ?? []) as ContextPageRow[]
}

/**
 * Fetch a single context page by ID with all columns (for detail view).
 * Throws if the page is not found or has been soft-deleted.
 */
export async function fetchContextPageById(id: string) {
  const supabase = createClient()

  const { data, error } = await supabase
    .from('context_pages')
    .select('*')
    .eq('id', id)
    .is('deleted_at', null)
    .single()

  if (error) throw error
  return data
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

/**
 * Extract the AI Implementation Prompt section from markdown content.
 * Falls back to the full content if the heading is not found.
 */
export function extractAIPrompt(content: string): string {
  const heading = /^##\s+(?:AI\s+)?Implementation\s+Prompt/im
  const match = heading.exec(content)
  if (!match) return content
  return content.slice(match.index)
}

/**
 * Copy text to clipboard with toast feedback.
 */
export async function copyToClipboard(text: string, label?: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text)
    toast(label ?? 'Copied to clipboard')
  } catch {
    toast.error('Failed to copy to clipboard')
  }
}
