---
phase: 21-auth-redesign-and-social-oauth
plan: 01
subsystem: auth, ui
tags: [oauth, supabase, google, github, social-login, tailwindcss]

requires:
  - phase: 16-auth-redesign-schema
    provides: Auth layout with brand/form panels, Supabase client, design tokens

provides:
  - SocialButtons shared component with Google/GitHub OAuth via Supabase
  - GoogleIcon and GitHubIcon inline SVG components
  - Teal focus ring CSS for auth inputs
  - Cleaned login page (no magic link)
  - Unified auth page layout (social -> divider -> form -> CTA)

affects: [21-02, auth-pages, onboarding]

tech-stack:
  added: []
  patterns:
    - "Social OAuth via supabase.auth.signInWithOAuth with provider param"
    - "Inline SVG icons as React components (no icon library dependency)"

key-files:
  created:
    - apps/web/src/components/auth/provider-icons.tsx
    - apps/web/src/components/auth/social-buttons.tsx
  modified:
    - apps/web/src/app/(auth)/login/page.tsx
    - apps/web/src/app/(auth)/signup/page.tsx
    - apps/web/src/app/(auth)/layout.tsx
    - apps/web/src/app/globals.css

key-decisions:
  - "Native button elements for social OAuth (not Button component) for full style control"
  - "or-divider uses bg-elevated (L3) to match form panel background"
  - "Footer links to /terms and /privacy (not # placeholder)"

patterns-established:
  - "Auth pages follow social -> divider -> form -> CTA layout order"
  - "Focus ring uses oklch primary token with 0.4 alpha ring + 0.15 glow"

requirements-completed: [OAUTH-01, AUTH-POLISH-01]

duration: 3min
completed: 2026-03-08
---

# Phase 21 Plan 01: Social OAuth Buttons & Auth Page Polish Summary

**Google and GitHub social OAuth buttons on login/signup pages with magic link removal, teal focus rings, and corrected footer links**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-08T10:35:45Z
- **Completed:** 2026-03-08T10:38:45Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Social OAuth buttons (Google + GitHub) on both login and signup pages above email/password form
- Magic link authentication completely removed from login page
- Teal focus ring CSS with oklch glow on all inputs/textareas
- Footer links corrected from /login to /terms and /privacy
- Form panel surface corrected from bg-overlay (L4) to bg-elevated (L3)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create shared social buttons and provider icons components** - `70df1c9` (feat)
2. **Task 2: Rewrite login and signup pages with social OAuth, remove magic link, add focus rings** - `3d2d5c7` (feat)

## Files Created/Modified
- `apps/web/src/components/auth/provider-icons.tsx` - GoogleIcon (brand colors) and GitHubIcon (currentColor) SVG components
- `apps/web/src/components/auth/social-buttons.tsx` - SocialButtons component calling signInWithOAuth
- `apps/web/src/app/(auth)/login/page.tsx` - Rewritten: social buttons at top, no magic link, forgot -> /reset-password
- `apps/web/src/app/(auth)/signup/page.tsx` - Added social buttons above form with or-divider
- `apps/web/src/app/(auth)/layout.tsx` - bg-elevated form panel, footer links to /terms and /privacy
- `apps/web/src/app/globals.css` - Teal focus ring CSS with oklch primary token

## Decisions Made
- Used native button elements for social OAuth buttons (not shadcn Button) for full style control over outlined appearance
- or-divider background changed to bg-elevated to match the form panel surface (L3)
- Footer links point to /terms and /privacy routes (not # placeholder) anticipating future pages

## Deviations from Plan

None - plan executed exactly as written.

## User Setup Required

**External services require manual configuration.** The plan's `user_setup` section documents:
- Google OAuth: Client ID/Secret from Google Cloud Console, enable in Supabase dashboard
- GitHub OAuth: Client ID/Secret from GitHub Developer Settings, enable in Supabase dashboard
- Redirect URLs must be configured in both OAuth providers and Supabase

## Next Phase Readiness
- Social buttons component ready for use by Plan 02 (auth callback handling)
- OAuth flow triggers correctly via Supabase -- actual provider credentials needed for end-to-end testing

---
*Phase: 21-auth-redesign-and-social-oauth*
*Completed: 2026-03-08*
