'use client'

import { createClient } from '@/lib/supabase/client'
import { GoogleIcon } from './provider-icons'
import { GitHubIcon } from './provider-icons'

interface SocialButtonsProps {
  redirectTo?: string
}

export function SocialButtons({ redirectTo }: SocialButtonsProps) {
  async function handleOAuth(provider: 'google' | 'github') {
    const supabase = createClient()
    await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: redirectTo || window.location.origin + '/auth/callback',
      },
    })
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => handleOAuth('google')}
        className="flex w-full items-center justify-center gap-3 rounded-lg border border-border bg-transparent px-4 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
      >
        <GoogleIcon />
        Continue with Google
      </button>
      <button
        type="button"
        onClick={() => handleOAuth('github')}
        className="flex w-full items-center justify-center gap-3 rounded-lg border border-border bg-transparent px-4 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted/50"
      >
        <GitHubIcon />
        Continue with GitHub
      </button>
    </div>
  )
}
