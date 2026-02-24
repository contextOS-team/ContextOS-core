'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { connectFathom } from '@/lib/api'

interface FathomConnectProps {
  /** Called after successful connection so parent can refresh status. */
  onConnected?: () => void
}

export function FathomConnect({ onConnected }: FathomConnectProps) {
  const [apiKey, setApiKey] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!apiKey.trim()) {
      setError('API key is required')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      await connectFathom(apiKey.trim())
      onConnected?.()
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to connect. Check your API key.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="space-y-1.5">
        <Label htmlFor="fathom-api-key" className="text-xs">
          API Key
        </Label>
        <Input
          id="fathom-api-key"
          type="password"
          placeholder="Enter your Fathom API key"
          value={apiKey}
          onChange={(e) => {
            setApiKey(e.target.value)
            setError(null)
          }}
          className="h-8 text-xs"
          autoComplete="off"
        />
        <p className="text-xs text-muted-foreground">
          Find your API key in{' '}
          <span className="font-medium">Fathom &rarr; Settings &rarr; API</span>
        </p>
      </div>

      {error && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      <Button size="sm" type="submit" disabled={isLoading || !apiKey.trim()}>
        {isLoading ? 'Connecting...' : 'Connect'}
      </Button>
    </form>
  )
}
