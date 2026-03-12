'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  connectSlack,
  connectGithub,
  connectGitlab,
  connectNotion,
  connectFathom,
  connectTelegram,
  connectJira,
  type IntegrationStatusResponse,
} from '@/lib/api'
import {
  SlackLogo,
  GitHubLogo,
  GitLabLogo,
  NotionLogo,
  FathomLogo,
  TelegramLogo,
  JiraLogo,
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

  const slackConnected = integrations?.slack.status === 'connected'
  const githubConnected = integrations?.github.status === 'connected'
  const gitlabConnected = integrations?.gitlab?.status === 'connected'
  const notionConnected = integrations?.notion.status === 'connected'
  const fathomConnected = integrations?.fathom.status === 'connected'
  const telegramConnected = integrations?.telegram.status === 'connected'
  const linearConnected = integrations?.linear?.status === 'connected'
  const jiraConnected = integrations?.jira?.status === 'connected'

  async function handleJira() {
    setConnecting('jira')
    try {
      const { authorization_url } = await connectJira()
      window.location.href = authorization_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect Jira')
      setConnecting(null)
    }
  }

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
  }

  function handleTelegramClick() {
    if (telegramConnected) return
    setShowTelegramForm(true)
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
      toast.success('Telegram connected')
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
          name="Jira"
          logo={<JiraLogo width={32} height={32} />}
          connected={jiraConnected}
          onClick={handleJira}
          disabled={connecting === 'jira' || (linearConnected && !jiraConnected)}
          disabledHint={linearConnected && !jiraConnected ? 'Linear is active' : undefined}
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
