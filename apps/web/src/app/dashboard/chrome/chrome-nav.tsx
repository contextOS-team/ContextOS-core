'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Activity, Home, Layers, Network } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'
import { AvatarPuck } from './avatar-puck'
import { SyncIndicator } from './sync-indicator'
import { useSyncState } from './use-sync-state'

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
  const syncState = useSyncState(workspaceId)

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
    <nav className="sticky top-0 z-40 flex h-14 items-center border-b border-border bg-background/80 px-6 backdrop-blur-sm">
      <Link
        href="/dashboard"
        className="text-[15px] font-semibold"
      >
        <span className="bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
          ContextOS
        </span>
      </Link>

      <div className="ml-6 h-4 w-px bg-border" />

      <div className="ml-4 flex items-center gap-0.5">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = isActive(href)
          return (
            <Link
              key={href}
              href={href}
              className={`relative flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors duration-150 ${
                active
                  ? 'bg-primary/10 text-foreground'
                  : 'text-muted-foreground/70 hover:bg-muted/50 hover:text-foreground'
              }`}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
              {active && (
                <span className="absolute bottom-0 left-2 right-2 h-[2px] translate-y-[9px] rounded-full bg-primary" />
              )}
            </Link>
          )
        })}
      </div>

      <div className="ml-auto flex items-center gap-4">
        <SyncIndicator state={syncState} />
        <AvatarPuck userEmail={userEmail} userFullName={userFullName} />
      </div>
    </nav>
  )
}
