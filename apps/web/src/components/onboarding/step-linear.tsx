'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { connectLinear } from '@/lib/api'
import { LinearLogo } from '@/components/icons/brand-logos'
import { SuccessCheckmark } from './success-checkmark'
import { Check } from 'lucide-react'
import { toast } from 'sonner'

interface StepLinearProps {
  onNext: () => void
  isConnected: boolean
  showSuccess: boolean
}

export function StepLinear({ onNext, isConnected, showSuccess }: StepLinearProps) {
  const [connecting, setConnecting] = useState(false)

  async function handleConnect() {
    setConnecting(true)
    try {
      const { authorization_url } = await connectLinear()
      window.location.href = authorization_url
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect Linear')
      setConnecting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Connect Linear</h2>
        <p className="text-sm text-muted-foreground">
          ContextOS generates context from your Linear tickets. This connection is required.
        </p>
      </div>

      {showSuccess ? (
        <SuccessCheckmark />
      ) : isConnected ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3">
            <Check className="h-4 w-4 text-primary" strokeWidth={3} />
            <span className="text-sm font-medium">Linear connected</span>
          </div>
          <Button onClick={onNext} className="w-full">
            Continue
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex justify-center py-4">
            <LinearLogo width={40} height={40} />
          </div>
          <Button
            onClick={handleConnect}
            disabled={connecting}
            className="w-full"
          >
            {connecting ? 'Redirecting...' : 'Connect Linear'}
          </Button>
        </div>
      )}
    </div>
  )
}
