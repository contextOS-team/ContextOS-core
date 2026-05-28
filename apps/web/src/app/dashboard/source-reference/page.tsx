import { Suspense } from 'react'
import { Skeleton } from '@/components/ui/skeleton'
import { SourceReferenceClient } from './source-reference-client'

function SourceReferenceFallback() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Skeleton className="h-4 w-32" />
        <Skeleton className="mt-3 h-8 w-64" />
      </div>
      <div className="dashboard-panel space-y-4 p-5">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-28 w-full" />
      </div>
    </div>
  )
}

export default function SourceReferencePage() {
  return (
    <Suspense fallback={<SourceReferenceFallback />}>
      <SourceReferenceClient />
    </Suspense>
  )
}
