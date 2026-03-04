# Phase 16: Auth Redesign + Schema Foundation - Research

**Researched:** 2026-03-04
**Domain:** Auth UI redesign (dark theme), Supabase schema (onboarding state, activity events), middleware onboarding gate
**Confidence:** HIGH

## Summary

Phase 16 has three distinct workstreams: (1) restyling auth pages (login/signup) to match the dark brand identity established in Phase 15, (2) creating two new database tables (`user_onboarding_state` and `activity_events`) with proper RLS, indexes, triggers, and retention policies, and (3) implementing a server-side onboarding gate that prevents dashboard access until onboarding is complete.

The codebase already has all the dark theme tokens (`.dark` class in `globals.css` with OKLCH values), the auth page structure (`(auth)/layout.tsx`, `login/page.tsx`, `signup/page.tsx`), working Supabase auth logic, and an established RLS/migration pattern (11 migrations, workspace-scoped policies). The auth pages currently use a centered card layout and need conversion to a split layout (left brand panel + right form panel). The `handle_new_user` trigger in migration `00002` is the natural place to auto-create onboarding state rows. Sonner is already a dependency but has no `<Toaster>` component wired up yet.

**Primary recommendation:** Structure work as three plans: (1) database migrations for both tables + trigger extension, (2) auth page UI redesign with split layout, (3) onboarding gate in middleware/layout + toast setup. Keep database work first since auth callback needs to know about onboarding state for redirect logic.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Split layout: left brand panel + right form panel for auth pages
- Left panel shows brand elements (logo, tagline, visual) -- shared across login and signup
- Right panel contains the auth form on an elevated dark surface
- Teal (#00D4AA) used on primary CTA buttons (Sign In, Sign Up) -- consistent with DS-02
- Magic link button stays secondary/outline
- Auth layout wraps both /login and /signup in the shared split layout via (auth)/layout.tsx
- Password primary, magic link secondary (current layout order preserved)
- Email/password form first, magic link as "or" alternative below
- Login: email + password + "Sign In" teal button, separator, magic link email + outline button
- Signup: collects name + email + password + "Sign Up" teal button
- /onboarding is a separate top-level route (not nested under /dashboard)
- /onboarding has its own layout -- no sidebar/nav from dashboard
- If user navigates to /dashboard while onboarding incomplete: redirect to current onboarding step + brief toast ("Complete setup first")
- Gate check happens server-side (ONB-09)

### Claude's Discretion
- Left brand panel content (logo + tagline + gradient art, or feature highlights, or other)
- Login vs signup as separate pages or combined
- Signup "Full name" field: keep or remove
- "Check your email" confirmation: inline replacement vs dedicated page
- Password requirements: keep 6-char min or increase
- Gate implementation level: middleware.ts vs dashboard/layout.tsx
- Post-onboarding landing destination: /dashboard or /dashboard/context
- user_onboarding_state table shape: step number, per-step booleans, JSONB, or hybrid
- activity_events event_type column: Postgres enum, text check constraint, or free text
- 30-day retention policy implementation: pg_cron, application-level cleanup, or soft delete
- Migration file structure: single file or split per table

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AUTH-01 | Login and signup pages use dark theme matching dashboard brand identity | Dark theme tokens already exist in globals.css `.dark` block; auth pages need split layout redesign using these tokens |
| AUTH-02 | Auth pages use the same teal accent, typography, and surface tokens as dashboard | Teal primary (`oklch(0.75 0.18 170)`) and elevated surface (`oklch(0.19 0.02 270)`) tokens are defined; form panel uses `bg-elevated`, buttons use `bg-primary` |
| ACT-04 | Activity events table exists with 30-day retention policy | New migration creates `activity_events` table with workspace-scoped RLS and pg_cron retention job |
| ONB-07 | Onboarding progress persists across browser refreshes (database-backed state) | New `user_onboarding_state` table auto-created by trigger on signup; stores step completion state |
| ONB-09 | Server-side onboarding gate prevents dashboard access until onboarding complete | Gate check in `dashboard/layout.tsx` server component queries onboarding state and redirects to `/onboarding` |
</phase_requirements>

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | ^15.2.0 | App Router, server components, middleware | Already in use |
| @supabase/ssr | ^0.6.0 | Server-side Supabase client for cookies/auth | Already in use |
| @supabase/supabase-js | ^2.49.0 | Supabase client (browser + server) | Already in use |
| sonner | ^1.7.0 | Toast notifications | Already in package.json, not yet wired |
| lucide-react | ^0.469.0 | Icons | Already in use |
| Tailwind CSS | ^4.0.0 | Styling with OKLCH tokens | Already in use |
| shadcn/ui | ^3.8.5 | UI component primitives | Already in use |

### Supporting (Supabase-side)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pg_cron | 1.6.x | Scheduled job for 30-day retention cleanup | Enabled by default on Supabase hosted; needs `create extension` for local |
| moddatetime | built-in | Auto-update `updated_at` timestamps | Already enabled in migration 00001 |

### No New Dependencies Needed
This phase requires zero new npm packages. Everything is already installed. The only additions are Supabase-side (pg_cron extension, new migrations).

## Architecture Patterns

### Recommended Project Structure (changes only)
```
apps/web/src/
  app/
    (auth)/
      layout.tsx              # REWRITE: split layout (left brand + right form)
      login/page.tsx           # RESTYLE: preserve logic, update UI
      signup/page.tsx          # RESTYLE: preserve logic, update UI
      auth/callback/route.ts   # MODIFY: add onboarding redirect check
    onboarding/
      layout.tsx               # NEW: minimal layout (no sidebar)
      page.tsx                 # NEW: placeholder redirect to step 1 (Phase 17 builds wizard)
  components/
    ui/sonner.tsx              # NEW: shadcn Toaster wrapper
supabase/
  migrations/
    00012_onboarding_and_activity.sql  # NEW: both tables + trigger extension + pg_cron
```

### Pattern 1: Split Auth Layout
**What:** Two-column auth layout with brand panel (left) and form panel (right)
**When to use:** Login and signup pages
**Example:**
```tsx
// (auth)/layout.tsx
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      {/* Left: Brand panel */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-center items-center bg-background p-12">
        <div className="max-w-md space-y-6">
          <h1 className="text-3xl font-bold tracking-tight">
            <span className="bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
              ContextOS
            </span>
          </h1>
          <p className="text-lg text-muted-foreground">
            AI-generated context for every engineering ticket
          </p>
          {/* Gradient accent art or feature highlights */}
        </div>
      </div>
      {/* Right: Form panel on elevated surface */}
      <div className="flex w-full lg:w-1/2 flex-col items-center justify-center bg-elevated p-8">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </div>
  )
}
```

### Pattern 2: Teal CTA Button Styling
**What:** Primary action buttons use teal with dark text, matching DS-02 convention
**When to use:** Sign In, Sign Up buttons
**Example:**
```tsx
// The existing Button component with default variant already maps to --primary
// which is oklch(0.75 0.18 170) in dark mode = teal
// So `<Button>Sign In</Button>` renders teal automatically in .dark context
// No custom classes needed -- the token system handles it

<Button type="submit" className="w-full">
  {loading ? 'Signing in...' : 'Sign In'}
</Button>

// Magic link button stays outline variant
<Button type="submit" variant="outline" className="w-full">
  Send Magic Link
</Button>
```

### Pattern 3: Onboarding Gate in Dashboard Layout (RECOMMENDED)
**What:** Server-side check in dashboard/layout.tsx that queries onboarding state and redirects
**When to use:** Every dashboard page load
**Why layout.tsx over middleware.ts:** Middleware runs on the Edge Runtime which has latency constraints. The `supabase.auth.getUser()` call already happens in middleware for session refresh. Adding a database query for onboarding state in middleware adds a second network round-trip on every request (including static assets that match). The dashboard layout is a server component that already calls `getUser()` and is the natural place for an additional database query. It only runs on dashboard routes, not all routes.
**Example:**
```tsx
// dashboard/layout.tsx
export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  // Onboarding gate check
  const { data: onboardingState } = await supabase
    .from('user_onboarding_state')
    .select('onboarding_completed')
    .eq('user_id', user.id)
    .single()

  if (!onboardingState?.onboarding_completed) {
    redirect('/onboarding')
  }

  return (
    <div className="relative flex flex-col min-h-screen bg-background dashboard-grain">
      <Sidebar userEmail={user.email ?? ''} userFullName={user.user_metadata?.full_name} />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-6 py-10 lg:px-10">{children}</div>
      </main>
    </div>
  )
}
```

### Pattern 4: Workspace-Scoped RLS (established pattern)
**What:** RLS policies that restrict data access to workspace members
**When to use:** All workspace-scoped tables (including activity_events)
**Example:**
```sql
-- Exact pattern from existing codebase (migration 00001)
alter table public.activity_events enable row level security;

create policy "workspace_data" on public.activity_events
  for all using (
    workspace_id in (
      select workspace_id from public.workspace_members where user_id = auth.uid()
    )
  );
```

### Pattern 5: User-Scoped RLS (for onboarding state)
**What:** RLS policy where user can only see/modify their own onboarding row
**When to use:** user_onboarding_state table (not workspace-scoped, user-scoped)
**Example:**
```sql
alter table public.user_onboarding_state enable row level security;

create policy "own_onboarding" on public.user_onboarding_state
  for all using (user_id = auth.uid())
  with check (user_id = auth.uid());
```

### Anti-Patterns to Avoid
- **Onboarding gate in middleware.ts:** Adds database query latency to every request. The existing middleware already does `getUser()` which is a network call. A second query for onboarding state doubles the cost. Use `dashboard/layout.tsx` instead -- it only runs on dashboard routes.
- **Using getSession() for auth checks:** Always use `getUser()` as it validates the JWT against the Supabase Auth server. `getSession()` reads from cookies without validation.
- **Storing onboarding state in user_metadata:** User metadata is stored in the auth.users JWT, which means changes require a token refresh. A separate table is more reliable and queryable.
- **Creating a new trigger for onboarding:** Extend the existing `handle_new_user()` trigger function rather than creating a second trigger on auth.users. Multiple triggers on the same table have undefined execution order in Postgres.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Toast notifications | Custom notification system | sonner (already installed) | Handles positioning, animations, stacking, auto-dismiss; shadcn has a wrapper component |
| Scheduled data cleanup | Application-level cron or setTimeout | pg_cron extension | Runs inside Postgres, no external process needed, survives app restarts |
| Auto-update timestamps | Manual `updated_at = now()` in queries | moddatetime trigger (already set up) | Already established pattern in migration 00001 |
| Dark mode tokens | Custom CSS variables per component | Existing `.dark` token block in globals.css | Phase 15 already built the complete token system |
| Auth session management | Custom JWT handling | @supabase/ssr middleware pattern | Already implemented and working |

## Common Pitfalls

### Pitfall 1: Onboarding row not created for existing users
**What goes wrong:** The `handle_new_user` trigger only fires on NEW signups. Existing users who signed up before this migration will not have a `user_onboarding_state` row. The gate check will fail (no row = `null`).
**Why it happens:** Trigger only fires on INSERT into auth.users.
**How to avoid:** Two approaches: (1) Treat NULL (no row) as "onboarding complete" for backward compatibility -- existing users skip onboarding. (2) Run a backfill migration that creates rows for all existing users with `onboarding_completed = true`. Approach 1 is simpler and correct for a dogfooding team.
**Warning signs:** Existing team members locked out of dashboard after deployment.

### Pitfall 2: Auth callback redirect ignoring onboarding
**What goes wrong:** After magic link or OAuth callback, user is redirected to `/dashboard` even if onboarding is incomplete.
**Why it happens:** The `auth/callback/route.ts` currently hardcodes `next ?? '/dashboard'` as the redirect target.
**How to avoid:** After exchanging the auth code, check onboarding state in the callback route. If incomplete, redirect to `/onboarding` instead of `/dashboard`. However, the dashboard layout gate is a safety net -- even if the callback sends them to `/dashboard`, the layout will redirect to `/onboarding`.
**Warning signs:** Brief flash of dashboard before redirect to onboarding.

### Pitfall 3: Split layout breaking on mobile
**What goes wrong:** The left brand panel takes up screen space on small devices, pushing the form off-screen.
**Why it happens:** No responsive handling of the two-column layout.
**How to avoid:** Use `hidden lg:flex` on the brand panel so it only shows on desktop. On mobile, only the form panel renders full-width. This is standard practice for split auth layouts.
**Warning signs:** Unusable auth form on mobile widths.

### Pitfall 4: pg_cron not available in local Supabase
**What goes wrong:** Local development with `supabase start` may not have pg_cron enabled, causing migration to fail.
**Why it happens:** pg_cron requires explicit enabling in local Supabase CLI.
**How to avoid:** Include `create extension if not exists pg_cron with schema pg_catalog;` at the top of the migration. For local dev, also ensure `supabase/config.toml` has no restrictions blocking it. If local pg_cron is problematic, wrap the cron schedule in a conditional or make it a separate migration that runs on hosted only.
**Warning signs:** Migration fails with "extension pg_cron not available."

### Pitfall 5: Elevated surface token on form panel not rendering
**What goes wrong:** The `bg-elevated` class doesn't resolve because the CSS variable mapping is through `@theme inline`.
**Why it happens:** The elevated token is defined as `--elevated: oklch(0.19 0.02 270)` in `.dark` and mapped via `--color-elevated: var(--elevated)` in `@theme inline`.
**How to avoid:** Use `bg-elevated` which maps through `--color-elevated`. This is already configured in `globals.css`. Verify by inspecting that the computed background is `oklch(0.19 0.02 270)`.
**Warning signs:** Form panel appears same color as page background.

### Pitfall 6: Toast not showing on redirect
**What goes wrong:** Calling `toast("Complete setup first")` then `redirect("/onboarding")` in a server component -- the toast never renders because redirect is server-side.
**Why it happens:** Server-side redirects happen before the client renders, so sonner never gets the toast event.
**How to avoid:** Set a query parameter or cookie on redirect (e.g., `redirect('/onboarding?from=dashboard')`), then read it on the onboarding page client component to trigger the toast. Or use middleware that sets a cookie before redirecting.
**Warning signs:** Redirect happens silently without the expected "Complete setup first" toast.

## Claude's Discretion Recommendations

### Left brand panel content
**Recommendation:** Logo + tagline + subtle gradient accent. Keep it clean and minimal -- a large ContextOS wordmark with teal gradient (matching the sidebar `bg-gradient-to-r from-primary to-primary/70`), the tagline "AI-generated context for every engineering ticket", and a subtle radial teal glow behind the logo area. No feature highlights or screenshots -- too much visual noise for an auth page.

### Login vs signup: keep separate pages
**Recommendation:** Keep `/login` and `/signup` as separate pages. They have different form fields (signup has full name), different success states (signup shows "check your email"), and separate mental models. Combining adds complexity for no user benefit.

### Signup "Full name" field: keep
**Recommendation:** Keep the full name field. It's already wired into `raw_user_meta_data`, used by the sidebar avatar initials, and stored in the profiles table. Removing it would break existing functionality.

### "Check your email" confirmation: inline replacement
**Recommendation:** Keep the current inline replacement pattern (state toggle within the same page). It's already implemented and works. A dedicated page adds routing complexity with no UX benefit.

### Password requirements: keep 6-char min
**Recommendation:** Keep 6-character minimum. This is a dogfooding team, low friction is preferred per context. Supabase Auth also enforces its own minimum on the server side.

### Gate implementation: dashboard/layout.tsx
**Recommendation:** Use `dashboard/layout.tsx` (server component). See Pattern 3 above for rationale. Middleware adds latency to all routes; the layout only checks on dashboard routes and already has a server-side auth check in place.

### Post-onboarding destination: /dashboard
**Recommendation:** Redirect to `/dashboard` after onboarding completes. It's the logical home page, and the home page (Phase 19 HOME-01) will show summary view. `/dashboard/context` is a sub-section.

### user_onboarding_state table shape: step-based with completed boolean
**Recommendation:** Use a `current_step` integer column plus a `completed_at` timestamptz column. This is the simplest shape that serves Phase 17's wizard needs:
- `current_step` (integer, default 1): which step the user is on (1-4 per ONB-01)
- `completed_at` (timestamptz, nullable): null means incomplete, set when wizard finishes
- No per-step booleans (adds columns for each step, hard to extend)
- No JSONB (over-flexible, no type safety in Postgres, harder to query with RLS)

### activity_events event_type: text with check constraint
**Recommendation:** Use `text not null check (event_type in ('sync_started', 'sync_completed', 'context_generated', 'integration_connected', 'integration_disconnected', 'user_signed_up'))`. This matches the established pattern in the codebase (see `oauth_tokens.provider`, `workspace_integrations.status`, etc.). New event types require a migration to alter the constraint, which is acceptable for a controlled list. Free text loses validation. Postgres enums are harder to alter (require `ALTER TYPE ... ADD VALUE`).

### 30-day retention: pg_cron
**Recommendation:** Use pg_cron to schedule a daily cleanup job. This is the cleanest approach:
- Runs inside Postgres, no application code needed
- Survives app deployments and restarts
- Already a pattern referenced in migration 00003 comments
- Soft delete adds complexity (need to filter deleted rows in every query)
- Application-level cleanup requires a running server and cron library

### Migration file structure: single file
**Recommendation:** One migration file (`00012_onboarding_and_activity.sql`) containing both tables, the trigger extension, indexes, RLS policies, and the pg_cron job. This is how the existing codebase works -- migration 00001 has 430 lines covering all initial tables. Splitting per table adds file management overhead with no benefit for two small tables.

## Code Examples

### Migration: user_onboarding_state table
```sql
-- Source: Based on established patterns from 00001_initial_schema.sql
create table public.user_onboarding_state (
  user_id uuid primary key references auth.users(id) on delete cascade,
  current_step integer not null default 1 check (current_step between 1 and 4),
  completed_at timestamptz,  -- null = not completed
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- RLS: user can only access their own onboarding state
alter table public.user_onboarding_state enable row level security;

create policy "own_onboarding" on public.user_onboarding_state
  for all using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- Auto-update timestamp
create trigger set_updated_at before update on public.user_onboarding_state
  for each row execute function moddatetime(updated_at);
```

### Migration: activity_events table
```sql
create table public.activity_events (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  actor_id uuid references auth.users(id) on delete set null,
  event_type text not null check (event_type in (
    'sync_started', 'sync_completed', 'context_generated',
    'integration_connected', 'integration_disconnected', 'user_signed_up'
  )),
  metadata jsonb default '{}',
  created_at timestamptz not null default now()
);

-- Composite index for timeline queries (workspace + chronological)
create index idx_activity_events_workspace_time
  on public.activity_events (workspace_id, created_at desc);

-- RLS: workspace members can access
alter table public.activity_events enable row level security;

create policy "workspace_data" on public.activity_events
  for all using (
    workspace_id in (
      select workspace_id from public.workspace_members where user_id = auth.uid()
    )
  );
```

### Migration: pg_cron retention job
```sql
-- Enable pg_cron if not already
create extension if not exists pg_cron with schema pg_catalog;

-- Schedule daily cleanup: delete events older than 30 days
select cron.schedule(
  'activity-events-30d-retention',
  '0 3 * * *',  -- 3:00 AM UTC daily
  $$ delete from public.activity_events where created_at < now() - interval '30 days' $$
);
```

### Migration: Extend handle_new_user trigger
```sql
-- Replace existing function to also create onboarding state
create or replace function public.handle_new_user()
returns trigger as $$
declare
  new_workspace_id uuid;
  email_prefix text;
  workspace_slug text;
begin
  email_prefix := split_part(NEW.email, '@', 1);
  workspace_slug := lower(regexp_replace(email_prefix, '[^a-z0-9]', '-', 'g'))
    || '-' || substr(gen_random_uuid()::text, 1, 8);

  -- Create workspace
  insert into public.workspaces (name, slug)
  values (email_prefix || '''s Workspace', workspace_slug)
  returning id into new_workspace_id;

  -- Create profile
  insert into public.profiles (id, email, full_name)
  values (NEW.id, NEW.email, coalesce(NEW.raw_user_meta_data->>'full_name', email_prefix));

  -- Create membership (owner role)
  insert into public.workspace_members (workspace_id, user_id, role)
  values (new_workspace_id, NEW.id, 'owner');

  -- Create onboarding state (starts at step 1, not completed)
  insert into public.user_onboarding_state (user_id)
  values (NEW.id);

  return NEW;
end;
$$ language plpgsql security definer;
```

### Sonner Toaster Setup
```tsx
// components/ui/sonner.tsx
// Source: shadcn/ui sonner component pattern
"use client"

import { Toaster as SonnerToaster } from "sonner"

export function Toaster() {
  return (
    <SonnerToaster
      theme="dark"
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast: "bg-elevated border-border text-foreground",
          description: "text-muted-foreground",
        },
      }}
    />
  )
}
```

```tsx
// Add to app/layout.tsx (root layout)
import { Toaster } from "@/components/ui/sonner"

// Inside <body>:
<Toaster />
```

### Toast on Redirect (client-side pattern)
```tsx
// onboarding/layout.tsx or page.tsx (client component)
'use client'

import { useSearchParams } from 'next/navigation'
import { useEffect } from 'react'
import { toast } from 'sonner'

export function OnboardingToastHandler() {
  const searchParams = useSearchParams()

  useEffect(() => {
    if (searchParams.get('from') === 'dashboard') {
      toast('Complete setup first', {
        description: 'Finish onboarding to access your dashboard',
      })
    }
  }, [searchParams])

  return null
}
```

### Auth Callback with Onboarding Check
```tsx
// (auth)/auth/callback/route.ts
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
      // Check onboarding status
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        const { data: onboardingState } = await supabase
          .from('user_onboarding_state')
          .select('completed_at')
          .eq('user_id', user.id)
          .single()

        const destination = onboardingState?.completed_at ? next : '/onboarding'

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
  }

  return NextResponse.redirect(`${origin}/login?error=auth`)
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `getSession()` for auth checks | `getUser()` always (validates JWT) | Supabase SSR 0.5+ | Security: getSession can be spoofed server-side |
| next-themes ThemeProvider | Manual .dark class via DarkModeApplier | Phase 15 decision | No dependency; dark mode is brand, not toggle |
| `animate-pulse` skeleton | `skeleton-shimmer` CSS class | Phase 15 | Premium shimmer-sweep effect |
| Centered card auth layout | Split layout (brand + form) | Phase 16 decision | Premium brand touchpoint on first interaction |

## Open Questions

1. **pg_cron on local Supabase CLI**
   - What we know: pg_cron is available on hosted Supabase. The local CLI (supabase start) may or may not have it depending on version.
   - What's unclear: Whether `create extension if not exists pg_cron` will succeed in local dev.
   - Recommendation: Include it in the migration with `if not exists`. If local fails, wrap the `cron.schedule()` call in a DO block with exception handling, or put it in a separate migration file that only runs on hosted.

2. **Backfill strategy for existing users**
   - What we know: Existing team members (3 people) signed up before this migration. They will not have onboarding state rows.
   - What's unclear: Whether they should go through onboarding or skip it.
   - Recommendation: Treat NULL (no onboarding row) as "completed" in the gate check. This means `if (!onboardingState || onboardingState.completed_at)` allows access. Only new signups after this migration go through onboarding. Alternatively, insert backfill rows with `completed_at = now()` in the same migration.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `globals.css`, `(auth)/layout.tsx`, `login/page.tsx`, `signup/page.tsx`, `middleware.ts`, `lib/supabase/middleware.ts`, `00001_initial_schema.sql`, `00002_workspace_creation_trigger.sql` -- direct file reads
- Supabase pg_cron docs: https://supabase.com/docs/guides/cron/quickstart -- exact SQL syntax for cron.schedule()
- Supabase Auth server-side Next.js docs: https://supabase.com/docs/guides/auth/server-side/nextjs -- middleware pattern, getUser() requirement

### Secondary (MEDIUM confidence)
- Supabase middleware performance discussion: https://github.com/orgs/supabase/discussions/20905 -- confirms getUser() latency concern, validates layout.tsx approach over middleware
- shadcn/ui Sonner component: https://ui.shadcn.com/docs/components/radix/sonner -- Toaster wrapper pattern
- Supabase trigger extension pattern: https://github.com/orgs/supabase/discussions/306 -- extending handle_new_user for additional tables

### Tertiary (LOW confidence)
- pg_cron local availability -- needs validation during implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already installed and in use
- Architecture: HIGH -- patterns directly derived from existing codebase (RLS, triggers, middleware)
- Auth UI redesign: HIGH -- dark tokens exist, split layout is a CSS change
- Database schema: HIGH -- follows established migration patterns exactly
- Onboarding gate: HIGH -- server component redirect is a proven Next.js pattern
- pg_cron local dev: LOW -- needs testing during implementation
- Pitfalls: MEDIUM -- based on common patterns and Supabase community reports

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (stable stack, no fast-moving dependencies)
