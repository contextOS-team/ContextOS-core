'use client'

import { Suspense, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { toast } from 'sonner'

function OnboardingToastHandler() {
  const searchParams = useSearchParams()

  useEffect(() => {
    if (searchParams.get('from') === 'dashboard') {
      toast('Complete setup first', {
        description: 'Finish onboarding to access your dashboard',
      })
    }
  }, [searchParams])

  return null
}

export default function OnboardingPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <Suspense fallback={null}>
        <OnboardingToastHandler />
      </Suspense>
      <div className="text-center">
        <h1 className="text-2xl font-bold">Welcome to ContextOS</h1>
        <p className="mt-2 text-muted-foreground">
          Let&apos;s get your workspace set up.
        </p>
        <p className="mt-8 text-sm text-muted-foreground">
          Onboarding wizard coming in Phase 17
        </p>
      </div>
    </div>
  )
}
