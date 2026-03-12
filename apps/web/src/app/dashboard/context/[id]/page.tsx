'use client'

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft,
  Copy,
  RefreshCw,
  Loader2,
  ExternalLink,
  MessageSquare,
  GitPullRequest,
  Code2,
  FileText,
  Video,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from 'lucide-react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { formatRelativeTime } from '@/lib/utils'
import {
  fetchContextPageById,
  extractAIPrompt,
  copyToClipboard,
  STATUS_COLORS,
} from '@/lib/context-feed'
import { createClient } from '@/lib/supabase/client'
import { useContextPagesRealtime } from '@/hooks/use-context-pages-realtime'
import { apiFetchSSE, SOURCE_LABELS } from '@/lib/api'
import { GenerationProgress } from '@/components/generation-progress'
import type { GenerationState } from '@/lib/context-feed'
import type { RealtimePostgresChangesPayload } from '@supabase/supabase-js'

// ---------------------------------------------------------------------------
// Source type config
// ---------------------------------------------------------------------------

const SOURCE_TYPE_CONFIG: Record<
  string,
  { label: string; icon: React.ElementType; group: string }
> = {
  linear_ticket: { label: 'Ticket', icon: CheckCircle2, group: 'Linear' },
  linear_comment: { label: 'Comment', icon: MessageSquare, group: 'Linear' },
  slack_message: { label: 'Message', icon: MessageSquare, group: 'Slack' },
  meeting_transcript: { label: 'Meeting', icon: Video, group: 'Meetings' },
  meeting_segment: { label: 'Segment', icon: Video, group: 'Meetings' },
  github_pull_request: { label: 'Pull Request', icon: GitPullRequest, group: 'GitHub' },
  github_review: { label: 'Review', icon: GitPullRequest, group: 'GitHub' },
  code_chunk: { label: 'Code', icon: Code2, group: 'GitHub' },
  notion_page: { label: 'Page', icon: FileText, group: 'Notion' },
  jira_issue: { label: 'Issue', icon: CheckCircle2, group: 'Jira' },
  jira_comment: { label: 'Comment', icon: MessageSquare, group: 'Jira' },
  context_page: { label: 'Context', icon: FileText, group: 'Other' },
}

const GROUP_ICONS: Record<string, React.ElementType> = {
  Linear: CheckCircle2,
  Slack: MessageSquare,
  Meetings: Video,
  GitHub: Code2,
  Notion: FileText,
  Jira: CheckCircle2,
  Other: FileText,
}

const GROUP_COLORS: Record<string, string> = {
  Linear: 'text-violet-400',
  Slack: 'text-pink-400',
  Meetings: 'text-amber-400',
  GitHub: 'text-emerald-400',
  Notion: 'text-blue-400',
  Jira: 'text-blue-500',
  Other: 'text-muted-foreground',
}

// ---------------------------------------------------------------------------
// Markdown section parser
// ---------------------------------------------------------------------------

interface ParsedSection {
  heading: string
  content: string
}

function parseMarkdownSections(markdown: string): ParsedSection[] {
  const lines = markdown.split('\n')
  const sections: ParsedSection[] = []
  let currentHeading = ''
  let currentLines: string[] = []

  for (const line of lines) {
    const headingMatch = line.match(/^##\s+(.+)$/)
    if (headingMatch) {
      if (currentHeading || currentLines.length > 0) {
        sections.push({
          heading: currentHeading,
          content: currentLines.join('\n').trim(),
        })
      }
      currentHeading = headingMatch[1]
      currentLines = []
    } else {
      currentLines.push(line)
    }
  }

  if (currentHeading || currentLines.length > 0) {
    sections.push({
      heading: currentHeading,
      content: currentLines.join('\n').trim(),
    })
  }

  return sections.filter((s) => s.content.length > 0)
}

const SECTION_STYLES: Record<string, { accent: string; bg: string }> = {
  Summary: { accent: 'border-l-primary', bg: 'bg-primary/5' },
  'Background & Decisions': { accent: 'border-l-violet-500', bg: '' },
  Requirements: { accent: 'border-l-amber-500', bg: '' },
  'Related Work': { accent: 'border-l-blue-500', bg: '' },
  'Relevant Code': { accent: 'border-l-emerald-500', bg: '' },
  'Open Questions': { accent: 'border-l-orange-500', bg: '' },
  'Key People': { accent: 'border-l-pink-500', bg: '' },
}

function getSectionStyle(heading: string) {
  return SECTION_STYLES[heading] ?? { accent: 'border-l-border', bg: '' }
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ContextPageData {
  id: string
  title: string
  ticket_identifier: string | null
  ticket_id: string | null
  jira_issue_id: string | null
  status: string
  content: string
  sources: Array<{ type: string; id: string; title: string; relevance_score: number; url?: string }>
  generated_at: string | null
  updated_at: string
}

// ---------------------------------------------------------------------------
// Collapsible Section
// ---------------------------------------------------------------------------

function ContentSection({
  heading,
  content,
  defaultOpen = true,
}: {
  heading: string
  content: string
  defaultOpen?: boolean
}) {
  const [open, setOpen] = useState(defaultOpen)
  const style = getSectionStyle(heading)
  const isPrompt = heading.toLowerCase().includes('implementation prompt')

  return (
    <div
      className={`rounded-lg border ${style.bg} overflow-hidden transition-all duration-200`}
    >
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center gap-2 px-4 py-3 text-left border-l-2 ${style.accent} hover:bg-muted/30 transition-colors`}
      >
        {open ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
        )}
        <span className="text-sm font-semibold text-foreground">{heading}</span>
        {isPrompt && (
          <span className="ml-auto flex items-center gap-1 text-xs text-primary">
            <Sparkles className="h-3 w-3" />
            AI Prompt
          </span>
        )}
      </button>
      {open && (
        <div className={`px-4 pb-4 pt-1 border-l-2 ${style.accent}`}>
          <div className="prose prose-sm prose-invert max-w-none">
            <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Source group sidebar
// ---------------------------------------------------------------------------

function SourceSidebar({
  sources,
}: {
  sources: Array<{ type: string; id: string; title: string; relevance_score: number; url?: string }>
}) {
  const grouped = useMemo(() => {
    const groups: Record<string, typeof sources> = {}
    for (const source of sources) {
      const config = SOURCE_TYPE_CONFIG[source.type]
      const groupName = config?.group ?? 'Other'
      if (!groups[groupName]) groups[groupName] = []
      groups[groupName].push(source)
    }
    return groups
  }, [sources])

  const groupNames = Object.keys(grouped)

  if (groupNames.length === 0) {
    return (
      <div className="text-xs text-muted-foreground px-1">
        Generated from ticket description only
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {groupNames.map((groupName) => {
        const items = grouped[groupName]
        const Icon = GROUP_ICONS[groupName] ?? FileText
        const color = GROUP_COLORS[groupName] ?? 'text-muted-foreground'

        return (
          <div key={groupName}>
            <div className={`flex items-center gap-1.5 mb-1.5 ${color}`}>
              <Icon className="h-3.5 w-3.5" />
              <span className="text-xs font-medium">{groupName}</span>
              <span className="text-xs text-muted-foreground ml-auto">
                {items.length}
              </span>
            </div>
            <div className="space-y-0.5">
              {items.map((source, i) => {
                const config = SOURCE_TYPE_CONFIG[source.type]
                const inner = (
                  <>
                    <span className="text-muted-foreground shrink-0 mt-0.5">
                      {config?.label ?? source.type}
                    </span>
                    <span className="text-foreground/80 truncate flex-1">
                      {source.title}
                    </span>
                    <span className="font-mono text-muted-foreground/60 tabular-nums shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                      {Math.min(Math.round(source.relevance_score * 100), 100)}%
                    </span>
                  </>
                )
                return source.url ? (
                  <a
                    key={`${source.type}-${source.id}-${i}`}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-muted/30 transition-colors group cursor-pointer"
                  >
                    {inner}
                  </a>
                ) : (
                  <div
                    key={`${source.type}-${source.id}-${i}`}
                    className="flex items-start gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-muted/30 transition-colors group"
                  >
                    {inner}
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function ContextDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [page, setPage] = useState<ContextPageData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [generation, setGeneration] = useState<GenerationState | null>(null)
  const [jiraSiteUrl, setJiraSiteUrl] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Detect provider from sources (works for all pages, even those without jira_issue_id FK)
  const isJiraTicket = useMemo(
    () => page?.sources?.some((s) => s.type === 'jira_issue' || s.type === 'jira_comment')
      ?? !!page?.jira_issue_id,
    [page?.sources, page?.jira_issue_id],
  )

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

  // Fetch Jira site URL when page is a Jira ticket
  useEffect(() => {
    if (!isJiraTicket) return
    const supabase = createClient()
    supabase
      .from('workspace_integrations')
      .select('config')
      .eq('provider', 'jira')
      .maybeSingle()
      .then(({ data }) => {
        const config = data?.config as Record<string, unknown> | undefined
        // Prefer site_url (actual URL like "https://foo.atlassian.net")
        // Fall back to external_name for configs saved before site_url was added
        const url = config?.site_url
        if (typeof url === 'string' && url) {
          setJiraSiteUrl(url)
        } else {
          const name = config?.external_name
          if (typeof name === 'string' && name) {
            setJiraSiteUrl(`https://${name}.atlassian.net`)
          }
        }
      })
  }, [isJiraTicket])

  useEffect(() => {
    loadPage()
  }, [loadPage])

  useContextPagesRealtime({
    onUpdate: useCallback(
      (payload: RealtimePostgresChangesPayload<Record<string, unknown>>) => {
        const updated = payload.new as Record<string, unknown>
        if (updated?.id === id) {
          loadPage()
        }
      },
      [id, loadPage]
    ),
  })

  const handleCopyPrompt = useCallback(async () => {
    if (!page?.content) return
    const promptText = extractAIPrompt(page.content)
    await copyToClipboard(promptText, 'Prompt copied to clipboard')
  }, [page?.content])

  const startGeneration = useCallback((ticketIdentifier: string) => {
    abortRef.current?.abort()

    setGeneration({
      ticket: ticketIdentifier,
      steps: [],
      status: 'streaming',
    })

    const controller = apiFetchSSE(
      `/api/context/${encodeURIComponent(ticketIdentifier)}/generate-stream`,
      (event) => {
        setGeneration((prev) => {
          if (!prev) return prev

          switch (event.event) {
            case 'start':
              return {
                ...prev,
                steps: event.steps.map((source) => ({
                  source,
                  label: SOURCE_LABELS[source] || source,
                  status: 'waiting' as const,
                })),
              }

            case 'step_start':
              return {
                ...prev,
                steps: prev.steps.map((s) =>
                  s.source === event.source
                    ? { ...s, status: 'active' as const, detail: 'Searching...' }
                    : s
                ),
              }

            case 'step_complete':
              return {
                ...prev,
                steps: prev.steps.map((s) =>
                  s.source === event.source
                    ? { ...s, status: 'complete' as const, count: event.count, detail: event.detail }
                    : s
                ),
              }

            case 'step_error':
              return {
                ...prev,
                steps: prev.steps.map((s) =>
                  s.source === event.source
                    ? { ...s, status: 'error' as const, detail: event.error }
                    : s
                ),
                status: 'error',
                errorMessage: event.error,
              }

            case 'complete':
              return {
                ...prev,
                status: 'complete',
                contextPageId: event.context_page_id,
              }

            case 'error':
              return {
                ...prev,
                status: 'error',
                errorMessage: event.message,
              }

            default:
              return prev
          }
        })
      },
      (error) => {
        setGeneration((prev) =>
          prev ? { ...prev, status: 'error', errorMessage: error.message } : prev
        )
      }
    )

    abortRef.current = controller
  }, [])

  const handleRegenerate = useCallback(() => {
    if (!page?.ticket_identifier) return
    startGeneration(page.ticket_identifier)
  }, [page?.ticket_identifier, startGeneration])

  useEffect(() => {
    if (generation?.status === 'complete') {
      const timer = setTimeout(() => {
        loadPage()
        setGeneration(null)
      }, 1500)
      return () => clearTimeout(timer)
    }
  }, [generation?.status, loadPage])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  // Parse content into sections
  const { sections, promptText, hasPromptSection } = useMemo(() => {
    if (!page?.content) return { sections: [], promptText: '', hasPromptSection: false }
    const prompt = extractAIPrompt(page.content)
    const hasPrompt = prompt !== page.content
    const mainContent = hasPrompt
      ? page.content.slice(0, page.content.indexOf(prompt))
      : page.content
    const parsed = parseMarkdownSections(mainContent)
    return { sections: parsed, promptText: prompt, hasPromptSection: hasPrompt }
  }, [page?.content])

  // Source type breakdown for header
  const sourceBreakdown = useMemo(() => {
    if (!page?.sources?.length) return ''
    const groups: Record<string, number> = {}
    for (const s of page.sources) {
      const config = SOURCE_TYPE_CONFIG[s.type]
      const group = config?.group ?? 'Other'
      groups[group] = (groups[group] ?? 0) + 1
    }
    return Object.entries(groups)
      .map(([g, n]) => `${n} ${g}`)
      .join(', ')
  }, [page?.sources])

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-6 w-3/4" />
        <div className="flex items-center gap-3">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-32" />
        </div>
        <div className="flex gap-6 mt-6">
          <div className="w-56 shrink-0 space-y-3">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-16 mt-4" />
            <Skeleton className="h-4 w-full" />
          </div>
          <div className="flex-1 space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="h-32 w-full mt-4" />
            <Skeleton className="h-4 w-3/4 mt-4" />
            <Skeleton className="h-4 w-5/6" />
          </div>
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

  return (
    <div className="animate-fade-in-up">
      {/* Back link */}
      <Link
        href="/dashboard/context"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="h-4 w-4" />
        Context
      </Link>

      {/* Header */}
      <div className="mt-5">
        <h1 className="text-xl font-semibold text-foreground">{page.title}</h1>
        <div className="flex items-center gap-3 mt-1.5">
          {page.ticket_identifier && (
            <span className="font-mono text-sm text-muted-foreground">
              {page.ticket_identifier}
            </span>
          )}
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
              page.status === 'ready'
                ? 'bg-emerald-500/10 text-emerald-400'
                : page.status === 'stale'
                  ? 'bg-amber-500/10 text-amber-400'
                  : page.status === 'generating'
                    ? 'bg-blue-500/10 text-blue-400'
                    : 'bg-muted text-muted-foreground'
            }`}
          >
            <span className={`h-2 w-2 rounded-full ${colors.dot}`} />
            {page.status}
          </span>
          {page.generated_at && (
            <span className="text-sm text-muted-foreground">
              Generated {formatRelativeTime(page.generated_at)}
            </span>
          )}
        </div>

        {/* Action bar */}
        <div className="flex items-center gap-2 mt-4">
          <Button variant="outline" onClick={handleCopyPrompt}>
            <Copy className="h-4 w-4 mr-1.5" />
            Copy Prompt
          </Button>
          <Button
            variant="outline"
            onClick={handleRegenerate}
            disabled={generation !== null || !page.ticket_identifier}
          >
            {generation ? (
              <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4 mr-1.5" />
            )}
            {generation ? 'Regenerating...' : 'Regenerate'}
          </Button>
          {page.ticket_identifier && isJiraTicket && jiraSiteUrl && (
            <Button variant="ghost" asChild>
              <a
                href={`${jiraSiteUrl}/browse/${page.ticket_identifier}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ExternalLink className="h-4 w-4 mr-1.5" />
                Open in Jira
              </a>
            </Button>
          )}
          {page.ticket_identifier && !isJiraTicket && (
            <Button variant="ghost" asChild>
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
      </div>

      {/* Generation progress */}
      {generation && (
        <div className="mt-4">
          <GenerationProgress
            ticketIdentifier={generation.ticket}
            steps={generation.steps}
            status={generation.status}
            errorMessage={generation.errorMessage}
            onRetry={() => startGeneration(generation.ticket)}
            onDismiss={() => {
              abortRef.current?.abort()
              setGeneration(null)
            }}
          />
        </div>
      )}

      {/* Two-column layout */}
      <div className="flex gap-6 mt-6">
        {/* Left sidebar — sources */}
        <aside className="w-56 shrink-0 hidden lg:block">
          <div className="sticky top-6 space-y-5">
            {/* Source summary */}
            <div>
              <p className="section-label mb-2">
                Sources ({page.sources?.length ?? 0})
              </p>
              {sourceBreakdown && (
                <p className="text-xs text-muted-foreground mb-3">{sourceBreakdown}</p>
              )}
              <SourceSidebar sources={page.sources ?? []} />
            </div>
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 min-w-0 space-y-3">
          {/* Parsed sections with distinct visual treatment */}
          {sections.length > 0 ? (
            <div className="space-y-3 stagger-children">
              {sections.map((section, i) => (
                <ContentSection
                  key={section.heading || i}
                  heading={section.heading || 'Overview'}
                  content={section.content}
                  defaultOpen={i < 4}
                />
              ))}
            </div>
          ) : (
            /* Fallback: render raw markdown */
            <div className="rounded-lg border bg-card p-5">
              <div className="prose prose-sm prose-invert max-w-none">
                <Markdown remarkPlugins={[remarkGfm]}>{page.content}</Markdown>
              </div>
            </div>
          )}

          {/* AI Prompt section */}
          {hasPromptSection && (
            <div className="relative">
              <ContentSection
                heading="AI Implementation Prompt"
                content={promptText}
                defaultOpen={false}
              />
              <button
                onClick={handleCopyPrompt}
                className="absolute top-3 right-3 text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 z-10"
              >
                <Copy className="h-3 w-3" />
                Copy
              </button>
            </div>
          )}
        </main>
      </div>

      {/* Mobile sources — shown below content on small screens */}
      <div className="lg:hidden mt-8">
        <p className="section-label mb-3">Sources ({page.sources?.length ?? 0})</p>
        <div className="rounded-lg border bg-card p-4">
          <SourceSidebar sources={page.sources ?? []} />
        </div>
      </div>
    </div>
  )
}
