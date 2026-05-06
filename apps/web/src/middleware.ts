import { type NextRequest } from 'next/server'
import { updateSession } from '@/lib/supabase/middleware'

export async function middleware(request: NextRequest) {
  return await updateSession(request)
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for static assets and API routes.
     * Auth/onboarding cookie work runs on every match and hits Supabase twice,
     * so the matcher is kept as restrictive as possible.
     */
    '/((?!_next/static|_next/image|_next/data|favicon.ico|robots.txt|sitemap.xml|api/|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js|woff2?|ttf|otf|map)$).*)',
  ],
}
