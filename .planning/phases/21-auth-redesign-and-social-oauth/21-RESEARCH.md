# Phase 21: Auth Redesign and Social OAuth - Research

**Researched:** 2026-03-08
**Domain:** Supabase OAuth, Next.js auth pages, UI polish
**Confidence:** HIGH

## Summary

This phase adds Google and GitHub social OAuth to existing auth pages, removes magic link authentication, polishes the form-side visual design, and optionally refreshes the brand panel. The existing codebase already has the core infrastructure: the `(auth)/auth/callback/route.ts` handles code exchange with onboarding redirect logic, `handle_new_user` trigger creates workspace/profile/onboarding state for any new user, and the split layout with brand panel is in place.

The implementation is straightforward because Supabase's `signInWithOAuth` uses the exact same PKCE callback flow as magic links. The callback route already works for OAuth -- no changes needed. The main work is UI: adding social buttons, removing magic link UI, adding focus ring styling, and fixing footer links.

**Primary recommendation:** Use `supabase.auth.signInWithOAuth({ provider, options: { redirectTo } })` for both Google and GitHub. Extract social button logic into a shared component used by both login and signup pages. Brand panel decision (Remotion vs static) should be a separate task from the OAuth work.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Add both Google and GitHub as OAuth providers via Supabase Auth
- Social buttons appear on BOTH login and signup pages
- Social buttons positioned at the TOP of the form, above the "or" divider and email/password fields
- Buttons use outlined/neutral style with provider logos + text ("Continue with Google", "Continue with GitHub")
- Auto-create account on any page -- social OAuth on login creates account if none exists (Supabase native behavior)
- Social signup pulls user's name from OAuth provider profile (no extra form step)
- After social signup, new users go through the same onboarding wizard as email users (handle_new_user trigger creates onboarding state row)
- Keep the existing split layout (brand panel left, form panel right)
- Polish the form side: remove redundant subtitle, tighten spacing
- Add teal-accented focus rings with subtle glow on input fields
- Fix placeholder footer links (Terms/Privacy both pointing to /login)
- Unified layout rhythm: social buttons -> "or" divider -> email/password form -> action button
- Remove magic link entirely from login page (toggle button, email field, and all related states)
- Keep "Forgot password?" link with standard Supabase password reset email flow
- Keep separate pages at /login and /signup (not merged)
- Keep "Full name" field on email signup form
- Both pages share the same visual structure: social buttons -> divider -> form -> CTA

### Claude's Discretion
- Brand panel content decision (Remotion player, product screenshot, or refreshed gradient design)
- Social button exact styling (border color, hover state, icon sizing)
- Input focus ring implementation (CSS box-shadow vs ring utility)
- Forgot password flow details (inline vs separate page)
- Form spacing and typography refinements
- Any micro-interactions or transitions between states
- Whether to add subtle animation to brand panel (slow orb drift, etc.)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @supabase/supabase-js | ^2.49.0 | `signInWithOAuth` for Google/GitHub | Already installed, native OAuth support |
| @supabase/ssr | ^0.6.0 | Server-side Supabase client for callback route | Already installed, handles PKCE flow |
| Next.js | ^15.2.0 | App Router with route groups | Already installed |
| lucide-react | ^0.469.0 | UI icons (if needed for non-brand icons) | Already installed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @remotion/player | ^4.0.434 | Brand panel animation (if Remotion option chosen) | Already installed, reuse RemotionHeroPlayer component |

### No New Dependencies Needed
Social OAuth requires zero new packages. Supabase handles the entire flow. Provider logos (Google, GitHub) should be inline SVGs -- not an icon library dependency.

## Architecture Patterns

### Recommended Component Structure
```
apps/web/src/app/(auth)/
├── layout.tsx            # Split layout (brand panel + form panel) -- MODIFY brand panel
├── login/page.tsx        # REWRITE: social buttons + email/password (remove magic link)
├── signup/page.tsx       # REWRITE: social buttons + email/password
├── auth/callback/route.ts # NO CHANGES NEEDED
└── reset-password/page.tsx # NEW (optional): password reset form
```

```
apps/web/src/components/auth/
├── social-buttons.tsx     # NEW: shared Google + GitHub OAuth buttons
└── provider-icons.tsx     # NEW: inline SVG icons for Google and GitHub
```

### Pattern 1: Shared Social OAuth Buttons Component
**What:** Extract social login buttons into a reusable component used by both login and signup pages.
**When to use:** Always -- avoids duplicating OAuth logic across two pages.
**Example:**
```typescript
// Source: Supabase official docs
'use client'

import { createClient } from '@/lib/supabase/client'

interface SocialButtonsProps {
  redirectTo?: string
}

export function SocialButtons({ redirectTo }: SocialButtonsProps) {
  const handleOAuth = async (provider: 'google' | 'github') => {
    const supabase = createClient()
    await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: redirectTo || `${window.location.origin}/auth/callback`,
      },
    })
  }

  return (
    <div className="space-y-3">
      <button onClick={() => handleOAuth('google')} className="...">
        <GoogleIcon /> Continue with Google
      </button>
      <button onClick={() => handleOAuth('github')} className="...">
        <GitHubIcon /> Continue with GitHub
      </button>
    </div>
  )
}
```

### Pattern 2: Password Reset via Supabase
**What:** Use `supabase.auth.resetPasswordForEmail` to send reset email, then `updateUser` on the callback page.
**Example:**
```typescript
// Send reset email
await supabase.auth.resetPasswordForEmail(email, {
  redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
})

// On reset-password page, after user lands from email link:
await supabase.auth.updateUser({ password: newPassword })
```

### Pattern 3: Inline SVG Provider Icons
**What:** Use inline SVGs for Google and GitHub logos instead of importing from a library.
**Why:** Zero dependency, exact brand colors, small footprint.
```typescript
function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" width="20" height="20">
      {/* Official Google "G" paths with brand colors */}
    </svg>
  )
}

function GitHubIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
      {/* GitHub Octocat mark */}
    </svg>
  )
}
```

### Anti-Patterns to Avoid
- **Duplicating OAuth logic in both pages:** Extract into SocialButtons component
- **Using `onClick` with `<a>` for OAuth:** Use `<button>` -- OAuth triggers a redirect via JS, not a link
- **Hardcoding redirect URLs:** Always construct from `window.location.origin` for env portability
- **Adding loading state for OAuth buttons:** The redirect happens instantly; no spinner needed (browser navigates away)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth flow | Custom OAuth state machine | `supabase.auth.signInWithOAuth()` | Handles PKCE, state validation, token exchange |
| Password reset | Custom reset token system | `supabase.auth.resetPasswordForEmail()` | Secure token generation and email delivery |
| Session management | Cookie parsing for social auth | Existing callback route | Already handles code exchange + onboarding redirect |
| Provider icons | npm package for brand icons | Inline SVGs | 2 icons, zero bundle cost |

**Key insight:** The entire OAuth backend is handled by Supabase. This phase is 90% frontend UI work and 10% calling `signInWithOAuth`.

## Common Pitfalls

### Pitfall 1: Supabase Dashboard Not Configured
**What goes wrong:** `signInWithOAuth` redirects to Supabase error page instead of Google/GitHub consent screen.
**Why it happens:** Google and GitHub providers must be enabled in Supabase dashboard with client ID/secret, AND the callback URL must be in the redirect allow list.
**How to avoid:** Before coding, enable providers in Supabase dashboard (Authentication > Providers). Add `http://localhost:3000/auth/callback` and production URL to redirect allow list.
**Warning signs:** "Provider not enabled" error, redirect to unexpected URL.

### Pitfall 2: Missing Redirect URL in signInWithOAuth
**What goes wrong:** After OAuth consent, user gets redirected to Supabase default instead of app callback.
**Why it happens:** `redirectTo` option not passed, or URL not in Supabase allow list.
**How to avoid:** Always pass `redirectTo` pointing to `/auth/callback`. Verify URL is in Supabase dashboard redirect allow list.

### Pitfall 3: Social User Name Not Populated
**What goes wrong:** Social signup creates user but `raw_user_meta_data.full_name` is empty.
**Why it happens:** Google and GitHub provide name in different metadata fields. Google uses `full_name` and `name`, GitHub uses `user_name` and `name`.
**How to avoid:** The `handle_new_user` trigger should read from `raw_user_meta_data` -- verify it handles both Google and GitHub metadata field names. Google provides `full_name`, GitHub provides `user_name`.

### Pitfall 4: "Forgot password?" Link Still Points to /login
**What goes wrong:** Current code has `<Link href="/login">` for forgot password -- it's a placeholder that goes nowhere useful.
**How to avoid:** Either (a) implement a dedicated `/reset-password` page, or (b) use inline state on the login page to show a "reset password" email form. Decision is Claude's discretion per CONTEXT.md.

### Pitfall 5: bg-overlay vs bg-elevated on Form Panel
**What goes wrong:** Current layout uses `bg-overlay` (L4) for the form panel, which is the highest surface level.
**Why it matters:** Phase 16 notes say "bg-elevated (L3) form panel" but current code uses `bg-overlay`. Verify which is correct and be consistent.
**How to avoid:** Check which surface level the form panel should use. `bg-elevated` (L3) is more appropriate for a form surface; `bg-overlay` (L4) is for overlays/modals.

## Code Examples

### Existing Callback Route (NO CHANGES NEEDED)
```typescript
// Source: apps/web/src/app/(auth)/auth/callback/route.ts
// Already handles: code exchange, onboarding status check, redirect
// Works identically for email signup, magic link, and social OAuth
```

### Social OAuth Button Click Handler
```typescript
// Source: Supabase official docs (verified)
const supabase = createClient()
await supabase.auth.signInWithOAuth({
  provider: 'google', // or 'github'
  options: {
    redirectTo: `${window.location.origin}/auth/callback`,
  },
})
// Browser navigates away -- no response handling needed
```

### Teal Focus Ring (CSS approach)
```css
/* Using project's OKLCH primary token */
input:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px oklch(0.75 0.18 170 / 0.4), 0 0 12px oklch(0.75 0.18 170 / 0.15);
  border-color: oklch(0.75 0.18 170 / 0.6);
}
```

### Outlined Social Button Style (Linear/Vercel pattern)
```typescript
// Outlined neutral button on dark surface
<button
  className="flex w-full items-center justify-center gap-3 rounded-lg border border-border
             bg-transparent px-4 py-2.5 text-sm font-medium text-foreground
             transition-colors hover:bg-muted/50"
>
  <GoogleIcon className="h-5 w-5" />
  Continue with Google
</button>
```

### Password Reset Email
```typescript
// Source: Supabase official docs (verified)
const supabase = createClient()
const { error } = await supabase.auth.resetPasswordForEmail(email, {
  redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
})
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Magic link OTP auth | Social OAuth (Google/GitHub) | This phase | Faster login, no email wait |
| signInWithOtp | signInWithOAuth | Supabase v2+ | Same callback route, different trigger |
| Custom OAuth flows | Supabase managed OAuth | Supabase v2 | Zero server-side OAuth code needed |

**Deprecated/outdated:**
- Magic link (`signInWithOtp`): Being removed this phase. Three auth methods (Google + GitHub + email/password) is sufficient.

## Open Questions

1. **Brand panel decision (Remotion vs static)**
   - What we know: RemotionHeroPlayer component exists at `components/landing/RemotionPlayer.tsx`, uses lazy import and `next/dynamic` with ssr:false. Works on landing page.
   - What's unclear: Whether reusing Remotion in the auth brand panel is worth the bundle cost for auth pages. The hero animation is designed for full-width landing, not a half-panel.
   - Recommendation: Start with a refreshed static brand panel (better orbs, maybe product screenshot). Remotion can be added as an enhancement if desired. This keeps auth page load fast.

2. **Forgot password: inline vs separate page**
   - What we know: `resetPasswordForEmail` sends email with link. Need a page to land on.
   - What's unclear: Whether to show the email input inline on login page (toggle) or create a dedicated `/reset-password` route.
   - Recommendation: Dedicated `/reset-password` page. Cleaner UX, avoids cluttering the streamlined login form.

3. **handle_new_user trigger and social OAuth metadata**
   - What we know: Trigger runs on any new user. Google provides `full_name`, GitHub provides `user_name` in `raw_user_meta_data`.
   - What's unclear: Whether the trigger currently reads the right field for both providers.
   - Recommendation: Verify the trigger SQL during implementation. May need to add `COALESCE(raw_user_meta_data->>'full_name', raw_user_meta_data->>'name', raw_user_meta_data->>'user_name')`.

## Sources

### Primary (HIGH confidence)
- [Supabase Google OAuth docs](https://supabase.com/docs/guides/auth/social-login/auth-google) - signInWithOAuth API, PKCE flow
- [Supabase GitHub OAuth docs](https://supabase.com/docs/guides/auth/social-login/auth-github) - signInWithOAuth API
- [Supabase password docs](https://supabase.com/docs/guides/auth/passwords) - resetPasswordForEmail API
- Existing codebase: `(auth)/auth/callback/route.ts`, `(auth)/login/page.tsx`, `(auth)/signup/page.tsx`, `(auth)/layout.tsx`

### Secondary (MEDIUM confidence)
- [Teknasyon Engineering - Next.js Supabase Google Login](https://engineering.teknasyon.com/next-js-with-supabase-google-login-step-by-step-guide-088ef06e0501) - verified patterns match official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - using only existing dependencies, Supabase API is well-documented
- Architecture: HIGH - callback route already works, component extraction is straightforward
- Pitfalls: HIGH - well-known OAuth configuration requirements, verified with official docs
- Brand panel: MEDIUM - discretionary decision, multiple viable options

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable -- Supabase OAuth API is mature)
