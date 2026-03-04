# Phase 16: Auth Redesign + Schema Foundation - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Auth pages (login, signup) match the dark brand identity established in Phase 15. Database tables for onboarding state tracking and activity events exist with proper RLS, indexes, and triggers. Server-side onboarding gate prevents dashboard access until onboarding is complete. No onboarding wizard UI (that's Phase 17) — just the infrastructure and auth restyling.

</domain>

<decisions>
## Implementation Decisions

### Auth page layout
- Split layout: left brand panel + right form panel
- Left panel shows brand elements (logo, tagline, visual) — shared across login and signup
- Right panel contains the auth form on an elevated dark surface
- Teal (#00D4AA) used on primary CTA buttons (Sign In, Sign Up) — consistent with DS-02 (teal = actionable)
- Magic link button stays secondary/outline
- Auth layout wraps both /login and /signup in the shared split layout via (auth)/layout.tsx

### Auth form UX
- Password primary, magic link secondary (current layout order preserved)
- Email/password form first, magic link as "or" alternative below — matches current structure
- Login: email + password + "Sign In" teal button, separator, magic link email + outline button
- Signup: collects name + email + password + "Sign Up" teal button

### Onboarding gate
- /onboarding is a separate top-level route (not nested under /dashboard)
- /onboarding has its own layout — no sidebar/nav from dashboard
- If user navigates to /dashboard while onboarding incomplete: redirect to current onboarding step + brief toast ("Complete setup first")
- Gate check happens server-side (ONB-09)

### Claude's Discretion
- Left brand panel content (logo + tagline + gradient art, or feature highlights, or other — pick what feels most premium and matches the landing page aesthetic)
- Login vs signup as separate pages or combined (current separate pages at /login and /signup may stay or merge)
- Signup "Full name" field: keep or remove (currently collected, stored in user metadata)
- "Check your email" confirmation: inline replacement vs dedicated page
- Password requirements: keep 6-char min or increase (dogfooding team, low friction preferred)
- Gate implementation level: middleware.ts vs dashboard/layout.tsx (consider latency tradeoffs)
- Post-onboarding landing destination: /dashboard or /dashboard/context
- user_onboarding_state table shape: step number, per-step booleans, JSONB, or hybrid — pick what best serves Phase 17's wizard needs
- activity_events event_type column: Postgres enum, text check constraint, or free text — pick based on how often new event types will be added
- 30-day retention policy implementation: pg_cron, application-level cleanup, or soft delete
- Migration file structure: single file or split per table

</decisions>

<specifics>
## Specific Ideas

- Auth pages should feel premium like the rest of the dark theme — not an afterthought
- Split layout is a deliberate brand touchpoint: first thing users see, sets the tone
- Teal button is a strong visual anchor on the dark form panel — immediate brand recognition
- Toast on redirect ("Complete setup first") gives user context without being blocking or alarming

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `globals.css`: Full OKLCH dark token system from Phase 15 — auth pages inherit automatically when .dark class applied
- `(auth)/layout.tsx`: Existing auth layout wrapper — needs redesign from centered card to split layout
- `(auth)/login/page.tsx`: Working email/password + magic link logic — preserve auth logic, restyle UI
- `(auth)/signup/page.tsx`: Working signup with name/email/password — preserve logic, restyle
- `(auth)/auth/callback/route.ts`: OAuth callback handler — works as-is, may need onboarding redirect logic
- shadcn components (Button, Input, Card, Label): Will inherit dark tokens
- Skeleton component from Phase 15: Can be used for auth page loading states if needed

### Established Patterns
- DarkModeApplier applies .dark to html — auth pages will automatically get dark tokens
- Landing page scoped under .landing-theme — no collision with auth pages
- `handle_new_user` trigger auto-creates workspace + profile on signup — onboarding state row should also be created here
- Migrations numbered sequentially (00001-00011) — next migration is 00012
- RLS pattern: workspace-scoped policies using auth.uid() joined through workspace_members

### Integration Points
- `middleware.ts`: Currently redirects unauth→login, auth→dashboard. Needs onboarding gate logic added (check onboarding_complete before allowing /dashboard)
- `dashboard/layout.tsx`: Server component that checks auth — backup location for onboarding gate if not in middleware
- `handle_new_user` trigger (00002): Should be extended or a new trigger added to auto-create onboarding state row on signup
- Auth callback route: After code exchange, may need to check onboarding status to redirect to /onboarding instead of /dashboard

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-auth-redesign-schema-foundation*
*Context gathered: 2026-03-04*
