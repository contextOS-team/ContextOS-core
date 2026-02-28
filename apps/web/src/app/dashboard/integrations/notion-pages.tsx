'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  FileText,
  Database,
  ExternalLink,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { getNotionPages, type NotionPageInfo } from '@/lib/api'

const PAGE_SIZE = 10

interface NotionPagesProps {
  /** Increment to trigger a re-fetch (e.g. after re-sync completes). */
  refreshKey?: number
}

export function NotionPages({ refreshKey }: NotionPagesProps) {
  const [pages, setPages] = useState<NotionPageInfo[]>([])
  const [total, setTotal] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const fetchPage = useCallback(async (page: number) => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getNotionPages(page, PAGE_SIZE)
      setPages(data.pages || [])
      setTotal(data.total)
      setCurrentPage(data.page)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load pages')
    } finally {
      setIsLoading(false)
    }
  }, [])

  // Single effect: fetch page 1 on mount and when refreshKey changes
  useEffect(() => {
    fetchPage(1)
  }, [fetchPage, refreshKey])

  function goToPage(page: number) {
    fetchPage(page)
  }

  if (isLoading && pages.length === 0) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        Loading pages...
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <p className="text-xs font-medium text-muted-foreground">
        {total} {total === 1 ? 'page' : 'pages'} synced
      </p>

      {/* Error */}
      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      {/* Page list */}
      <div className="space-y-0.5 rounded-md border bg-background">
        {pages.length === 0 ? (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            No pages synced yet
          </p>
        ) : (
          pages.map((page) => (
            <div
              key={page.id}
              className="flex items-center gap-3 px-3 py-2 hover:bg-muted/50"
            >
              {page.page_type === 'database_entry' ? (
                <Database className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              ) : (
                <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              )}
              <span className="min-w-0 flex-1 truncate text-xs font-medium">
                {page.title}
              </span>
              {page.page_type && (
                <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                  {page.page_type === 'database_entry' ? 'db entry' : page.page_type}
                </span>
              )}
              {page.url && (
                <a
                  href={page.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-[11px] text-muted-foreground">
            Page {currentPage} of {totalPages}
          </p>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="xs"
              disabled={currentPage <= 1 || isLoading}
              onClick={() => goToPage(currentPage - 1)}
              className="h-6 w-6 p-0"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="xs"
              disabled={currentPage >= totalPages || isLoading}
              onClick={() => goToPage(currentPage + 1)}
              className="h-6 w-6 p-0"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
