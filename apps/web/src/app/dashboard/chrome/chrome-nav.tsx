'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Activity, Home, Layers, Network } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'
import { AvatarPuck } from './avatar-puck'
import { SyncIndicator } from './sync-indicator'
import { useSourceSyncState } from './use-source-sync-state'

interface ChromeNavProps {
  userEmail: string
  userFullName?: string | null
}

const navItems = [
  { href: '/dashboard', label: 'Home', icon: Home },
  { href: '/dashboard/context', label: 'Context', icon: Layers },
  { href: '/dashboard/graph', label: 'Graph', icon: Network },
  { href: '/dashboard/activity', label: 'Activity', icon: Activity },
]

export function ChromeNav({ userEmail, userFullName }: ChromeNavProps) {
  const pathname = usePathname()
  const [workspaceId, setWorkspaceId] = useState<string | null>(null)
  const { state: syncState, notifySyncRequested } = useSourceSyncState(workspaceId)

  useEffect(() => {
    let cancelled = false

    async function loadWorkspace() {
      const supabase = createClient()
      const {
        data: { user },
      } = await supabase.auth.getUser()

      if (!user || cancelled) return

      const { data } = await supabase
        .from('workspace_members')
        .select('workspace_id')
        .eq('user_id', user.id)
        .single()

      if (!cancelled) {
        setWorkspaceId(data?.workspace_id ?? null)
      }
    }

    void loadWorkspace()

    return () => {
      cancelled = true
    }
  }, [])

  function isActive(href: string): boolean {
    if (href === '/dashboard') {
      return pathname === '/dashboard' || pathname.startsWith('/dashboard/decisions')
    }
    return pathname.startsWith(href)
  }

  return (
    <nav className="dashboard-chrome">
      <Link href="/dashboard" className="dashboard-brand">
        ContextOS
      </Link>

      <div className="dashboard-nav-list">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = isActive(href)
          return (
            <Link
              key={href}
              href={href}
              className={`dashboard-nav-item ${active ? 'dashboard-nav-item--active' : ''}`}
              aria-label={label}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="dashboard-nav-label">{label}</span>
            </Link>
          )
        })}
      </div>

      <div className="ml-auto flex items-center gap-3">
        <SyncIndicator state={syncState} onSyncRequested={notifySyncRequested} />
        <AvatarPuck userEmail={userEmail} userFullName={userFullName} />
      </div>
    </nav>
  )
}
