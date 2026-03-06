'use client'

import { useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'

export default function IntegrationsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()

  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString())
    params.set('tab', 'integrations')
    router.replace(`/dashboard/settings?${params.toString()}`)
  }, [router, searchParams])

  return null
}
