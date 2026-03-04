import { NextResponse } from 'next/server'
import { createClient } from '@/lib/supabase/server'

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/dashboard'

  if (code) {
    const supabase = await createClient()
    const { error } = await supabase.auth.exchangeCodeForSession(code)

    if (!error) {
      // Check onboarding status to determine redirect destination
      const { data: { user } } = await supabase.auth.getUser()
      let destination = next

      if (user) {
        const { data: onboardingState } = await supabase
          .from('user_onboarding_state')
          .select('completed_at')
          .eq('user_id', user.id)
          .single()

        // If onboarding row exists and not completed, redirect to onboarding
        if (onboardingState && !onboardingState.completed_at) {
          destination = '/onboarding'
        }
      }

      const forwardedHost = request.headers.get('x-forwarded-host')
      const isLocalEnv = process.env.NODE_ENV === 'development'

      if (isLocalEnv) {
        return NextResponse.redirect(`${origin}${destination}`)
      } else if (forwardedHost) {
        return NextResponse.redirect(`https://${forwardedHost}${destination}`)
      } else {
        return NextResponse.redirect(`${origin}${destination}`)
      }
    }
  }

  // Return the user to login with an error if code exchange failed
  return NextResponse.redirect(`${origin}/login?error=auth`)
}
