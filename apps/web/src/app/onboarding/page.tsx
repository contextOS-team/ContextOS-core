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

    const oauthError = searchParams.get('oauth_error')
    const reason = searchParams.get('reason')
    if (oauthError) {
      const provider = oauthError === 'jira' ? 'Jira' : 'Linear'
      const messages: Record<string, string> = {
        provider_conflict: `Another ticket provider is already connected`,
        exchange_failed: `Failed to connect ${provider}. Please try again.`,
      }
      toast.error(messages[reason ?? ''] ?? `Failed to connect ${provider}`)
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
