'use client'

import { Check } from 'lucide-react'

interface SourceCardProps {
  name: string
  logo: React.ReactNode
  connected: boolean
  onClick: () => void
  disabled?: boolean
  /** Shown below the name when disabled */
  disabledHint?: string
}

export function SourceCard({ name, logo, connected, onClick, disabled, disabledHint }: SourceCardProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || connected}
      className={`
        relative flex flex-col items-center justify-center gap-1.5 rounded-lg border p-4
        transition-colors duration-150
        ${connected
          ? 'border-primary/30 bg-primary/5 cursor-default'
          : 'border-border hover:border-primary/50 hover:bg-card disabled:opacity-50 disabled:cursor-not-allowed'
        }
      `}
    >
      <div className="h-8 w-8 text-foreground">{logo}</div>
      <span className="text-sm font-medium">{name}</span>
      {disabled && disabledHint && !connected && (
        <span className="text-[10px] text-muted-foreground/70 leading-tight">{disabledHint}</span>
      )}
      {connected && (
        <div className="animate-scale-in absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-primary">
          <Check className="h-3 w-3 text-primary-foreground" strokeWidth={3} />
        </div>
      )}
    </button>
  )
}
