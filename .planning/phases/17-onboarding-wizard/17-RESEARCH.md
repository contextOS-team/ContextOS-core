# Phase 17: Onboarding Wizard - Research

**Researched:** 2026-03-04
**Domain:** Multi-step wizard UI with OAuth integration flows, database-backed state persistence
**Confidence:** HIGH

## Summary

Phase 17 replaces the Phase 16 placeholder at `/onboarding/page.tsx` with a 4-step guided wizard: workspace naming, Linear connection (required), optional source connections (Slack, GitHub, Notion, Fathom), and first context page generation. The entire codebase foundation is already in place -- database schema (`user_onboarding_state` with `current_step` 1-4), auth guards, OAuth connect handlers, brand logos, CSS animations, and the design token system.

The primary technical challenge is **OAuth redirect handling during onboarding**. All backend OAuth callbacks currently redirect to `/dashboard` (or `/dashboard/integrations` for GitHub), which triggers the dashboard layout's onboarding gate redirect to `/onboarding?from=dashboard`. This two-hop redirect works but loses the query parameters that indicate connection success (e.g., `?linear=connected`). The wizard must detect newly connected integrations by querying `getIntegrationStatus()` on mount rather than relying on URL parameters. This is actually cleaner -- the wizard checks real state from the database.

**Primary recommendation:** Build the wizard as a single client component with a step state machine driven by `current_step` from the database. Each step completion writes to the DB via Supabase client before advancing the UI. OAuth returns trigger a re-mount that reads DB state and integration status to determine which step to show and which integrations are connected.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Progress indicator:** Minimal dot stepper -- 4 dots (filled teal for completed, teal ring for active, muted outline for upcoming). No labels in indicator; step title/description in content area. Positioned above step content inside centered card.
- **Layout:** Full-width centered card on bg-background (L1), card uses bg-card (L2) with subtle border. ContextOS wordmark above card. Max-width ~480px. `dashboard-grain` on background.
- **Step transitions:** Crossfade CSS-only, opacity 1->0 / 0->1, ~200ms using `cubic-bezier(0.34, 1.56, 0.64, 1)`. NOT horizontal slide. No Framer Motion.
- **Navigation:** Back button on steps 2-4 (subtle text link). Forward: teal primary button with step-specific labels. Button disabled when requirements unmet.
- **OAuth UX (Steps 2 & 3):** Full-page redirect, NOT popup. Reuse existing connect handlers from `@/lib/api`. After return: wizard reads current_step from DB, detects connected integration, shows success.
- **Success confirmation (ONB-08):** CSS spring scale-in checkmark. Teal circle with white checkmark scales from 0->1 using `animate-scale-in`. Replaces "Connect" button position. After ~800ms auto-advance. No Lottie, CSS-only.
- **Step 3 optional sources:** 2x2 grid (Slack, GitHub, Notion, Fathom). Connected sources show teal checkmark overlay. "Skip" (ghost) and "Continue" (primary) buttons. Skip must be prominent and guilt-free.
- **Step 4 first context page:** Attempt real generation; fallback to realistic sample/mock. Shimmer skeleton with rotating progress text during generation (~10-30s). Uses `skeleton-shimmer` class.
- **Completion flow:** "You're all set!" heading + description + "Go to Dashboard" teal button. Sets `completed_at`, redirects to /dashboard. NOT auto-redirect.
- **State persistence:** Database-only via `user_onboarding_state.current_step`. No cookie, no localStorage. OAuth redirect returns to /onboarding, wizard reads step from DB.

### Claude's Discretion
- Exact card dimensions, padding, and border radius
- Step title and description copy for each of the 4 steps
- Back button positioning (top-left text link vs bottom-left below actions)
- Progress message rotation timing during step 4 generation
- Sample/mock context page content and structure for fallback
- Error handling UX for failed OAuth connections (toast, inline error, retry)
- Workspace name input validation rules (min/max length, character restrictions)
- Whether step 4 shows full 5-section context page or condensed preview
- FathomConnect inline form handling (API key, not OAuth) -- reuse existing component or simplify

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ONB-01 | User sees a 4-step onboarding wizard after first signup before accessing dashboard | Wizard component replaces Phase 16 placeholder at `/onboarding/page.tsx`. Layout auth guard and dashboard onboarding gate already in place. |
| ONB-02 | Step 1: user names their workspace (single text input) | Workspace name update requires new Supabase client call (direct `update` on `workspaces` table) or new backend endpoint. Current `handle_new_user` auto-creates with email prefix name. |
| ONB-03 | Step 2: user connects Linear (required, cannot proceed without) | `connectLinear()` from `@/lib/api` returns `{authorization_url}`. `getIntegrationStatus()` checks connection status on mount. Backend callback redirects to `/dashboard` which gate-redirects back to `/onboarding`. |
| ONB-04 | Step 3: user optionally connects additional sources (Slack, GitHub, Notion, Fathom) | All connect functions exist in `@/lib/api`. Brand logos in `@/components/icons/brand-logos`. FathomConnect component exists for API key flow. GitHub uses `{installation_url}` not `{authorization_url}`. |
| ONB-05 | Step 4: first generated context page with mock fallback | `generateContextPage()` and `getContextPage()` exist in `@/lib/api`. Need sample/mock data for fallback when pipeline unavailable. |
| ONB-06 | OAuth redirect preserves wizard state via database (user returns to correct step) | `user_onboarding_state.current_step` persists across redirects. Wizard reads from DB on mount. Dashboard gate redirects incomplete users back to `/onboarding`. |
| ONB-08 | Animated checkmark confirmation when integration connects successfully | `animate-scale-in` CSS class exists in `globals.css` with spring curve. Build checkmark icon + teal circle, apply class on mount. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | 15 (App Router) | Page routing, server components | Already in use |
| React | 19 | UI components | Already in use |
| Supabase JS | @supabase/supabase-js | DB reads (onboarding state), auth | Already configured with client/server helpers |
| Tailwind CSS | v4 | Styling with OKLCH tokens | Already in use with dark mode variant |
| shadcn/ui | latest | Button, Input, Label components | Already installed |
| sonner | latest | Toast notifications | Already configured |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | latest | Check icon for success confirmation | Already installed, use for checkmark SVG |

### Alternatives Considered
None -- all decisions are locked. The stack is established from prior phases.

## Architecture Patterns

### Recommended Project Structure
```
apps/web/src/app/onboarding/
  layout.tsx          # Existing auth guard (keep as-is)
  page.tsx            # Replace placeholder with wizard orchestrator

apps/web/src/components/onboarding/
  onboarding-wizard.tsx    # Main wizard state machine (client component)
  step-indicator.tsx       # 4-dot progress indicator
  step-workspace.tsx       # Step 1: workspace name input
  step-linear.tsx          # Step 2: connect Linear (required)
  step-sources.tsx         # Step 3: optional sources grid
  step-context.tsx         # Step 4: first context page
  success-checkmark.tsx    # Animated checkmark confirmation
  source-card.tsx          # Individual source card for step 3 grid
```

### Pattern 1: Wizard State Machine
**What:** Single parent component manages step state, loads initial step from DB, advances on completion.
**When to use:** Multi-step flows with persistence requirements.
**Example:**
```typescript
// onboarding-wizard.tsx
'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { getIntegrationStatus, type IntegrationStatusResponse } from '@/lib/api'

type WizardStep = 1 | 2 | 3 | 4
type WizardState = 'loading' | 'active' | 'completing'

export function OnboardingWizard() {
  const [step, setStep] = useState<WizardStep>(1)
  const [state, setState] = useState<WizardState>('loading')
  const [integrations, setIntegrations] = useState<IntegrationStatusResponse | null>(null)

  // Load current step from DB on mount (handles OAuth returns)
  useEffect(() => {
    async function loadState() {
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return

      const { data } = await supabase
        .from('user_onboarding_state')
        .select('current_step')
        .eq('user_id', user.id)
        .single()

      if (data) setStep(data.current_step as WizardStep)

      // Also check integration status (for steps 2 & 3)
      try {
        const status = await getIntegrationStatus()
        setIntegrations(status)
      } catch {
        // Integration check failed -- not blocking
      }

      setState('active')
    }
    loadState()
  }, [])

  async function advanceStep() {
    const nextStep = Math.min(step + 1, 4) as WizardStep
    const supabase = createClient()
    const { data: { user } } = await supabase.auth.getUser()
    if (!user) return

    await supabase
      .from('user_onboarding_state')
      .update({ current_step: nextStep })
      .eq('user_id', user.id)

    setStep(nextStep)
  }

  // ... render steps with crossfade
}
```

### Pattern 2: CSS Crossfade Transition
**What:** Opacity-based step transitions without JavaScript animation libraries.
**When to use:** Step changes in the wizard.
**Example:**
```css
/* In globals.css or component-level */
.step-enter {
  opacity: 0;
  transition: opacity 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
.step-active {
  opacity: 1;
  transition: opacity 200ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
```
Alternative approach: use a key-based re-render with the existing `animate-fade-in-up` class on each step container. When `step` changes, the new step component mounts with the animation class applied.

### Pattern 3: OAuth Return Detection
**What:** After OAuth redirect, wizard detects newly connected integrations by comparing DB step with integration status.
**When to use:** Steps 2 and 3 after OAuth callback redirect chain.
**Example:**
```typescript
// On wizard mount, if current_step is 2 and Linear is connected:
// Show success checkmark for ~800ms, then auto-advance to step 3
useEffect(() => {
  if (step === 2 && integrations?.linear.status === 'connected') {
    setShowSuccess(true)
    const timer = setTimeout(() => {
      setShowSuccess(false)
      advanceStep()
    }, 800)
    return () => clearTimeout(timer)
  }
}, [step, integrations])
```

### Anti-Patterns to Avoid
- **localStorage/cookie state:** The decision explicitly says database-only. Do not duplicate state.
- **Popup OAuth windows:** Locked decision says full-page redirect only.
- **Framer Motion:** Phase 15 zero-bundle decision. CSS-only animations.
- **Reading URL params for OAuth success:** Backend callbacks redirect to `/dashboard`, not `/onboarding`. Query params are lost in the dashboard gate redirect. Always use `getIntegrationStatus()` as source of truth.
- **Blocking on integration status fetch:** Load step from DB first (fast), then fetch integration status in parallel. Show the step UI optimistically.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth connect flows | Custom OAuth handlers | `connectLinear()`, `connectSlack()`, `connectGithub()`, `connectNotion()` from `@/lib/api` | Already handle token, redirect URL generation, error states |
| Integration status checks | Custom DB queries | `getIntegrationStatus()` from `@/lib/api` | Returns all providers in one call with typed response |
| Fathom API key form | New form component | Existing `FathomConnect` component or simplified version | Already has validation, loading, error states |
| Loading skeletons | Custom shimmer | `skeleton-shimmer` CSS class + `Skeleton` component | Already matches design system |
| Spring animations | JS animation logic | `animate-scale-in`, `animate-fade-in-up`, `spring-in` CSS classes | Already defined in globals.css with correct curve |
| Toast notifications | Custom notification UI | `sonner` toast | Already configured project-wide |
| Auth guard on /onboarding | Custom auth check | Existing `onboarding/layout.tsx` server component | Already redirects unauthenticated users to /login |

## Common Pitfalls

### Pitfall 1: OAuth Callback Redirect Chain
**What goes wrong:** OAuth callbacks (Linear, Slack, GitHub, Notion) redirect to `/dashboard` or `/dashboard/integrations`, not `/onboarding`. The dashboard layout gate then redirects to `/onboarding?from=dashboard`. This two-hop works but the `?linear=connected` query parameter is lost.
**Why it happens:** Backend callbacks were built for the dashboard integrations page, not the onboarding wizard.
**How to avoid:** Do NOT rely on URL query parameters to detect OAuth success. Instead, call `getIntegrationStatus()` on wizard mount and check provider status. If current_step is on step 2 and Linear is connected, show the success animation.
**Warning signs:** Wizard shows "Connect Linear" button even after successful OAuth flow.

### Pitfall 2: GitHub Uses installation_url Not authorization_url
**What goes wrong:** Calling `connectGithub()` returns `{ installation_url: string }`, not `{ authorization_url: string }` like the other providers.
**Why it happens:** GitHub Apps use an installation flow, not standard OAuth.
**How to avoid:** Handle both response shapes. For GitHub, redirect to `installation_url`. For others, redirect to `authorization_url`.
**Warning signs:** TypeScript type errors or runtime undefined when accessing the wrong property.

### Pitfall 3: Step Advancement Race Condition
**What goes wrong:** User clicks "Continue" rapidly, causing multiple DB updates that skip steps.
**Why it happens:** Async DB update hasn't completed before next click fires.
**How to avoid:** Disable the forward button during the DB update (loading state). Use a transitioning/loading flag.
**Warning signs:** Steps 2 or 3 are skipped entirely.

### Pitfall 4: Workspace Name Update Has No Backend Endpoint
**What goes wrong:** Step 1 needs to save the workspace name, but there's no PATCH/PUT endpoint for workspaces in the backend. Only `GET /api/workspaces/current` exists.
**Why it happens:** Workspace name editing was deferred to Phase 20 (SET-02).
**How to avoid:** Use Supabase client directly to update the `workspaces` table. The user is the workspace owner (created by `handle_new_user` trigger), and RLS should allow updates via workspace_members policy. Verify RLS allows this, or add a policy if needed.
**Warning signs:** 403/RLS error when trying to save workspace name.

### Pitfall 5: Fathom Is Not OAuth
**What goes wrong:** Treating Fathom like the OAuth integrations (redirect flow) when it actually uses an API key form.
**Why it happens:** Step 3 shows 4 sources in a grid; easy to assume they all work the same way.
**How to avoid:** Fathom card should open an inline API key form (like the existing `FathomConnect` component) instead of triggering a redirect. Show a dialog/expanded card with the key input.
**Warning signs:** Clicking Fathom tries to redirect to a non-existent OAuth URL.

### Pitfall 6: Supabase RLS on user_onboarding_state
**What goes wrong:** Direct Supabase client updates to `user_onboarding_state` fail silently or with auth errors.
**Why it happens:** RLS policy `own_onboarding` uses `auth.uid()` which requires an active Supabase session.
**How to avoid:** Ensure the Supabase client has a valid session before writing. The client-side `createClient()` should handle this via cookie-based auth. Test that `update()` actually works from the browser.
**Warning signs:** Step advancement appears to work in UI but doesn't persist across refresh.

## Code Examples

### Dot Step Indicator
```typescript
// step-indicator.tsx
interface StepIndicatorProps {
  currentStep: number
  totalSteps: number
}

export function StepIndicator({ currentStep, totalSteps }: StepIndicatorProps) {
  return (
    <div className="flex items-center gap-2">
      {Array.from({ length: totalSteps }, (_, i) => {
        const step = i + 1
        const isCompleted = step < currentStep
        const isActive = step === currentStep

        return (
          <div
            key={step}
            className={`h-2 w-2 rounded-full transition-colors duration-200 ${
              isCompleted
                ? 'bg-primary'                    // filled teal
                : isActive
                ? 'ring-2 ring-primary bg-transparent' // teal ring
                : 'bg-muted-foreground/30'        // muted outline
            }`}
          />
        )
      })}
    </div>
  )
}
```

### Success Checkmark Animation
```typescript
// success-checkmark.tsx
import { Check } from 'lucide-react'

export function SuccessCheckmark() {
  return (
    <div className="flex items-center justify-center">
      <div className="animate-scale-in flex h-12 w-12 items-center justify-center rounded-full bg-primary">
        <Check className="h-6 w-6 text-primary-foreground" strokeWidth={3} />
      </div>
    </div>
  )
}
```

### Source Card for Step 3
```typescript
// source-card.tsx
interface SourceCardProps {
  name: string
  logo: React.ReactNode
  connected: boolean
  onClick: () => void
  disabled?: boolean
}

export function SourceCard({ name, logo, connected, onClick, disabled }: SourceCardProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || connected}
      className={`
        relative flex flex-col items-center justify-center gap-2 rounded-lg border p-4
        transition-colors duration-150
        ${connected
          ? 'border-primary/30 bg-primary/5'
          : 'border-border hover:border-primary/50 hover:bg-card'
        }
        disabled:cursor-default
      `}
    >
      <div className="h-8 w-8 text-foreground">{logo}</div>
      <span className="text-sm font-medium">{name}</span>
      {connected && (
        <div className="animate-scale-in absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-primary">
          <Check className="h-3 w-3 text-primary-foreground" strokeWidth={3} />
        </div>
      )}
    </button>
  )
}
```

### Workspace Name Update via Supabase
```typescript
// Step 1: Save workspace name directly via Supabase client
async function saveWorkspaceName(name: string) {
  const supabase = createClient()
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) throw new Error('Not authenticated')

  // Get user's workspace via workspace_members
  const { data: membership } = await supabase
    .from('workspace_members')
    .select('workspace_id')
    .eq('user_id', user.id)
    .single()

  if (!membership) throw new Error('No workspace found')

  const { error } = await supabase
    .from('workspaces')
    .update({ name })
    .eq('id', membership.workspace_id)

  if (error) throw new Error(`Failed to update workspace name: ${error.message}`)
}
```

### Context Page Generation with Fallback (Step 4)
```typescript
// step-context.tsx - generation with mock fallback
const PROGRESS_MESSAGES = [
  'Pulling your tickets...',
  'Analyzing context...',
  'Gathering related discussions...',
  'Generating prompt...',
]

async function attemptGeneration(): Promise<ContextPageData | null> {
  try {
    // Get user's Linear tickets to find one to generate
    const status = await getIntegrationStatus()
    if (status.linear.status !== 'connected') return null

    // Trigger generation for a ticket (need to find an assigned ticket first)
    // This may fail if no tickets exist or pipeline is unavailable
    const result = await generateContextPage('SOME_TICKET_ID')
    if (result.status === 'ok') {
      // Poll or wait for generation to complete
      const page = await getContextPage(result.ticket_identifier)
      return page
    }
    return null
  } catch {
    return null // Fall back to mock
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Cookie/localStorage wizard state | Database-backed `current_step` column | Phase 16 (this project) | Survives browser close, no client-side sync issues |
| Framer Motion animations | CSS-only with cubic-bezier spring curve | Phase 15 decision | Zero additional bundle size |
| Popup OAuth windows | Full-page redirect + DB state resume | Architecture decision | Works on all browsers, no postMessage complexity |

## Open Questions

1. **Workspace RLS for name update**
   - What we know: `handle_new_user` creates the workspace and assigns owner role. The `workspaces` table has RLS enabled.
   - What's unclear: Whether existing RLS policies allow a workspace member/owner to UPDATE the `workspaces` table directly from the client. May need to verify or add a policy.
   - Recommendation: Test the Supabase client update call. If RLS blocks it, add an RLS policy `workspace_owner_update` or use the backend API instead.

2. **Step 4 ticket discovery**
   - What we know: `generateContextPage()` requires a specific ticket identifier. The wizard needs to find an appropriate ticket to generate.
   - What's unclear: Whether there's an endpoint to list the user's assigned Linear tickets that could be used as the generation target.
   - Recommendation: Check if the Linear sync has completed by this point. If tickets exist, use the first assigned one. If not, show the mock fallback immediately rather than waiting.

3. **GitHub callback redirect destination**
   - What we know: GitHub callback redirects to `/dashboard/integrations?github=connected`, not `/dashboard?github=connected` like the others.
   - What's unclear: Whether the dashboard gate catches this route and redirects to `/onboarding`.
   - Recommendation: Verify that `/dashboard/integrations` is caught by the dashboard layout's onboarding gate (it should be, since it's under `/dashboard/`). The two-hop redirect will still work.

## Sources

### Primary (HIGH confidence)
- **Codebase inspection:** Direct reading of all referenced files (`api.ts`, `globals.css`, `brand-logos.tsx`, `fathom-connect.tsx`, migration SQL, OAuth callback routes, dashboard layout, onboarding page/layout)
- **`user_onboarding_state` schema:** `supabase/migrations/00012_onboarding_and_activity.sql` -- confirms `current_step INTEGER CHECK (1-4)`, `completed_at TIMESTAMPTZ`, RLS policy `own_onboarding`
- **OAuth callback routes:** All 4 backend routers (`linear.py`, `slack.py`, `github.py`, `notion.py`) -- confirmed redirect destinations

### Secondary (MEDIUM confidence)
- Architecture patterns derived from existing codebase conventions (client component patterns, Supabase client usage, CSS animation approach)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries already in use, no new dependencies needed
- Architecture: HIGH - patterns derived from existing codebase, all integration points verified
- Pitfalls: HIGH - identified through direct code inspection (OAuth redirect chain, GitHub API difference, missing workspace update endpoint)

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (stable -- internal project with locked dependencies)
