'use client'

import { useState } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  LayoutDashboard,
  Plug,
  PanelLeftClose,
  PanelLeft,
  LogOut,
} from 'lucide-react'
import { createClient } from '@/lib/supabase/client'

interface SidebarProps {
  userEmail: string
  userFullName?: string | null
}

function getInitials(fullName: string | null | undefined, email: string): string {
  if (fullName && fullName.trim().length > 0) {
    const words = fullName.trim().split(/\s+/)
    if (words.length >= 2) {
      return (words[0][0] + words[words.length - 1][0]).toUpperCase()
    }
    return words[0][0].toUpperCase()
  }
  if (email.length > 0) {
    return email[0].toUpperCase()
  }
  return '?'
}

const navItems = [
  { href: '/dashboard', label: 'Home', icon: LayoutDashboard },
  { href: '/dashboard/integrations', label: 'Integrations', icon: Plug },
]

export function Sidebar({ userEmail, userFullName }: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const pathname = usePathname()
  const router = useRouter()

  function isActive(href: string): boolean {
    if (href === '/dashboard') {
      return pathname === '/dashboard'
    }
    return pathname.startsWith(href)
  }

  async function handleSignOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  const initials = getInitials(userFullName, userEmail)

  return (
    <aside
      className="h-screen sticky top-0 bg-sidebar border-r border-sidebar-border flex flex-col transition-[width] duration-200 ease-in-out"
      style={{ width: isCollapsed ? 60 : 240 }}
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-4 border-b border-sidebar-border shrink-0">
        <Link
          href="/dashboard"
          className="text-lg font-semibold text-sidebar-foreground truncate"
        >
          {isCollapsed ? 'C' : 'ContextOS'}
        </Link>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = isActive(href)
          return (
            <Link
              key={href}
              href={href}
              title={isCollapsed ? label : undefined}
              className={`flex items-center gap-3 px-4 py-2 text-sm transition-colors ${
                isCollapsed ? 'justify-center' : ''
              } ${
                active
                  ? 'bg-sidebar-accent text-sidebar-foreground font-medium border-l-[3px] border-primary'
                  : 'text-muted-foreground hover:text-sidebar-foreground hover:bg-sidebar-accent/50 border-l-[3px] border-transparent'
              }`}
            >
              <Icon className="h-5 w-5 shrink-0" />
              {!isCollapsed && <span className="truncate">{label}</span>}
            </Link>
          )
        })}
      </nav>

      {/* User section */}
      <div className="border-t border-sidebar-border p-3 shrink-0">
        <div className={`flex items-center gap-3 ${isCollapsed ? 'justify-center' : ''}`}>
          <div className="h-8 w-8 shrink-0 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-medium">
            {initials}
          </div>
          {!isCollapsed && (
            <div className="flex-1 min-w-0">
              {userFullName && (
                <p className="text-sm font-medium text-sidebar-foreground truncate">
                  {userFullName}
                </p>
              )}
              <p className="text-xs text-muted-foreground truncate">{userEmail}</p>
            </div>
          )}
        </div>
        <button
          onClick={handleSignOut}
          title={isCollapsed ? 'Sign out' : undefined}
          className={`flex items-center gap-3 w-full mt-2 px-2 py-1.5 text-sm text-muted-foreground hover:text-sidebar-foreground rounded-md hover:bg-sidebar-accent/50 transition-colors ${
            isCollapsed ? 'justify-center' : ''
          }`}
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!isCollapsed && <span>Sign out</span>}
        </button>
      </div>

      {/* Collapse toggle */}
      <div className="border-t border-sidebar-border p-2 shrink-0">
        <button
          onClick={() => setIsCollapsed(!isCollapsed)}
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={`flex items-center w-full p-1.5 text-muted-foreground hover:text-sidebar-foreground rounded-md hover:bg-sidebar-accent/50 transition-colors ${
            isCollapsed ? 'justify-center' : 'justify-end'
          }`}
        >
          {isCollapsed ? (
            <PanelLeft className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </button>
      </div>
    </aside>
  )
}
