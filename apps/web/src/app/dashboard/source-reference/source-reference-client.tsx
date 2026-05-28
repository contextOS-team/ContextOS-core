'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useEffect, useMemo, useState } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { createClient } from '@/lib/supabase/client'
import { formatRelativeTime } from '@/lib/utils'

type SourceType =
  | 'slack_message'
  | 'telegram_message'
  | 'notion_page'
  | 'fathom_transcript'

type SourceConfig = {
  table: string
  select: string
  label: string
  title: (row: SourceReferenceRow) => string
  body: (row: SourceReferenceRow) => string
  meta: (row: SourceReferenceRow) => string[]
}

type SourceReferenceRow = Record<string, unknown>

const SOURCE_CONFIG: Record<SourceType, SourceConfig> = {
  slack_message: {
    table: 'slack_messages',
    select: 'id,workspace_id,text,channel_name,user_name,slack_created_at,slack_ts,channel_id',
    label: 'Slack message',
    title: (row) => textValue(row.channel_name) ? `#${textValue(row.channel_name)}` : 'Slack message',
    body: (row) => textValue(row.text) ?? '',
    meta: (row) => [
      textValue(row.user_name),
      textValue(row.slack_created_at) ? formatRelativeTime(String(row.slack_created_at)) : null,
      textValue(row.slack_ts) ? `ts ${row.slack_ts}` : null,
    ].filter(Boolean) as string[],
  },
  telegram_message: {
    table: 'telegram_messages',
    select: 'id,workspace_id,text,chat_title,from_username,from_first_name,telegram_date,message_id,chat_id',
    label: 'Telegram message',
    title: (row) => textValue(row.chat_title) ?? 'Telegram message',
    body: (row) => textValue(row.text) ?? '',
    meta: (row) => [
      textValue(row.from_username) ? `@${textValue(row.from_username)}` : textValue(row.from_first_name),
      textValue(row.telegram_date) ? formatRelativeTime(String(row.telegram_date)) : null,
      typeof row.message_id === 'number' ? `message ${row.message_id}` : null,
    ].filter(Boolean) as string[],
  },
  notion_page: {
    table: 'notion_pages',
    select: 'id,workspace_id,title,content,url,last_edited_by,notion_updated_at',
    label: 'Notion page',
    title: (row) => textValue(row.title) ?? 'Notion page',
    body: (row) => textValue(row.content) ?? '',
    meta: (row) => [
      textValue(row.last_edited_by),
      textValue(row.notion_updated_at) ? formatRelativeTime(String(row.notion_updated_at)) : null,
    ].filter(Boolean) as string[],
  },
  fathom_transcript: {
    table: 'meeting_transcripts',
    select: 'id,workspace_id,title,transcript,summary,participants,meeting_date',
    label: 'Fathom transcript',
    title: (row) => textValue(row.title) ?? 'Fathom transcript',
    body: (row) => textValue(row.transcript) ?? textValue(row.summary) ?? '',
    meta: (row) => [
      Array.isArray(row.participants) ? row.participants.filter((item) => typeof item === 'string').slice(0, 3).join(', ') : null,
      textValue(row.meeting_date) ? formatRelativeTime(String(row.meeting_date)) : null,
    ].filter(Boolean) as string[],
  },
}

function textValue(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value.trim() : null
}

function sourceTypeValue(value: string | null): SourceType | null {
  if (
    value === 'slack_message'
    || value === 'telegram_message'
    || value === 'notion_page'
    || value === 'fathom_transcript'
  ) {
    return value
  }
  return null
}

function trimBody(value: string): string {
  if (value.length <= 4000) return value
  return `${value.slice(0, 4000).trimEnd()}\n...`
}

export function SourceReferenceClient() {
  const params = useSearchParams()
  const sourceType = sourceTypeValue(params.get('source_type'))
  const sourceId = params.get('source_id')
  const workspaceId = params.get('workspace_id')
  const sourceTimestamp = params.get('source_timestamp')
  const [row, setRow] = useState<SourceReferenceRow | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const config = sourceType ? SOURCE_CONFIG[sourceType] : null

  useEffect(() => {
    let cancelled = false

    async function load() {
      if (!config || !sourceId || !workspaceId) {
        setError('Source reference is missing required identifiers.')
        setIsLoading(false)
        return
      }

      setIsLoading(true)
      setError(null)
      const supabase = createClient()
      const { data, error: queryError } = await supabase
        .from(config.table)
        .select(config.select)
        .eq('workspace_id', workspaceId)
        .eq('id', sourceId)
        .single()

      if (cancelled) return
      if (queryError) {
        setError('Could not load this source reference.')
        setRow(null)
      } else {
        setRow((data ?? null) as unknown as SourceReferenceRow | null)
      }
      setIsLoading(false)
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [config, sourceId, workspaceId])

  const meta = useMemo(() => {
    if (!config || !row) return []
    const fromRow = config.meta(row)
    if (fromRow.length > 0) return fromRow
    return sourceTimestamp ? [formatRelativeTime(sourceTimestamp)] : []
  }, [config, row, sourceTimestamp])

  return (
    <div className="mx-auto max-w-3xl space-y-6 animate-fade-in-up">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-muted-foreground">
            {config?.label ?? 'Source reference'}
          </p>
          <h1 className="mt-2 text-2xl font-semibold text-foreground">
            {row && config ? config.title(row) : 'Source reference'}
          </h1>
        </div>
        <Link href="/dashboard" className="text-sm text-muted-foreground transition-colors hover:text-foreground">
          Home
        </Link>
      </div>

      {isLoading ? (
        <div className="dashboard-panel space-y-4 p-5">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : error ? (
        <div className="dashboard-panel p-5 text-sm text-destructive">
          {error}
        </div>
      ) : row && config ? (
        <article className="dashboard-panel p-5">
          {meta.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-2">
              {meta.map((item) => (
                <span key={item} className="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
                  {item}
                </span>
              ))}
            </div>
          )}
          <pre className="whitespace-pre-wrap break-words text-sm leading-6 text-foreground">
            {trimBody(config.body(row))}
          </pre>
        </article>
      ) : (
        <div className="dashboard-panel p-5 text-sm text-muted-foreground">
          Source not found.
        </div>
      )}
    </div>
  )
}
