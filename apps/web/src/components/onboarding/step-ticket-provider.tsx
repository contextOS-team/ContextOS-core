'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { connectLinear, connectJira } from '@/lib/api'
import { LinearLogo, JiraLogo } from '@/components/icons/brand-logos'
import { SuccessCheckmark } from './success-checkmark'
import { Check } from 'lucide-react'
import { toast } from 'sonner'

interface StepTicketProviderProps {
  onNext: () => void
  isLinearConnected: boolean
  isJiraConnected: boolean
  showSuccess: boolean
}

type Provider = 'linear' | 'jira'

export function StepTicketProvider({ onNext, isLinearConnected, isJiraConnected, showSuccess }: StepTicketProviderProps) {
  const [connecting, setConnecting] = useState<Provider | null>(null)

  const hasTicketProvider = isLinearConnected || isJiraConnected

  async function handleConnect(provider: Provider) {
    setConnecting(provider)
    try {
      const connectFn = provider === 'linear' ? connectLinear : connectJira
      const { authorization_url } = await connectFn()
      window.location.href = authorization_url
    } catch (err) {
      const name = provider === 'linear' ? 'Linear' : 'Jira'
      toast.error(err instanceof Error ? err.message : `Failed to connect ${name}`)
      setConnecting(null)
    }
  }

  if (showSuccess) {
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <h2 className="text-xl font-semibold">Connect tickets</h2>
          <p className="text-sm text-muted-foreground">
            Choose your ticket provider to get started.
          </p>
        </div>
        <SuccessCheckmark />
      </div>
    )
  }

  // Already connected state
  if (hasTicketProvider) {
    const providerName = isLinearConnected ? 'Linear' : 'Jira'
    return (
      <div className="space-y-6">
        <div className="space-y-2">
          <h2 className="text-xl font-semibold">Connect tickets</h2>
          <p className="text-sm text-muted-foreground">
            Choose your ticket provider to get started.
          </p>
        </div>
        <div className="space-y-4">
          <div className="dashboard-panel flex items-center gap-2 px-4 py-3">
            <Check className="h-4 w-4 text-primary" strokeWidth={3} />
            <span className="text-sm font-medium">{providerName} connected</span>
          </div>
          <Button onClick={onNext} className="w-full">
            Continue
          </Button>
        </div>
      </div>
    )
  }

  // Provider choice
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Connect tickets</h2>
        <p className="text-sm text-muted-foreground">
          ContextOS generates context from your tickets. Connect a provider to get started.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <button
          onClick={() => handleConnect('linear')}
          disabled={connecting !== null}
          className="dashboard-choice-card flex flex-col items-center gap-2.5 rounded-lg p-5"
        >
          <LinearLogo width={36} height={36} />
          <span className="text-sm font-medium">Linear</span>
        </button>
        <button
          onClick={() => handleConnect('jira')}
          disabled={connecting !== null}
          className="dashboard-choice-card flex flex-col items-center gap-2.5 rounded-lg p-5"
        >
          <JiraLogo width={36} height={36} />
          <span className="text-sm font-medium">Jira</span>
        </button>
      </div>

      {connecting && (
        <p className="text-xs text-center text-muted-foreground">
          Redirecting to {connecting === 'linear' ? 'Linear' : 'Jira'}...
        </p>
      )}

      <button
        onClick={onNext}
        disabled={connecting !== null}
        className="w-full text-sm text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
      >
        Skip for now
      </button>
    </div>
  )
}
