'use client'

interface StepIndicatorProps {
  currentStep: number
  totalSteps?: number
}

export function StepIndicator({ currentStep, totalSteps = 4 }: StepIndicatorProps) {
  return (
    <div className="flex items-center justify-center gap-2">
      {Array.from({ length: totalSteps }, (_, i) => {
        const step = i + 1
        const isCompleted = step < currentStep
        const isActive = step === currentStep

        return (
          <div
            key={step}
            className={`h-2 w-2 rounded-full transition-colors duration-200 ${
              isCompleted
                ? 'bg-primary'
                : isActive
                  ? 'ring-2 ring-primary bg-transparent'
                  : 'bg-muted-foreground/30'
            }`}
          />
        )
      })}
    </div>
  )
}
