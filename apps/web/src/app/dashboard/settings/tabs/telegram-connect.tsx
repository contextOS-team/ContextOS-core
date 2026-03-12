'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { connectTelegram } from '@/lib/api'

export function TelegramConnect({ onConnected }: { onConnected?: () => void }) {
  const [token, setToken] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!token.trim()) {
      setError('Bot token is required')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      await connectTelegram(token.trim())
      setToken('')
      onConnected?.()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to connect. Check your bot token.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="telegram-bot-token" className="text-xs">
          Bot Token
        </Label>
        <Input
          id="telegram-bot-token"
          type="password"
          placeholder="Bot token from @BotFather"
          value={token}
          onChange={(e) => {
            setToken(e.target.value)
            setError(null)
          }}
          className="h-8 text-xs"
          autoComplete="off"
        />
        <p className="text-xs text-muted-foreground">
          Create a bot via @BotFather on Telegram. In Bot Settings, turn Group Privacy OFF so the bot can read all messages.
        </p>
      </div>

      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      <Button size="sm" type="submit" disabled={isLoading || !token.trim()}>
        {isLoading ? 'Connecting...' : 'Connect'}
      </Button>
    </form>
  )
}
