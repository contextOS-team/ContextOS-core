'use client'

import { useEffect, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { Skeleton } from '@/components/ui/skeleton'
import { getWorkspace, type WorkspaceResponse } from '@/lib/api'
import { GeneralTab } from './tabs/general-tab'
import { ApiKeysTab } from './tabs/api-keys-tab'
import { TeamTab } from './tabs/team-tab'
import { IntegrationsTab } from './tabs/integrations-tab'

type Tab = 'general' | 'api-keys' | 'team' | 'integrations'

const TABS: { id: Tab; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'api-keys', label: 'API Keys' },
  { id: 'team', label: 'Team' },
  { id: 'integrations', label: 'Integrations' },
]

const SettingsSkeleton = () => (
  <div className="space-y-6 animate-fade-in-up">
    <Skeleton className="h-8 w-32" />
    <div className="flex gap-1">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-8 w-24 rounded-lg" />)}</div>
    <div className="rounded-xl border bg-card p-6 space-y-4">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-9 w-full max-w-sm" />
      <Skeleton className="h-9 w-20" />
    </div>
  </div>
)

export default function SettingsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null)

  const tabParam = searchParams.get('tab') as Tab | null
  const activeTab: Tab = tabParam && TABS.some((t) => t.id === tabParam) ? tabParam : 'general'

  const setActiveTab = (tab: Tab) => {
    const params = new URLSearchParams(searchParams.toString())
    if (tab === 'general') {
      params.delete('tab')
    } else {
      params.set('tab', tab)
    }
    const qs = params.toString()
    router.replace(`/dashboard/settings${qs ? `?${qs}` : ''}`, { scroll: false })
  }

  useEffect(() => {
    getWorkspace()
      .then((ws) => {
        setWorkspace(ws)
        setError(null)
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : 'Failed to load settings')
      })
      .finally(() => setIsLoading(false))
  }, [])

  if (isLoading) return <SettingsSkeleton />

  if (error) {
    return (
      <div className="space-y-6 animate-fade-in-up">
        <h2 className="text-2xl font-semibold tracking-[-0.03em] text-foreground">Settings</h2>
        <div className="rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in-up">
      <h2 className="text-2xl font-semibold tracking-[-0.03em] text-foreground">Settings</h2>

      <nav className="flex gap-1 border-b border-border pb-0 mb-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`relative px-3 py-2 text-sm font-medium transition-colors duration-150 ${
              activeTab === tab.id
                ? 'text-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {tab.label}
            {activeTab === tab.id && (
              <span className="absolute bottom-0 left-2 right-2 h-[2px] rounded-full bg-primary" />
            )}
          </button>
        ))}
      </nav>

      <div className="animate-fade-in-up" key={activeTab}>
        {activeTab === 'general' && workspace && (
          <GeneralTab workspace={workspace} onUpdate={setWorkspace} />
        )}
        {activeTab === 'api-keys' && <ApiKeysTab />}
        {activeTab === 'team' && <TeamTab />}
        {activeTab === 'integrations' && <IntegrationsTab />}
      </div>
    </div>
  )
}
