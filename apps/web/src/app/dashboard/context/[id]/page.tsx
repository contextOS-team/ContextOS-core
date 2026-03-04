'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Copy, RefreshCw, Loader2, ExternalLink } from 'lucide-react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from 'sonner'
import { formatRelativeTime } from '@/lib/utils'
import {
  fetchContextPageById,
  extractAIPrompt,
  copyToClipboard,
  STATUS_COLORS,
} from '@/lib/context-feed'
import { useContextPagesRealtime } from '@/hooks/use-context-pages-realtime'
import { generateContextPage } from '@/lib/api'
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js'

const SOURCE_TYPE_LABELS: Record<string, string> = {
  linear_ticket: 'Ticket',
  linear_comment: 'Comment',
  slack_message: 'Slack',
  meeting_transcript: 'Meeting',
  meeting_segment: 'Meeting Segment',
  github_pull_request: 'Pull Request',
  github_review: 'Review',
  context_page: 'Context Page',
}

interface ContextPageData {
  id: string
  title: string
  ticket_identifier: string | null
  status: string
  content: string
  sources: Array<{ type: string; id: string; title: string; relevance_score: number }>
  generated_at: string | null
  updated_at: string
}

export default function ContextDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [page, setPage] = useState<ContextPageData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isRegenerating, setIsRegenerating] = useState(false)

  const loadPage = useCallback(async () => {
    if (!id) return
    try {
      setError(null)
      const data = await fetchContextPageById(id)
      setPage(data as ContextPageData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load context page')
    } finally {
      setIsLoading(false)
    }
  }, [id])

  useEffect(() => {
    loadPage()
  }, [loadPage])

  // Realtime subscription -- update page when status changes (e.g. during regeneration)
  useContextPagesRealtime({
    onUpdate: useCallback(
      (payload: RealtimePostgresChangesPayload<Record<string, unknown>>) => {
        const updated = payload.new as Record<string, unknown>
        if (updated?.id === id) {
          // Refresh page data when our page is updated
          if (updated.status === 'ready' && isRegenerating) {
            setIsRegenerating(false)
            toast('Context page regenerated')
          }
          loadPage()
        }
      },
      [id, isRegenerating, loadPage]
    ),
  })

  const handleCopyPrompt = useCallback(async () => {
    if (!page?.content) return
    const promptText = extractAIPrompt(page.content)
    await copyToClipboard(promptText, 'Prompt copied to clipboard')
  }, [page?.content])

  const handleRegenerate = useCallback(async () => {
    if (!page?.ticket_identifier) return
    setIsRegenerating(true)
    try {
      await generateContextPage(page.ticket_identifier)
      toast(`Regenerating ${page.ticket_identifier}...`)
    } catch (err) {
      setIsRegenerating(false)
      toast.error(err instanceof Error ? err.message : 'Failed to start regeneration')
    }
  }, [page?.ticket_identifier])

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        {/* Back link skeleton */}
        <Skeleton className="h-4 w-20" />
        {/* Title skeleton */}
        <Skeleton className="h-6 w-3/4" />
        {/* Metadata row skeleton */}
        <div className="flex items-center gap-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-1.5 w-1.5 rounded-full" />
          <Skeleton className="h-4 w-32" />
        </div>
        {/* Action bar skeleton */}
        <div className="flex items-center gap-2">
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-28" />
          <Skeleton className="h-9 w-32" />
        </div>
        {/* Content area skeleton */}
        <div className="space-y-3 mt-8">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      </div>
    )
  }

  // Error state
  if (error || !page) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        <Link
          href="/dashboard/context"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Context
        </Link>
        <div className="rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error ?? 'Context page not found'}
        </div>
      </div>
    )
  }

  const colors = STATUS_COLORS[page.status] ?? STATUS_COLORS.draft
  const promptText = extractAIPrompt(page.content)
  const hasPromptSection = promptText !== page.content
  const mainContent = hasPromptSection
    ? page.content.slice(0, page.content.indexOf(promptText))
    : page.content

  return (
    <div className="space-y-0 animate-fade-in-up">
      {/* Back link */}
      <Link
        href="/dashboard/context"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Context
      </Link>

      {/* Header */}
      <h1 className="text-xl font-semibold text-foreground">{page.title}</h1>
      <div className="flex items-center gap-3 mt-1.5">
        {page.ticket_identifier && (
          <span className="font-mono text-sm text-muted-foreground">
            {page.ticket_identifier}
          </span>
        )}
        <span className={`h-1.5 w-1.5 rounded-full ${colors.dot}`} />
        <span className="text-sm text-muted-foreground capitalize">{page.status}</span>
        {page.generated_at && (
          <span className="text-sm text-muted-foreground">
            Generated {formatRelativeTime(page.generated_at)}
          </span>
        )}
      </div>

      {/* Action bar */}
      <div className="flex items-center gap-2 mt-4">
        <Button onClick={handleCopyPrompt}>
          <Copy className="h-4 w-4 mr-1.5" />
          Copy Prompt
        </Button>
        <Button
          variant="outline"
          onClick={handleRegenerate}
          disabled={isRegenerating || !page.ticket_identifier}
        >
          {isRegenerating ? (
            <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4 mr-1.5" />
          )}
          {isRegenerating ? 'Regenerating...' : 'Regenerate'}
        </Button>
        {page.ticket_identifier && (
          <Button
            variant="ghost"
            asChild
          >
            <a
              href={`https://linear.app/issue/${page.ticket_identifier}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <ExternalLink className="h-4 w-4 mr-1.5" />
              Open in Linear
            </a>
          </Button>
        )}
      </div>

      {/* Content area -- markdown rendering */}
      <div className="mt-8 prose prose-sm prose-invert max-w-none">
        <Markdown remarkPlugins={[remarkGfm]}>{mainContent}</Markdown>
      </div>

      {/* AI Prompt callout */}
      {hasPromptSection && (
        <div className="mt-8 rounded-xl border bg-elevated p-6 relative">
          <button
            onClick={handleCopyPrompt}
            className="absolute top-4 right-4 text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
          >
            <Copy className="h-3 w-3" />
            Copy
          </button>
          <div className="prose prose-sm prose-invert max-w-none">
            <Markdown remarkPlugins={[remarkGfm]}>{promptText}</Markdown>
          </div>
        </div>
      )}

      {/* Sources section */}
      {page.sources?.length > 0 && (
        <div>
          <h3 className="section-label mt-8 mb-3">
            Sources ({page.sources.length})
          </h3>
          <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
            {page.sources.map((source, i) => (
              <div key={`${source.type}-${source.id}-${i}`} className="flex items-center px-4 py-2.5">
                <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium shrink-0">
                  {SOURCE_TYPE_LABELS[source.type] ?? source.type}
                </span>
                <span className="text-sm text-foreground truncate ml-2 flex-1">
                  {source.title}
                </span>
                <span className="text-xs font-mono text-muted-foreground tabular-nums shrink-0 ml-3">
                  {(source.relevance_score * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
