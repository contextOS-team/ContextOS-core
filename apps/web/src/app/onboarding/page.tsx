'use client'

import { Suspense, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { toast } from 'sonner'
import { OnboardingWizard } from '@/components/onboarding/onboarding-wizard'

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
    <>
      <Suspense fallback={null}>
        <OnboardingToastHandler />
      </Suspense>
      <OnboardingWizard />
    </>
  )
}
