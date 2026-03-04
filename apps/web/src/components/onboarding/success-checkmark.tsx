'use client'

import { Check } from 'lucide-react'

export function SuccessCheckmark() {
  return (
    <div className="flex items-center justify-center py-8">
      <div className="animate-scale-in flex h-12 w-12 items-center justify-center rounded-full bg-primary">
        <Check className="h-6 w-6 text-primary-foreground" strokeWidth={3} />
      </div>
    </div>
  )
}
