# Phase 21: Auth Redesign and Social OAuth - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Add Google and GitHub social OAuth login/signup to the existing auth pages, polish the visual design of login and signup pages (keep split layout, improve form side), remove magic link, and ensure social auth integrates cleanly with the existing onboarding flow. No changes to the onboarding wizard itself, dashboard auth gates, or middleware logic.

</domain>

<decisions>
## Implementation Decisions

### Social OAuth providers
- Add both Google and GitHub as OAuth providers via Supabase Auth
- Social buttons appear on BOTH login and signup pages
- Social buttons positioned at the TOP of the form, above the "or" divider and email/password fields
- Buttons use outlined/neutral style with provider logos + text ("Continue with Google", "Continue with GitHub")
- Auto-create account on any page — social OAuth on login creates account if none exists (Supabase native behavior)
- Social signup pulls user's name from OAuth provider profile (no extra form step)
- After social signup, new users go through the same onboarding wizard as email users (handle_new_user trigger creates onboarding state row)

### Auth page visual polish
- Keep the existing split layout (brand panel left, form panel right)
- Polish the form side: remove redundant "Sign in to your ContextOS account" subtitle, tighten spacing
- Add teal-accented focus rings with subtle glow on input fields
- Fix placeholder footer links (Terms/Privacy both pointing to /login)
- Unified layout rhythm: social buttons → "or" divider → email/password form → action button

### Brand panel
- Claude's discretion on brand panel content — consider using Remotion hero animation as a dynamic product showcase, or refresh with product screenshot, or keep current gradient orbs
- Goal: brand panel should feel alive and showcase the product, not just be abstract decoration

### Magic link removal
- Remove magic link entirely from login page (toggle button, email field, and all related states)
- With Google + GitHub + email/password, 3 auth methods is sufficient
- Keep "Forgot password?" link with standard Supabase password reset email flow

### Sign-up vs sign-in flow
- Keep separate pages at /login and /signup (not merged)
- Keep "Full name" field on email signup form
- Social signup auto-populates name from provider
- Both pages share the same visual structure: social buttons → divider → form → CTA

### Claude's Discretion
- Brand panel content decision (Remotion player, product screenshot, or refreshed gradient design)
- Social button exact styling (border color, hover state, icon sizing)
- Input focus ring implementation (CSS box-shadow vs ring utility)
- Forgot password flow details (inline vs separate page)
- Form spacing and typography refinements
- Any micro-interactions or transitions between states
- Whether to add subtle animation to brand panel (slow orb drift, etc.)

</decisions>

<specifics>
## Specific Ideas

- User suggested exploring Remotion hero animation in the brand panel — would create a dynamic, product-showcasing auth experience
- Social buttons should follow the Linear/Vercel outlined-neutral pattern — recognizable provider logos on dark surface without brand color clashing
- Auth pages are the brand's handshake — should feel premium, not like default shadcn
- Design critique identified: form side feels generic compared to the polished brand panel — this phase should close that gap

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `(auth)/layout.tsx`: Split layout with brand panel (gradient orbs, grid, feature pills) + form panel — structural foundation stays
- `(auth)/login/page.tsx`: Working email/password auth logic via `supabase.auth.signInWithPassword` — preserve logic, add `signInWithOAuth`
- `(auth)/signup/page.tsx`: Working signup with name/email/password — preserve logic, add social buttons
- `(auth)/auth/callback/route.ts`: OAuth callback with onboarding redirect check — works for social OAuth too (Supabase uses same code exchange flow)
- `globals.css`: Full OKLCH dark token system (--primary is teal oklch(0.75 0.18 170)) — focus rings should use this
- Remotion Player component (`components/landing/RemotionPlayer.tsx`): Could be reused in brand panel if decided
- shadcn Button, Input, Label components: All inherit dark tokens

### Established Patterns
- DarkModeApplier applies .dark to html — auth pages get dark tokens automatically
- `handle_new_user` trigger creates workspace + profile + onboarding state on signup — social OAuth triggers this same path
- Supabase Auth `signInWithOAuth` uses the same callback route as magic links — `/auth/callback`
- CSS-only spring animations preferred over Framer Motion (Phase 15 decision)

### Integration Points
- Supabase Auth config: Google and GitHub providers must be enabled in Supabase dashboard + env vars for client IDs/secrets
- `(auth)/auth/callback/route.ts`: Already handles code exchange + onboarding redirect — no changes needed for social OAuth
- `middleware.ts`: No changes needed — social auth sessions are standard Supabase sessions
- `handle_new_user` DB trigger: Already handles new user creation — social OAuth users get the same treatment

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 21-auth-redesign-and-social-oauth*
*Context gathered: 2026-03-08*
