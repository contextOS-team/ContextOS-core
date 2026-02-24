---
phase: 01-foundation
plan: 03
subsystem: ui
tags: [nextjs, supabase-ssr, shadcn-ui, tailwindcss, auth-ui, middleware]

requires:
  - phase: 01-01
    provides: Supabase project config, database schema with profiles/workspaces tables
provides:
  - Login page with email/password and magic link authentication
  - Signup page with email/password registration
  - Dashboard shell with user info and sign-out
  - Supabase SSR client setup (browser + server + middleware)
  - Auth callback route for magic link and OAuth flows
  - Next.js middleware for auth redirects
affects: [phase-2-integrations, phase-5-dashboard]

tech-stack:
  added: ["@supabase/ssr", "shadcn/ui", "class-variance-authority", "lucide-react", "radix-ui"]
  patterns: [supabase-ssr-cookie-auth, nextjs-route-groups, server-component-auth-check]

key-files:
  created:
    - apps/web/src/lib/supabase/client.ts
    - apps/web/src/lib/supabase/server.ts
    - apps/web/src/lib/supabase/middleware.ts
    - apps/web/src/app/(auth)/layout.tsx
    - apps/web/src/app/(auth)/login/page.tsx
    - apps/web/src/app/(auth)/signup/page.tsx
    - apps/web/src/app/(auth)/auth/callback/route.ts
    - apps/web/src/app/dashboard/layout.tsx
    - apps/web/src/app/dashboard/page.tsx
    - apps/web/src/app/dashboard/sign-out-button.tsx
    - apps/web/src/components/ui/button.tsx
    - apps/web/src/components/ui/input.tsx
    - apps/web/src/components/ui/card.tsx
    - apps/web/src/components/ui/label.tsx
  modified:
    - apps/web/src/middleware.ts
    - apps/web/src/app/layout.tsx
    - apps/web/src/app/page.tsx

key-decisions:
  - "Dashboard uses /dashboard path instead of (dashboard) route group for cleaner URL structure"
  - "SignOutButton extracted as client component to keep dashboard layout as server component"
  - "Magic link emailRedirectTo falls back to window.location.origin when NEXT_PUBLIC_APP_URL is unset"

patterns-established:
  - "Supabase SSR: browser client via createBrowserClient, server client via createServerClient with cookie adapter"
  - "Auth middleware: updateSession refreshes tokens on every request, redirects unauthed to /login"
  - "Route groups: (auth) for login/signup with centered layout, /dashboard for protected pages with header"
  - "Server-side auth check: dashboard layout fetches user via getUser() and redirects if null"

requirements-completed: [DASH-01]

duration: 4min
completed: 2026-02-24
---

# Plan 01-03: Frontend Auth UI Summary

**Supabase SSR auth pages with login (email+password & magic link), signup, dashboard shell, and Next.js middleware redirects using shadcn/ui**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-24
- **Completed:** 2026-02-24
- **Tasks:** 3 (2 auto + 1 human-verify checkpoint)
- **Files modified:** 17

## Accomplishments
- Login page with dual auth methods: email/password and magic link
- Signup page with full name, email, password registration and email confirmation handling
- Dashboard shell showing user info with sign-out functionality
- Supabase SSR client setup for browser, server, and middleware contexts
- Next.js middleware redirecting unauthed users to /login and authed users away from auth pages
- Auth callback route handling magic link and OAuth code exchange
- Human-verified: full signup → login → session persistence → sign-out flow works

## Task Commits

1. **Task 1: Supabase client setup, middleware, and auth callback** - `663a8ac` (feat)
2. **Task 2: Login, signup, and dashboard pages with shadcn/ui** - `663a8ac` (feat)
3. **Task 3: Verify auth flow end-to-end** - Human checkpoint, approved

## Files Created/Modified
- `apps/web/src/lib/supabase/client.ts` - Browser-side Supabase client using createBrowserClient
- `apps/web/src/lib/supabase/server.ts` - Server-side Supabase client with cookie adapter
- `apps/web/src/lib/supabase/middleware.ts` - Session refresh + auth redirect logic
- `apps/web/src/middleware.ts` - Next.js middleware entry point calling updateSession
- `apps/web/src/app/(auth)/layout.tsx` - Centered auth layout with ContextOS branding
- `apps/web/src/app/(auth)/login/page.tsx` - Login page with email+password and magic link
- `apps/web/src/app/(auth)/signup/page.tsx` - Signup page with registration form
- `apps/web/src/app/(auth)/auth/callback/route.ts` - Auth callback for code exchange
- `apps/web/src/app/dashboard/layout.tsx` - Dashboard shell with header and sign-out
- `apps/web/src/app/dashboard/page.tsx` - Dashboard home showing user account info
- `apps/web/src/app/dashboard/sign-out-button.tsx` - Client-side sign-out button
- `apps/web/src/app/page.tsx` - Root redirect to /dashboard
- `apps/web/src/components/ui/button.tsx` - shadcn/ui Button component
- `apps/web/src/components/ui/input.tsx` - shadcn/ui Input component
- `apps/web/src/components/ui/card.tsx` - shadcn/ui Card component
- `apps/web/src/components/ui/label.tsx` - shadcn/ui Label component

## Decisions Made
- Dashboard uses `/dashboard` path instead of `(dashboard)` route group — cleaner URLs
- SignOutButton is a separate client component so the dashboard layout stays a server component
- Magic link redirectTo falls back to `window.location.origin` when env var is unset

## Deviations from Plan
None - plan executed as written. Tasks 1 and 2 were committed together in a single commit.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Full auth flow working: signup, login, magic link, session persistence, sign-out
- Dashboard shell ready for Phase 5 expansion with real features
- Supabase SSR pattern established for all future server/client components
- Phase 2 (Linear integration) can begin — auth foundation is complete

---
*Phase: 01-foundation*
*Completed: 2026-02-24*
