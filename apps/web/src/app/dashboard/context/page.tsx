'use client'

import { useCallback, useState } from 'react'
import { Search, Sparkles, Loader2, FileText, Clock, Zap, ExternalLink } from 'lucide-react'
import {
  getContextPage,
  generateContextPage,
  searchContext,
  type ContextPageResponse,
  type SearchResponse,
} from '@/lib/api'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

type Tab = 'lookup' | 'search'

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

export default function ContextPage() {
  const [tab, setTab] = useState<Tab>('lookup')

  // Lookup state
  const [ticketId, setTicketId] = useState('')
  const [contextPage, setContextPage] = useState<ContextPageResponse | null>(null)
  const [lookupLoading, setLookupLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [lookupError, setLookupError] = useState<string | null>(null)

  // Search state
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResponse | null>(null)
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchError, setSearchError] = useState<string | null>(null)

  const handleLookup = useCallback(async () => {
    if (!ticketId.trim()) return
    setLookupLoading(true)
    setLookupError(null)
    setContextPage(null)
    try {
      const page = await getContextPage(ticketId.trim().toUpperCase())
      setContextPage(page)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load context page'
      if (msg.includes('404')) {
        setLookupError(`No context page found for ${ticketId.toUpperCase()}. Click "Generate" to create one.`)
      } else {
        setLookupError(msg)
      }
    } finally {
      setLookupLoading(false)
    }
  }, [ticketId])

  const handleGenerate = useCallback(async () => {
    if (!ticketId.trim()) return
    setGenerating(true)
    setLookupError(null)
    try {
      await generateContextPage(ticketId.trim().toUpperCase())
      // Poll for completion
      let attempts = 0
      const poll = async () => {
        attempts++
        try {
          const page = await getContextPage(ticketId.trim().toUpperCase())
          if (page.status === 'ready') {
            setContextPage(page)
            setGenerating(false)
            return
          }
        } catch {
          // Not ready yet
        }
        if (attempts < 30) {
          setTimeout(poll, 2000)
        } else {
          setGenerating(false)
          setLookupError('Generation is taking longer than expected. Try refreshing in a minute.')
        }
      }
      setTimeout(poll, 3000) // First check after 3s
    } catch (err) {
      setGenerating(false)
      setLookupError(err instanceof Error ? err.message : 'Failed to start generation')
    }
  }, [ticketId])

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return
    setSearchLoading(true)
    setSearchError(null)
    setSearchResults(null)
    try {
      const results = await searchContext(searchQuery.trim(), undefined, 20)
      setSearchResults(results)
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      setSearchLoading(false)
    }
  }, [searchQuery])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Context Engine</h2>
        <p className="text-muted-foreground text-sm mt-1">
          AI-generated context pages and semantic search across all your data
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b pb-2">
        <button
          onClick={() => setTab('lookup')}
          className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
            tab === 'lookup'
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          }`}
        >
          <FileText className="h-4 w-4 inline mr-2" />
          Ticket Context
        </button>
        <button
          onClick={() => setTab('search')}
          className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
            tab === 'search'
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:text-foreground hover:bg-muted'
          }`}
        >
          <Search className="h-4 w-4 inline mr-2" />
          Semantic Search
        </button>
      </div>

      {/* Ticket Context Tab */}
      {tab === 'lookup' && (
        <div className="space-y-4">
          {/* Input */}
          <div className="flex gap-3">
            <Input
              placeholder="Enter ticket identifier (e.g. CON-16)"
              value={ticketId}
              onChange={(e) => setTicketId(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleLookup()}
              className="max-w-sm"
            />
            <Button onClick={handleLookup} disabled={lookupLoading || !ticketId.trim()}>
              {lookupLoading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <FileText className="h-4 w-4 mr-2" />
              )}
              Look Up
            </Button>
            <Button
              onClick={handleGenerate}
              disabled={generating || !ticketId.trim()}
              variant="outline"
            >
              {generating ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Sparkles className="h-4 w-4 mr-2" />
              )}
              {generating ? 'Generating...' : 'Generate'}
            </Button>
          </div>

          {/* Error */}
          {lookupError && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {lookupError}
            </div>
          )}

          {/* Generating indicator */}
          {generating && (
            <Card>
              <CardContent className="py-8">
                <div className="flex flex-col items-center gap-3 text-center">
                  <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  <div>
                    <p className="font-medium">Generating context page...</p>
                    <p className="text-sm text-muted-foreground">
                      Finding related content, building embeddings, and synthesizing with AI.
                      This may take 10-30 seconds.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Context Page Result */}
          {contextPage && !generating && (
            <div className="space-y-4">
              {/* Metadata bar */}
              <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
                <span className="flex items-center gap-1">
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      contextPage.status === 'ready'
                        ? 'bg-green-500'
                        : contextPage.status === 'generating'
                        ? 'bg-yellow-500'
                        : contextPage.status === 'stale'
                        ? 'bg-orange-500'
                        : 'bg-gray-400'
                    }`}
                  />
                  {contextPage.status}
                </span>
                {contextPage.generated_at && (
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {new Date(contextPage.generated_at).toLocaleString()}
                  </span>
                )}
                {contextPage.generation_model && (
                  <span className="flex items-center gap-1">
                    <Zap className="h-3 w-3" />
                    {contextPage.generation_model}
                  </span>
                )}
                {contextPage.generation_tokens_used && (
                  <span>{contextPage.generation_tokens_used.toLocaleString()} tokens</span>
                )}
              </div>

              {/* Content */}
              <Card>
                <CardHeader>
                  <CardTitle>{contextPage.title}</CardTitle>
                  <CardDescription>{contextPage.ticket_identifier}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="prose prose-sm max-w-none dark:prose-invert whitespace-pre-wrap">
                    {contextPage.content}
                  </div>
                </CardContent>
              </Card>

              {/* Sources */}
              {contextPage.sources.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">
                      Sources ({contextPage.sources.length})
                    </CardTitle>
                    <CardDescription>
                      Content used to generate this context page
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {contextPage.sources.map((source, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm"
                        >
                          <div className="flex items-center gap-2">
                            <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-medium">
                              {SOURCE_TYPE_LABELS[source.type] || source.type}
                            </span>
                            <span className="text-foreground">{source.title}</span>
                          </div>
                          <span className="text-muted-foreground">
                            {(source.relevance_score * 100).toFixed(0)}% relevant
                          </span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      )}

      {/* Semantic Search Tab */}
      {tab === 'search' && (
        <div className="space-y-4">
          {/* Search input */}
          <div className="flex gap-3">
            <Input
              placeholder="Search across all your data (e.g. 'authentication flow')"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="max-w-lg"
            />
            <Button onClick={handleSearch} disabled={searchLoading || !searchQuery.trim()}>
              {searchLoading ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Search className="h-4 w-4 mr-2" />
              )}
              Search
            </Button>
          </div>

          {/* Error */}
          {searchError && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {searchError}
            </div>
          )}

          {/* Results */}
          {searchResults && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">
                {searchResults.count} result{searchResults.count !== 1 ? 's' : ''} for &ldquo;{searchResults.query}&rdquo;
              </p>
              {searchResults.results.length === 0 ? (
                <Card>
                  <CardContent className="py-8 text-center text-muted-foreground">
                    No results found. Try a different query or make sure embeddings have been generated.
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-2">
                  {searchResults.results.map((result, i) => (
                    <Card key={i}>
                      <CardContent className="py-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="text-sm font-medium text-muted-foreground w-6">
                              {i + 1}.
                            </span>
                            <span className="rounded bg-muted px-2 py-0.5 text-xs font-medium">
                              {SOURCE_TYPE_LABELS[result.source_type] || result.source_type}
                            </span>
                            <span className="text-sm font-mono text-muted-foreground">
                              {result.source_id.slice(0, 8)}...
                            </span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-24 rounded-full bg-muted overflow-hidden">
                              <div
                                className="h-full rounded-full bg-primary"
                                style={{ width: `${result.similarity * 100}%` }}
                              />
                            </div>
                            <span className="text-sm font-medium w-12 text-right">
                              {(result.similarity * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
