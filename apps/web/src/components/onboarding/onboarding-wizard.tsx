'use client'

import { useEffect, useState, useCallback } from 'react'
import { createClient } from '@/lib/supabase/client'
import { getIntegrationStatus, type IntegrationStatusResponse } from '@/lib/api'
import { Skeleton } from '@/components/ui/skeleton'
import { StepIndicator } from './step-indicator'
import { StepWorkspace } from './step-workspace'
import { StepLinear } from './step-linear'
import { StepSources } from './step-sources'

type WizardStep = 1 | 2 | 3 | 4
type WizardState = 'loading' | 'active' | 'completing'

export function OnboardingWizard() {
  const [step, setStep] = useState<WizardStep>(1)
  const [wizardState, setWizardState] = useState<WizardState>('loading')
  const [integrations, setIntegrations] = useState<IntegrationStatusResponse | null>(null)
  const [showSuccess, setShowSuccess] = useState(false)
  const [advancing, setAdvancing] = useState(false)
  const [workspaceName, setWorkspaceName] = useState('')

  // Load initial state from DB and check integration status
  useEffect(() => {
    async function loadState() {
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return

      // Load current step and workspace name in parallel with integration status
      const [onboardingResult, integrationsResult, membershipResult] = await Promise.allSettled([
        supabase
          .from('user_onboarding_state')
          .select('current_step')
          .eq('user_id', user.id)
          .single(),
        getIntegrationStatus(),
        supabase
          .from('workspace_members')
          .select('workspace_id, workspaces(name)')
          .eq('user_id', user.id)
          .single(),
      ])

      if (onboardingResult.status === 'fulfilled' && onboardingResult.value.data) {
        setStep(onboardingResult.value.data.current_step as WizardStep)
      }

      if (integrationsResult.status === 'fulfilled') {
        setIntegrations(integrationsResult.value)
      }

      if (membershipResult.status === 'fulfilled' && membershipResult.value.data) {
        const ws = membershipResult.value.data.workspaces as unknown as { name: string } | null
        if (ws?.name) {
          setWorkspaceName(ws.name)
        }
      }

      setWizardState('active')
    }
    loadState()
  }, [])

  // OAuth return detection: if on step 2 and Linear is connected, show success then advance
  useEffect(() => {
    if (wizardState !== 'active') return
    if (step === 2 && integrations?.linear.status === 'connected' && !showSuccess && !advancing) {
      setShowSuccess(true)
      const timer = setTimeout(() => {
        setShowSuccess(false)
        advanceStep(3)
      }, 800)
      return () => clearTimeout(timer)
    }
  }, [step, integrations, wizardState, showSuccess, advancing])

  // OAuth return detection for step 3: check if any source newly connected
  // (User returns to step 3 after OAuth, sources show connected state via integrations)

  const advanceStep = useCallback(async (nextStep: WizardStep) => {
    if (advancing) return
    setAdvancing(true)

    try {
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return

      await supabase
        .from('user_onboarding_state')
        .update({ current_step: nextStep })
        .eq('user_id', user.id)

      setStep(nextStep)
    } finally {
      setAdvancing(false)
    }
  }, [advancing])

  const refreshIntegrations = useCallback(async () => {
    try {
      const status = await getIntegrationStatus()
      setIntegrations(status)
    } catch {
      // Non-blocking
    }
  }, [])

  function goBack() {
    if (step > 1) {
      setStep((step - 1) as WizardStep)
    }
  }

  // Loading skeleton
  if (wizardState === 'loading') {
    return (
      <div className="dashboard-grain relative flex min-h-screen items-center justify-center">
        <div className="w-full max-w-[480px] px-4">
          <div className="mb-6 text-center">
            <Skeleton className="mx-auto h-5 w-24" />
          </div>
          <div className="rounded-xl border border-border bg-card p-8">
            <div className="mb-6 flex justify-center gap-2">
              <Skeleton className="h-2 w-2 rounded-full" />
              <Skeleton className="h-2 w-2 rounded-full" />
              <Skeleton className="h-2 w-2 rounded-full" />
              <Skeleton className="h-2 w-2 rounded-full" />
            </div>
            <Skeleton className="mb-2 h-7 w-48" />
            <Skeleton className="mb-6 h-4 w-64" />
            <Skeleton className="mb-4 h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="dashboard-grain relative flex min-h-screen items-center justify-center">
      <div className="w-full max-w-[480px] px-4">
        {/* ContextOS wordmark */}
        <div className="mb-6 text-center">
          <span className="text-base font-semibold tracking-tight text-foreground">
            ContextOS
          </span>
        </div>

        {/* Card */}
        <div className="rounded-xl border border-border bg-card p-8">
          {/* Step indicator */}
          <div className="mb-6">
            <StepIndicator currentStep={step} />
          </div>

          {/* Step content with crossfade */}
          <div key={step} className="animate-step-enter">
            {step === 1 && (
              <StepWorkspace
                onNext={(name) => {
                  setWorkspaceName(name)
                  advanceStep(2)
                }}
                defaultName={workspaceName}
              />
            )}

            {step === 2 && (
              <StepLinear
                onNext={() => advanceStep(3)}
                isConnected={integrations?.linear.status === 'connected'}
                showSuccess={showSuccess}
              />
            )}

            {step === 3 && (
              <StepSources
                onNext={() => advanceStep(4)}
                onSkip={() => advanceStep(4)}
                integrations={integrations}
                onSourceConnected={refreshIntegrations}
              />
            )}

            {step === 4 && (
              <div className="space-y-4 py-8 text-center">
                <p className="text-sm text-muted-foreground">
                  Generating your first context page...
                </p>
                <div className="mx-auto h-2 w-32 overflow-hidden rounded-full bg-muted">
                  <div className="skeleton-shimmer h-full w-full" />
                </div>
              </div>
            )}
          </div>

          {/* Back button for steps 2-4 */}
          {step > 1 && !showSuccess && (
            <button
              onClick={goBack}
              className="mt-4 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              Back
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
