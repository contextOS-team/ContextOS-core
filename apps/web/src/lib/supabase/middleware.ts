import { createServerClient, type CookieOptions } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet: { name: string; value: string; options: CookieOptions }[]) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          supabaseResponse = NextResponse.next({
            request,
          })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  // Do not run code between createServerClient and
  // supabase.auth.getUser(). A simple mistake could make it very hard to debug
  // issues with users being randomly logged out.

  const {
    data: { user },
  } = await supabase.auth.getUser()

  const pathname = request.nextUrl.pathname

  // Public paths that don't require authentication
  const isPublicPath =
    pathname === '/' ||
    pathname === '/login' ||
    pathname === '/signup' ||
    pathname.startsWith('/auth/callback') ||
    pathname === '/opengraph-image' ||
    pathname === '/twitter-image' ||
    pathname === '/icon' ||
    pathname === '/apple-icon' ||
    pathname === '/robots.txt' ||
    pathname === '/sitemap.xml'

  if (!user && !isPublicPath) {
    // Redirect unauthenticated users to login
    const url = request.nextUrl.clone()
    url.pathname = '/login'
    return NextResponse.redirect(url)
  }

  if (user) {
    // Onboarding state is only needed on routes that branch on it. Skipping
    // the Supabase query on every other request removes a per-navigation
    // round-trip on a Frankfurt → Hetzner-Nuremberg path that costs ~10-100ms.
    const needsOnboardingCheck =
      pathname === '/login' ||
      pathname === '/signup' ||
      pathname === '/onboarding' ||
      pathname.startsWith('/dashboard')

    if (needsOnboardingCheck) {
      const { data: onboarding } = await supabase
        .from('user_onboarding_state')
        .select('completed_at')
        .eq('user_id', user.id)
        .single()

      const onboardingComplete = !!onboarding?.completed_at

      if (pathname === '/login' || pathname === '/signup') {
        const url = request.nextUrl.clone()
        url.pathname = onboardingComplete ? '/dashboard' : '/onboarding'
        return NextResponse.redirect(url)
      }

      if (!onboardingComplete && pathname.startsWith('/dashboard')) {
        const url = request.nextUrl.clone()
        url.pathname = '/onboarding'
        return NextResponse.redirect(url)
      }

      if (onboardingComplete && pathname === '/onboarding') {
        const url = request.nextUrl.clone()
        url.pathname = '/dashboard'
        return NextResponse.redirect(url)
      }
    }
  }

  return supabaseResponse
}
