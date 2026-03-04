'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { LogOut, Settings } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

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
  { href: '/dashboard/activity', label: 'Activity' },
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
      {/* Left: wordmark with teal gradient */}
      <Link
        href="/dashboard"
        className="text-[15px] font-semibold tracking-[-0.02em]"
      >
        <span className="bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
          ContextOS
        </span>
      </Link>

      {/* Nav links */}
      <div className="ml-8 flex items-center gap-1">
        {navItems.map(({ href, label }) => {
          const active = isActive(href)
          return (
            <Link
              key={href}
              href={href}
              className={`relative px-3 py-1.5 text-[13px] font-medium transition-colors duration-150 ${
                active
                  ? 'text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {label}
              {active && (
                <span className="absolute bottom-0 left-3 right-3 h-[2px] rounded-full bg-primary translate-y-[9px]" />
              )}
            </Link>
          )
        })}
      </div>

      {/* Right: avatar dropdown */}
      <div className="ml-auto flex items-center">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              className="h-7 w-7 shrink-0 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-semibold outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              title={userFullName ?? userEmail}
            >
              {initials}
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <div className="px-2 py-1.5">
              <p className="text-sm font-medium text-foreground truncate">
                {userFullName ?? userEmail}
              </p>
              {userFullName && (
                <p className="text-xs text-muted-foreground truncate">{userEmail}</p>
              )}
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push('/dashboard/settings')}>
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleSignOut}>
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </nav>
  )
}
