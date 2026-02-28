'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { LogOut } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'

interface TopNavProps {
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
  { href: '/dashboard', label: 'Home' },
  { href: '/dashboard/context', label: 'Context' },
  { href: '/dashboard/integrations', label: 'Integrations' },
]

export function Sidebar({ userEmail, userFullName }: TopNavProps) {
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
    <nav className="sticky top-0 z-40 flex h-14 items-center border-b border-border bg-background/80 backdrop-blur-sm px-6">
      {/* Left: wordmark */}
      <Link
        href="/dashboard"
        className="text-[15px] font-semibold tracking-[-0.02em] text-foreground"
      >
        ContextOS
      </Link>

      {/* Nav links */}
      <div className="ml-8 flex items-center gap-1">
        {navItems.map(({ href, label }) => {
          const active = isActive(href)
          return (
            <Link
              key={href}
              href={href}
              className={`relative px-3 py-1.5 text-[13px] font-medium rounded-md transition-colors duration-150 ${
                active
                  ? 'text-foreground bg-muted'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              }`}
            >
              {label}
              {active && (
                <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-primary rounded-full translate-y-[9px]" />
              )}
            </Link>
          )
        })}
      </div>

      {/* Right: user + sign out */}
      <div className="ml-auto flex items-center gap-3">
        <div
          className="h-7 w-7 shrink-0 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-semibold"
          title={userFullName ?? userEmail}
        >
          {initials}
        </div>
        <button
          onClick={handleSignOut}
          title="Sign out"
          className="flex items-center justify-center rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors duration-150"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </nav>
  )
}
