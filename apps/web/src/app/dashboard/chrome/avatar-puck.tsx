'use client'

import { LogOut, Settings, UserCircle } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

interface AvatarPuckProps {
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

export function AvatarPuck({ userEmail, userFullName }: AvatarPuckProps) {
  const router = useRouter()
  const initials = getInitials(userFullName, userEmail)

  async function handleSignOut() {
    const supabase = createClient()
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-[#ece9e3] outline-none transition-transform duration-150 ease-out hover:scale-[1.04] active:scale-[0.96]"
          title={userFullName ?? userEmail}
          data-testid="avatar-puck"
        >
          {initials}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <div className="px-2 py-1.5">
          <p className="truncate text-sm font-medium text-foreground">
            {userFullName ?? userEmail}
          </p>
          {userFullName && (
            <p className="truncate text-xs text-muted-foreground">{userEmail}</p>
          )}
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => router.push('/dashboard/settings')}>
          <UserCircle className="mr-2 h-4 w-4" />
          Profile
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => router.push('/dashboard/settings?tab=general')}>
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
  )
}
