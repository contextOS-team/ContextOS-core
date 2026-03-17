'use client'

import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  connectSlack,
  connectGithub,
  connectGitlab,
  connectNotion,
  connectFathom,
  connectTelegram,
  getTelegramSyncStatus,
  type IntegrationStatusResponse,
} from '@/lib/api'
import {
  SlackLogo,
  GitHubLogo,
  GitLabLogo,
  NotionLogo,
  FathomLogo,
  TelegramLogo,
} from '@/components/icons/brand-logos'
import { SourceCard } from './source-card'
import { toast } from 'sonner'

interface StepSourcesProps {
  onNext: () => void
  onSkip: () => void
  integrations: IntegrationStatusResponse | null
  onSourceConnected: () => void
}

export function StepSources({ onNext, onSkip, integrations, onSourceConnected }: StepSourcesProps) {
  const [connecting, setConnecting] = useState<string | null>(null)
  const [showFathomForm, setShowFathomForm] = useState(false)
  const [fathomKey, setFathomKey] = useState('')
  const [fathomLoading, setFathomLoading] = useState(false)
  const [showTelegramForm, setShowTelegramForm] = useState(false)
  const [telegramToken, setTelegramToken] = useState('')
  const [telegramLoading, setTelegramLoading] = useState(false)
  const [telegramSyncStatus, setTelegramSyncStatus] = useState<string | null>(null)
  const [telegramSyncCount, setTelegramSyncCount] = useState(0)
  const syncPollRef = useRef<NodeJS.Timeout | null>(null)

  const slackConnected = integrations?.slack.status === 'connected'
  const githubConnected = integrations?.github.status === 'connected'
  const gitlabConnected = integrations?.gitlab?.status === 'connected'
  const notionConnected = integrations?.notion.status === 'connected'
  const fathomConnected = integrations?.fathom.status === 'connected'
  const telegramConnected = integrations?.telegram.status === 'connected'

  // Poll Telegram sync status when syncing
  useEffect(() => {
    if (telegramSyncStatus !== 'syncing') return

    syncPollRef.current = setInterval(async () => {
      try {
        const status = await getTelegramSyncStatus()
        setTelegramSyncCount(status.records_synced)
        if (status.sync_status === 'complete') {
          setTelegramSyncStatus('complete')
          setTelegramSyncCount(status.records_synced)
          toast.success(`Synced ${status.records_synced} Telegram messages`)
        } else if (status.sync_status === 'error') {
          setTelegramSyncStatus('error')
        }
      } catch {
        // Non-blocking
      }
    }, 3000)

    return () => {
      if (syncPollRef.current) clearInterval(syncPollRef.current)
    }
  }, [telegramSyncStatus])

  async function handleSlack() {
    setConnecting('slack')
    try {
      const { authorization_url } = await connectSlack()
      window.location.href = authorization_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect Slack')
      setConnecting(null)
    }
  }

  async function handleGithub() {
    setConnecting('github')
    try {
      const { installation_url } = await connectGithub()
      window.location.href = installation_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect GitHub')
      setConnecting(null)
    }
  }

  async function handleGitlab() {
    setConnecting('gitlab')
    try {
      const { authorization_url } = await connectGitlab()
      window.location.href = authorization_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect GitLab')
      setConnecting(null)
    }
  }

  async function handleNotion() {
    setConnecting('notion')
    try {
      const { authorization_url } = await connectNotion()
      window.location.href = authorization_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect Notion')
      setConnecting(null)
    }
  }

  function handleFathomClick() {
    if (fathomConnected) return
    setShowFathomForm(true)
    setShowTelegramForm(false)
    setTelegramToken('')
  }

  function handleTelegramClick() {
    if (telegramConnected) return
    setShowTelegramForm(true)
    setShowFathomForm(false)
    setFathomKey('')
  }

  async function handleTelegramSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!telegramToken.trim()) return

    setTelegramLoading(true)
    try {
      await connectTelegram(telegramToken.trim())
      setShowTelegramForm(false)
      setTelegramToken('')
      onSourceConnected()
      toast.success('Telegram connected — syncing message history...')
      setTelegramSyncStatus('syncing')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect Telegram')
    } finally {
      setTelegramLoading(false)
    }
  }

  async function handleFathomSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!fathomKey.trim()) return

    setFathomLoading(true)
    try {
      await connectFathom(fathomKey.trim())
      setShowFathomForm(false)
      setFathomKey('')
      onSourceConnected()
      toast.success('Fathom connected')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect Fathom')
    } finally {
      setFathomLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Connect more sources</h2>
        <p className="text-sm text-muted-foreground">
          Optional &mdash; connect any sources you want. You can always add more later.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <SourceCard
          name="Slack"
          logo={<SlackLogo width={32} height={32} />}
          connected={slackConnected}
          onClick={handleSlack}
          disabled={connecting === 'slack'}
        />
        <SourceCard
          name="GitHub"
          logo={<GitHubLogo width={32} height={32} />}
          connected={githubConnected}
          onClick={handleGithub}
          disabled={connecting === 'github'}
        />
        <SourceCard
          name="GitLab"
          logo={<GitLabLogo width={32} height={32} />}
          connected={gitlabConnected}
          onClick={handleGitlab}
          disabled={connecting === 'gitlab'}
        />
        <SourceCard
          name="Notion"
          logo={<NotionLogo width={32} height={32} />}
          connected={notionConnected}
          onClick={handleNotion}
          disabled={connecting === 'notion'}
        />
        <SourceCard
          name="Fathom"
          logo={<FathomLogo width={32} height={32} />}
          connected={fathomConnected}
          onClick={handleFathomClick}
        />
        <SourceCard
          name="Telegram"
          logo={<TelegramLogo width={32} height={32} />}
          connected={telegramConnected}
          onClick={handleTelegramClick}
        />
      </div>

      {showFathomForm && !fathomConnected && (
        <form onSubmit={handleFathomSubmit} className="space-y-3 rounded-lg border border-border p-4">
          <div className="space-y-1.5">
            <label htmlFor="fathom-api-key-onboarding" className="text-xs font-medium">
              Fathom API Key
            </label>
            <Input
              id="fathom-api-key-onboarding"
              type="password"
              placeholder="Enter your Fathom API key"
              value={fathomKey}
              onChange={(e) => setFathomKey(e.target.value)}
              className="h-8 text-xs"
              autoComplete="off"
              autoFocus
            />
            <p className="text-xs text-muted-foreground">
              Find your API key in{' '}
              <a
                href="https://fathom.video/api_clients/new"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-primary underline underline-offset-2 hover:text-primary/80"
              >
                Fathom &rarr; API Clients
              </a>
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              type="submit"
              disabled={fathomLoading || !fathomKey.trim()}
            >
              {fathomLoading ? 'Connecting...' : 'Connect'}
            </Button>
            <Button
              size="sm"
              type="button"
              variant="ghost"
              onClick={() => {
                setShowFathomForm(false)
                setFathomKey('')
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      {showTelegramForm && !telegramConnected && (
        <form onSubmit={handleTelegramSubmit} className="space-y-3 rounded-lg border border-border p-4">
          <div className="space-y-1.5">
            <label htmlFor="telegram-bot-token-onboarding" className="text-xs font-medium">
              Telegram Bot Token
            </label>
            <Input
              id="telegram-bot-token-onboarding"
              type="password"
              placeholder="Enter your bot token from @BotFather"
              value={telegramToken}
              onChange={(e) => setTelegramToken(e.target.value)}
              className="h-8 text-xs"
              autoComplete="off"
              autoFocus
            />
            <p className="text-xs text-muted-foreground">
              Create a bot via @BotFather on Telegram. In Bot Settings, turn Group Privacy OFF so the bot can read all messages.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              type="submit"
              disabled={telegramLoading || !telegramToken.trim()}
            >
              {telegramLoading ? 'Connecting...' : 'Connect'}
            </Button>
            <Button
              size="sm"
              type="button"
              variant="ghost"
              onClick={() => {
                setShowTelegramForm(false)
                setTelegramToken('')
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      {/* Telegram sync status indicator */}
      {telegramConnected && telegramSyncStatus === 'syncing' && (
        <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-4 py-3">
          <div className="h-2 w-2 animate-pulse rounded-full bg-primary" />
          <p className="text-xs text-muted-foreground">
            Syncing Telegram history{telegramSyncCount > 0 ? ` — ${telegramSyncCount} messages` : '...'}
          </p>
        </div>
      )}
      {telegramConnected && telegramSyncStatus === 'complete' && telegramSyncCount > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-4 py-3">
          <svg className="h-3.5 w-3.5 text-green-500" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
          </svg>
          <p className="text-xs text-muted-foreground">
            Synced {telegramSyncCount} Telegram messages
          </p>
        </div>
      )}

      <div className="flex gap-3">
        <Button variant="ghost" onClick={onSkip} className="flex-1">
          Skip
        </Button>
        <Button onClick={onNext} className="flex-1">
          Continue
        </Button>
      </div>
    </div>
  )
}
