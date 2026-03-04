# Pitfalls Research

**Domain:** Dashboard redesign, onboarding flow, dark theme design system — adding to existing ContextOS app
**Researched:** 2026-03-04
**Confidence:** HIGH (verified across official docs, GitHub issues, community post-mortems, direct codebase inspection)

---

## Critical Pitfalls

Mistakes that cause rewrites, FOUC in production, or permanent "AI slop" impressions.

### Pitfall 1: White Flash on Dark Dashboard (FOUC at Route Transition)

**What goes wrong:**
The dashboard layout uses `bg-background` which resolves to `oklch(0.985 0.002 260)` — a near-white. When the user navigates from the landing page (hard dark background: `#0A0A0F`) to `/dashboard`, there is a visible white flash as the new layout renders before CSS applies. This is compounded if `next-themes` or any theme toggling is introduced: Next.js SSR renders the default light `:root` variables before the client can apply a `.dark` class, causing a flash on every hard-navigation.

**Why it happens:**
The root `<html>` element has no `dark` class. The landing page works around this by injecting `<style>{html, body { background-color: #0A0A0F !important; }}</style>` directly into the landing layout — a hack that only covers the landing segment. When the dashboard layout mounts with `bg-background` (which resolves to light mode white), the browser paints that background instantly before JavaScript runs. No `ThemeProvider` or `suppressHydrationWarning` is in place.

**How to avoid:**
Apply the `dark` class at the dashboard layout level, not globally. The existing `globals.css` already has a `.dark` block with correct OKLCH dark tokens — use it. In the dashboard layout wrapper, add `className="dark"` to the outer `<div>`. This forces Tailwind's `dark:` variant to activate for all descendants without touching the root `<html>` (which would break the landing page). The correct pattern:

```tsx
// app/dashboard/layout.tsx
return (
  <div className="dark flex flex-col min-h-screen bg-background text-foreground">
    <Sidebar ... />
    <main ...>{children}</main>
  </div>
)
```

Because `globals.css` defines `@custom-variant dark (&:is(.dark *))`, any element inside `.dark` will resolve its OKLCH variables to the dark values. No `next-themes`, no `ThemeProvider`, no `suppressHydrationWarning` needed — the dark theme is structural, not user-preference-driven.

**Warning signs:**
- White background visible for 50-200ms when clicking "Sign In" and landing on `/dashboard`
- Browser devtools paint flashing tool shows a light frame before the dark frame
- Users on slow connections see the white background for 1+ seconds

**Phase to address:**
Dashboard redesign phase — the very first commit that adds the dark class to the layout wrapper. Must be done before any visual polish work begins, because it changes which CSS variables all subsequent components resolve to.

---

### Pitfall 2: The "Dark Mode Template" Trap — Generic shadcn/Tailwind Dark

**What goes wrong:**
The dashboard ends up looking like every other Next.js + shadcn + Tailwind dark mode app: gray-900 background, white text, blue primary accent, card borders in gray-700, skeleton loaders, and an endless grid of cards. The landing page has distinctive character (teal #00D4AA, near-black navy #0A0A0F, grain texture, glow effects). The dashboard shares none of it. Users notice the discontinuity immediately — the landing page looks like a designed product, the dashboard looks like a `npx shadcn@latest init` starting point.

The specific visual fingerprints of "AI slop" dark dashboards:
- Pure gray background (`#111827` or `oklch(0.17 0 0)`) with zero color temperature
- Default blue primary (`#3b82f6`) with no brand connection
- Card components with a 1px border and background 1 step lighter than the page
- Padding and spacing from the shadcn defaults, never questioned
- Status dots as plain colored circles with no surrounding context
- "Connect" buttons that look like plain `<Button variant="outline">`
- No visual hierarchy between primary actions and secondary content
- Empty states that are just centered text with an icon

**Why it happens:**
Developers ship the shadcn defaults and treat visual polish as something to "do later." The defaults are intentionally neutral so they work for everyone — which means they look like everyone else's app. The existing dashboard already uses `bg-card`, `border-border`, `text-muted-foreground` — all correct token names, all resolving to the same neutral gray palette that thousands of apps use.

**How to avoid:**
The dashboard dark theme must be deliberately different from shadcn defaults. Three specific interventions:

1. **Background color temperature**: Instead of the neutral `oklch(0.12 0.015 270)` in `.dark`, shift the dashboard background to have a subtle teal undertone: `oklch(0.10 0.012 210)` (cooler, slightly blue-teal). This one change makes the dashboard feel like it belongs to the ContextOS brand rather than being a shadcn template.

2. **Surface hierarchy with teal influence**: Card backgrounds should be `oklch(0.14 0.014 220)`, borders should have a barely-perceptible teal tint: `oklch(0.25 0.018 210)`. This is imperceptible individually but creates a coherent palette when all surfaces are viewed together.

3. **Accent that matches the landing**: The dashboard primary should be a muted version of the landing's `#00D4AA` — `oklch(0.55 0.12 180)` rather than a generic blue. It reads as the same product family without being as vibrant as the marketing page.

These changes live in a `dashboard-theme` CSS class applied at the dashboard layout level (same scoping pattern as `landing-theme`), overriding only the specific OKLCH tokens that need adjustment.

**Warning signs:**
- Screenshot the dashboard and the landing page side by side — if they look like they're from different products, the pitfall has occurred
- Any component using the default shadcn `primary` color that resolves to the same blue as the shadcn docs
- The dashboard background reads as "dark gray" rather than "near-black with blue-teal undertone"

**Phase to address:**
Dashboard redesign — during the dark theme CSS token definition, before any components are built. Token decisions propagate everywhere; retrofitting them requires touching every component.

---

### Pitfall 3: Onboarding Flow Interrupted by OAuth Redirect — Lost Progress

**What goes wrong:**
The onboarding wizard guides the user through: create workspace → connect Linear → connect Slack → generate first context. The Linear and Slack connection steps redirect the user to external OAuth providers. When the OAuth provider redirects back to `/auth/callback`, the onboarding state (current step, form data, workspace ID) is gone. The user lands back on the dashboard home page instead of returning to onboarding step 3. The onboarding "just stops" mid-flow.

This is a guarantee, not an edge case. Every OAuth connect within onboarding involves a full-page redirect away from and back to the app. The user's browser state is wiped on redirect.

**Why it happens:**
The existing OAuth callback (`/auth/callback`) redirects to `/dashboard` unconditionally. There is no mechanism to preserve onboarding state across the OAuth round-trip. State stored in React `useState` or in-memory is gone when the page unloads for the OAuth redirect. The onboarding wizard has no persistent backing store.

**How to avoid:**
Before redirecting to the OAuth provider, store the onboarding resume point in a cookie or Supabase `profiles` table:

```typescript
// Before: window.location.href = authorization_url
// After:
document.cookie = `onboarding_return=/onboarding?step=3&status=linear_connected; path=/; max-age=600; SameSite=Lax`
window.location.href = authorization_url
```

In the OAuth callback route (`/auth/callback`), read this cookie and redirect to the onboarding resume URL instead of `/dashboard`. Clear the cookie after redirect. The Supabase-based approach (writing `onboarding_step` to `profiles`) is more robust but adds a round-trip; the cookie approach works fine for a short-lived onboarding flow.

**Warning signs:**
- Manual test: start onboarding, click "Connect Linear," complete OAuth, observe where you land
- Any OAuth connect handler that calls `window.location.href = authorization_url` without first preserving state is vulnerable
- The existing `handleQuickConnect` in `dashboard/page.tsx` has this exact vulnerability

**Phase to address:**
Onboarding implementation phase — before any OAuth connect buttons are wired into the wizard. The resume-point preservation must be built into the OAuth initiation helpers, not bolted on afterward.

---

### Pitfall 4: Scoped CSS Bleeding — `.landing-theme` Tokens Leaking into Dashboard

**What goes wrong:**
The landing page uses a scoped `.landing-theme` class to isolate its dark design tokens from the dashboard's light defaults. This works correctly today. When the dashboard switches to dark mode, there is a risk of CSS variable collision if the `dashboard-theme` class shares variable names with `landing-theme`, or if the `landing-theme` styles are accidentally applied to dashboard routes via an ancestor element.

More concretely: the landing layout wraps its children in `<div class="landing-theme landing-grain">`. If any shared layout component (a modal, a portal-based dialog from Radix/shadcn) renders outside this div, it will get the wrong tokens. Radix UI portals render at the `<body>` level by default — outside `.landing-theme` scope — which means dialogs, dropdowns, and tooltips on the landing page get `:root` (light mode) tokens, not `.landing-theme` tokens.

**Why it happens:**
The existing `globals.css` uses `@custom-variant dark (&:is(.dark *))` which expects `.dark` on an ancestor. The landing theme achieves darkness via `.landing-theme` CSS variable overrides, not via `.dark` class. This means shadcn components that use `dark:bg-*` Tailwind variants will NOT activate inside `.landing-theme` — only the CSS variable overrides work. Any shadcn component that uses both approaches (e.g., `dark:text-white bg-background`) will have mixed results.

**How to avoid:**
Establish a strict rule: the dashboard segment uses `.dark` class on the layout wrapper for dark mode. The landing segment uses `.landing-theme` for CSS variable overrides only. No route segment ever uses both mechanisms. Document which CSS variable names are "reserved" by each scope and ensure they never overlap. The `dashboard-theme` class (if created) must only override variables that `.dark` doesn't already set.

For Radix portals in landing components: add `data-vaul-drawer-wrapper` to the `.landing-theme` div so Radix portals are rendered inside it, or add `.landing-theme` class to the portal root manually.

**Warning signs:**
- A shadcn `Dialog` or `DropdownMenu` on the landing page shows with white/light background
- Any CSS variable (`--primary`, `--border`, etc.) rendering differently inside vs. outside a portal
- The dashboard dark theme affects elements on the landing page (or vice versa) after the route transition

**Phase to address:**
Dashboard dark theme phase — as part of defining the scoping strategy before writing any themed components. Run a visual diff test of all landing page components with portals after the dashboard dark class is added.

---

### Pitfall 5: Activity Feed Accumulating Unbounded Supabase Realtime Subscriptions

**What goes wrong:**
The activity timeline subscribes to Supabase Realtime to receive live updates (new context generated, sync completed, etc.). If the subscription is created inside a React `useEffect` without proper cleanup, every component mount creates a new channel. In development with React Strict Mode (which double-invokes effects), this immediately creates two subscriptions per mount. In production, navigating away and back to the activity feed page creates a new subscription each time without removing the old one.

Supabase Free plan allows 200 concurrent connections, 100 channels per connection. For a small founding team (3 users with 2-3 tabs open each), exceeding connection limits is unlikely. But leaking channels silently inflates costs and can cause unexpected "too_many_channels" errors if the browser tab is left open for hours with frequent re-renders.

**Why it happens:**
Developers copy Supabase Realtime examples that show `supabase.channel('activity').on(...)` without a cleanup return. The existing codebase creates a single Supabase client per call (via `createClient()`), which is correct. But channels need explicit removal: `supabase.removeChannel(channel)` must be called in the effect cleanup.

**How to avoid:**
```typescript
useEffect(() => {
  const channel = supabase
    .channel('activity-feed')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'context_jobs' }, handleUpdate)
    .subscribe()

  return () => {
    supabase.removeChannel(channel)
  }
}, [supabase])
```

Create one channel per logical feed, not one channel per item. Use a single subscription with a filter rather than N subscriptions for N items. For the founding team scale (3 users), polling with a 10-second interval is equally valid and simpler than Realtime — prefer simplicity and reach for Realtime only when live updates are a stated requirement.

**Warning signs:**
- Browser devtools WebSocket frames show duplicate identical messages arriving for one event
- Supabase dashboard showing "Peak Connections" far higher than your user count
- React Strict Mode (dev) causing duplicate notifications for single events

**Phase to address:**
Activity timeline phase — the subscription pattern must be correct from the first implementation. Add a cleanup unit test: mount and unmount the timeline component and verify channel count returns to baseline.

---

## Moderate Pitfalls

Mistakes that cause rework, visual bugs, or degraded UX.

### Pitfall 6: Onboarding Step Validation Blocking on Error, Not Guiding Forward

**What goes wrong:**
The onboarding wizard shows an error state when the user skips a step or tries to proceed without completing all fields, but provides no forward path. "Connect Linear to continue" is a dead end if the Linear OAuth app registration is pending. Users who hit an error on step 2 of 5 cannot continue, cannot skip, cannot exit gracefully. They close the browser and never return.

**Why it happens:**
Developers treat onboarding as a form to be validated rather than a guided journey. The instinct is "don't let users through until they've completed this step" — but for integration setup steps that depend on external services, this creates an unresolvable dead end.

**How to avoid:**
Every onboarding step must have an explicit "I'll do this later" escape. Mark skipped steps as `pending` rather than `required`. Design the dashboard to reflect onboarding completion state (the existing "0/5 connected" pattern is exactly right) so users can return to incomplete steps naturally. Only block progression for steps that are truly a prerequisite for the next step (e.g., can't generate context without at least one integration). Linear and Slack connection steps must be skippable.

**Warning signs:**
- Any onboarding step that throws an error with no "Skip" option
- Completion blocking on external OAuth status that the user cannot control in the moment
- No way to exit onboarding and return to it later

**Phase to address:**
Onboarding implementation phase — bake skip logic into the wizard state machine before implementing individual steps.

---

### Pitfall 7: Context Feed Empty State Is a Dead End

**What goes wrong:**
The first time a user reaches the context feed page, it is empty. The empty state shows "No context pages yet" with a description and maybe an icon. The user has no actionable next step. They don't know if they need to connect Linear first, assign a ticket, or wait. They close the tab.

This is the highest drop-off point for internal tools: the first time a user sees the product's core feature and it's... nothing.

**Why it happens:**
Empty states are treated as an afterthought. Developers implement the feed for the case where data exists, add a basic empty state, and ship. The empty state doesn't account for the user's onboarding status (no integrations vs. integrations connected but no tickets assigned yet vs. tickets assigned but generation pending).

**How to avoid:**
The context feed empty state must branch on user state:
- **No integrations connected:** Show "Connect Linear to start generating context" with a direct link to integrations setup
- **Linear connected, no tickets assigned to user:** Show "Assign a Linear ticket to yourself to generate your first context page" with a screenshot/mockup of what a context page looks like
- **Generation in progress:** Show the skeleton loader with a "Generating your first context page..." message
- **Generation complete, no context pages:** Should not happen — redirect bug

Each branch must have a call to action, not just an explanation.

**Warning signs:**
- The empty state is a single message centered on the page with no button
- The empty state text is the same regardless of whether integrations are connected
- There is no loading/generating state shown while the first context page is being produced

**Phase to address:**
Context feed implementation phase — design the empty state variants before implementing the feed, not after.

---

### Pitfall 8: Onboarding Wizard Progress Not Persisted — Users Lose State on Refresh

**What goes wrong:**
The user completes steps 1-3 of a 5-step onboarding wizard, then refreshes the page or closes and reopens the browser. They are back at step 1. All progress is gone. If the wizard required connecting Linear (which involves an OAuth redirect), the integration IS connected, but the wizard shows it as step 2 again.

**Why it happens:**
Onboarding state is stored in React component state (`useState`) without persistence. When the component unmounts (navigation, refresh, tab close), the state is lost.

**How to avoid:**
The `profiles` table already exists (or should be created in the DB schema phase) with a `onboarding_completed_at` column. Add an `onboarding_step` integer column. After each step completion, write the current step number to the database. On page load, read the current step from the database and resume there. The onboarding wizard derives its initial step from the database, not from component state.

The check for which steps are "complete" should be derived from actual data (Linear integration connected? → step 2 complete) rather than from stored step numbers. This makes the wizard resilient to partial state: if the user connected Linear outside of onboarding, the wizard should recognize it and advance past that step.

**Warning signs:**
- Step advancement is stored only in `useState` or `useRef`
- The wizard starts at step 1 even when the user has an integration already connected
- Completing OAuth redirect returns the user to step 1 of onboarding

**Phase to address:**
Onboarding implementation phase, but the `profiles.onboarding_step` column must be added in the DB schema phase.

---

### Pitfall 9: Auth Page Redesign Inherits Wrong Token Set

**What goes wrong:**
The auth pages (`/login`, `/signup`) are redesigned to match the dark brand identity. The developer adds a `dark` class to the auth layout, which activates the `.dark` OKLCH tokens in `globals.css`. Everything looks correct in development. In production, a user with an OS-level dark mode preference who visits `/login` for the first time sees the page flash white (SSR renders `:root` light tokens) before the dark class is applied client-side. Worse: if `next-themes` is ever added globally, the auth pages toggle with the user's system preference rather than being locked to the brand's dark identity.

**Why it happens:**
Auth pages that are "dark by design" (not user-preference-driven) must use the structural `.dark` class approach, not the `next-themes` ThemeProvider approach. Mixing the two causes the FOUC issue above and makes the auth page's dark theme contingent on user preference rather than brand identity.

**How to avoid:**
The auth layout wrapper must include `dark` as a static CSS class, identical to the dashboard layout approach. Do not use `ThemeProvider` or `next-themes` for the auth pages. The `<style>{html, body { background-color: ... }}` hack used by the landing layout works here too — add it to the auth layout to prevent the white flash between the `<html>` background (light) and the `.dark` div background (near-black) while the page loads.

**Warning signs:**
- The auth page background is white for 50-200ms on first load
- The "or" divider in the login form uses `bg-card` which resolves to a light color inside a dark context
- Input placeholders have poor contrast against the dark input background

**Phase to address:**
Auth page redesign phase — the very first step is establishing the dark wrapper with the background flash prevention, then building the styled components on top of that.

---

### Pitfall 10: Activity Timeline N+1 Query for Actor/Resource Details

**What goes wrong:**
The activity timeline shows events like "Linear synced 12 tickets" and "Context generated for CON-45." Each event record in the database stores a `resource_id` (ticket ID, integration ID, etc.) but not the display name. When rendering the timeline, the frontend makes one query to fetch 20 events, then 20 individual queries to fetch the display name for each event's resource. The timeline loads slowly because of 21 sequential or 21 parallel database calls.

**Why it happens:**
Activity events are a log — the schema captures the event type, actor, resource ID, and timestamp. Denormalizing the display name into the event record feels wrong ("what if the ticket title changes?"). So the display name is fetched lazily, per-event, at render time.

**How to avoid:**
Two acceptable approaches depending on how important the display name accuracy is:

1. **Denormalize at write time**: When writing an activity event, also write the display name (ticket title, integration name) at that moment. Accept that historical events show the name as it was when the event occurred. This is correct behavior for an audit log — "Context generated for 'Implement rate limiting'" is more informative than "Context generated for CON-45."

2. **Join at query time**: Write a single SQL query that JOINs activity events with the relevant resource tables. One database round-trip for the entire page. This requires knowing at schema design time which resource types exist and defining the JOIN structure.

Option 1 is strongly preferred: simpler query, resilient to resource deletion, historically accurate.

**Warning signs:**
- The activity timeline loads the event list, then you see individual items appearing one by one as their resource details load
- Supabase dashboard shows 15-25 queries fired in sequence when the timeline page loads
- Any `useEffect` that iterates over events and makes a fetch call per event

**Phase to address:**
Activity timeline phase, but the schema decision (denormalize vs. join) must be made in the DB schema phase and communicated to whoever designs the activity events table.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using inline `style` overrides for dark theme instead of CSS variables | Quick visual fix | Bypasses the token system; every change requires finding and updating hardcoded values scattered across files | Never — use the `.dark` class + token overrides |
| Using `dark:bg-gray-800` Tailwind classes instead of `dark:bg-card` | Predictable color control | Creates a parallel color system that diverges from tokens; future token changes don't propagate | Never in ContextOS — shadcn components use semantic tokens, mixing in raw Tailwind color breaks the consistency |
| Putting all onboarding steps on one page (no step persistence) | Simpler to implement | Users who get interrupted (OAuth redirect, browser close) lose all progress | Only for truly trivial onboarding (1-2 steps, no OAuth) |
| Fetching activity events on a 5-second polling interval instead of Realtime | No WebSocket complexity | 5-second staleness on a "real-time" timeline; high read traffic on activity table at scale | Acceptable for founding team (3 users) as a starting point, replace with Realtime before external launch |
| Hardcoding the landing page's `#00D4AA` teal as a Tailwind `text-[#00D4AA]` in dashboard components | Matches brand color exactly | Not a CSS variable; if the brand color changes, it must be updated in every component where it's used | Never — add `--color-teal` to the dashboard-theme block |
| Using `<style>` inline hack to prevent flash (`html, body { background: #0A0A0F !important; }`) | Works immediately | The `!important` can override legitimate subsequent styles; it's a sledgehammer approach | Acceptable only as a flash-prevention shim in the layout file while a proper solution is built |

---

## Integration Gotchas

Common mistakes when the new features connect to existing systems.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Dark dashboard + existing landing CSS | Adding `.dark` class at `<html>` level to force dark dashboard — breaks landing page which relies on `:root` light variables | Apply `.dark` only to the dashboard layout `<div>`, not `<html>`. Landing uses `.landing-theme` scoping, never `.dark` class |
| OAuth connect inside onboarding wizard | Calling the existing `connectLinear()` / `connectSlack()` API helpers directly, which redirect immediately with no state preservation | Wrap every OAuth initiation in the wizard with a pre-redirect cookie write: `onboarding_return=/onboarding?step=N` |
| Supabase Realtime + Next.js client components | Creating a new Supabase client instance inside every component that needs Realtime | Use the shared `createClient()` from `@/lib/supabase/client` and ensure `removeChannel()` is called in effect cleanup |
| Activity events table + RLS | The activity events table visible to all workspace members but the current RLS pattern protects per-user — activity feed needs workspace-scoped reads | Design the `activity_events` RLS policy to filter by `workspace_id` (not `user_id`) from the start. Review existing RLS pattern before creating the table |
| Dark auth pages + existing auth callback | Auth callback route (`/auth/callback`) redirects to `/dashboard` — once onboarding exists, this redirect must check onboarding completion status | Add an `onboarding_completed_at` check in the callback: if null, redirect to `/onboarding`; otherwise `/dashboard` |
| shadcn `Dialog` / `Sheet` in dark dashboard | Radix portals render outside the `.dark` wrapper div, so they get `:root` light tokens | Wrap the entire `<body>` or add `dark` class at the `<html>` level only for authenticated routes — or add `className="dark"` to the portal root via `Radix.Portal` container prop |

---

## Performance Traps

Patterns that work fine for 3 users but degrade with real usage.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Polling the activity events table without a WHERE clause timestamp filter | Full table scan every 5 seconds per open tab | Always filter: `WHERE created_at > last_fetch_timestamp`. Add a compound index on `(workspace_id, created_at DESC)` | 1,000+ activity events |
| Rendering all activity events without virtualization | Timeline page freezes when scrolling after 200+ events are loaded | Use `@tanstack/react-virtual` or implement infinite scroll with `pageParam`. Never render unbounded lists | 200+ timeline events in DOM |
| Supabase Realtime broadcasting activity events to all subscribers without workspace filtering | Users in workspace A receive events for workspace B; auth bypass risk | Filter Realtime channel by `workspace_id`: `.on('postgres_changes', { filter: 'workspace_id=eq.YOUR_ID' }, ...)` | Multiple workspaces |
| Onboarding wizard fetching all integration statuses on every step render | 5 API calls per wizard step transition | Fetch integration status once on wizard mount, cache in state. Re-fetch only after an OAuth connect completes | Onboarding with slow mobile connection |
| CSS animation `animate-fade-in-up` on every context feed card re-render | Feed flickers/re-animates when new events arrive via Realtime | Apply entry animation only on initial mount (CSS `animation-fill-mode: both`) and suppress it for items that are updated in-place | Any Realtime update to existing items |

---

## Security Mistakes

Domain-specific issues for this milestone.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Exposing onboarding step state in the URL only (`?step=3`) | User can manually jump to step 5 without completing prerequisites, claiming "onboarding complete" without connecting integrations | Validate step completion server-side when marking onboarding complete. URL step is a UI hint, not a trust boundary |
| Activity events table without workspace isolation in RLS | User A can query user B's activity events if they craft a direct Supabase query | Mandatory RLS policy: `workspace_id = (SELECT workspace_id FROM profiles WHERE user_id = (SELECT auth.uid()))`. Never rely on the frontend to filter |
| OAuth state cookie with long TTL | An `onboarding_return` cookie that lives for 24 hours allows replaying the OAuth flow out of context | Set TTL to 10 minutes max. Validate that the return URL matches an allowed onboarding path (whitelist, not regex) |

---

## UX Pitfalls

Common user experience mistakes for these specific features.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Onboarding wizard with a progress bar that fills but then jumps back | User feels they are going backward; trust in the product erodes | Progress bar must be monotonically increasing. If a step can't be completed, it shows as "pending" (grayed out check) not as negative progress |
| Dark dashboard with insufficient contrast between surface levels | Eye fatigue in daily use; users cannot distinguish cards from the page background | Minimum 8% lightness difference between background and card in OKLCH: background `oklch(0.10)`, card `oklch(0.14)` is sufficient; background `oklch(0.12)`, card `oklch(0.13)` is not |
| Activity timeline showing raw event types ("context_generated") instead of human-readable descriptions | Feed is unreadable without understanding the internal event schema | Define a display name mapping for every event type at the application layer before writing the feed component |
| Onboarding showing "Connect X" buttons without explaining why | Users don't understand what they get from each integration | Each integration in onboarding shows one sentence: what data it provides and what it enables (e.g., "Linear — we pull ticket descriptions, comments, and history to generate context") |
| Auth page redesign with dark inputs that show no focus ring | Users who tab through the form lose keyboard navigation position | Ensure `ring` CSS variable has sufficient contrast in dark mode. The existing `--ring: oklch(0.60 0.18 250)` is adequate — verify it's not overridden |
| Activity feed with only "what happened" and no "what to do" | Engineers know 3 context pages were generated but don't know what to do with them | Each activity item should link directly to the resource it describes (context page, integration settings, etc.) |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Dark dashboard theme:** Add the `.dark` class to the layout wrapper AND verify that all shadcn components (Dialog, Sheet, DropdownMenu portals) render with dark tokens. Open a Dropdown from the dashboard and check the background color in devtools.
- [ ] **Onboarding OAuth flow:** Complete the OAuth round-trip within the wizard (not from the dashboard page) for BOTH Linear and Slack. Verify you land back on the correct onboarding step, not the dashboard home.
- [ ] **Flash prevention:** Navigate from the landing page to `/login` to `/dashboard` and check for any white frames using browser paint timing in devtools. Background should stay dark throughout.
- [ ] **Activity feed empty states:** Test all three empty state branches: (1) no integrations, (2) integrations connected but nothing generated, (3) generation in progress. All three must have a call-to-action.
- [ ] **Onboarding persistence:** Start onboarding, complete step 1, close the browser entirely, reopen — verify you resume at step 2 (or wherever you left off).
- [ ] **Supabase Realtime cleanup:** Navigate to the activity feed, then navigate away, then back. Open Supabase Realtime metrics — verify channel count is 1, not 2.
- [ ] **Context feed with real data:** Add the `.dark` class and verify all card content (timestamps, status dots, truncated text) has sufficient contrast. Run Chrome's accessibility checker with dark mode active.
- [ ] **Auth pages with dark class:** Test magic link flow end-to-end in dark auth. The email redirect back to `/auth/callback` must still work — the `dark` class on the auth layout does not affect the redirect URL.
- [ ] **Design system token consistency:** Do a text search for hardcoded hex values (`#00D4AA`, `#0A0A0F`, etc.) in dashboard and auth components. Every brand color should be a CSS variable reference.
- [ ] **Activity feed performance:** Load the timeline with 100+ seeded events. Check that only the visible events are in the DOM (windowed) or that pagination limits the DOM count. Check database query count in Supabase logs.

---

## Recovery Strategies

When pitfalls occur despite prevention.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| FOUC on dark dashboard | LOW | Add `dark` class to dashboard layout wrapper and `<style>` flash-prevention shim. One commit. |
| Generic dark theme ("AI slop") already shipped | MEDIUM | Create `dashboard-theme` CSS class with brand-tinted token overrides. Apply at layout level. Verify in browser. Typically 1-2 days of design iteration. |
| Onboarding OAuth redirect lost state | LOW | Add pre-redirect cookie write and callback route check. 2-3 hours. No schema changes needed. |
| Activity feed with N+1 query already shipped | MEDIUM | Migrate activity events table to store denormalized display names. Write a backfill migration. Update the event-write code. Schema change + data migration. |
| `.landing-theme` leaking into dashboard via shared ancestor | LOW | Inspect the DOM tree. The leakage is always an ancestor element that has both classes. Remove the `.landing-theme` class from any element outside `(landing)` route segment. |
| Onboarding step state lost on refresh (no persistence) | MEDIUM | Add `onboarding_step` column to `profiles` table. Write step number to DB on each advance. Read on wizard mount. Requires migration + logic rewrite. |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| FOUC white flash on dark dashboard | Dashboard redesign — first commit | Navigate landing → login → dashboard. No white frame visible. |
| Generic "AI slop" dark theme | Dashboard redesign — token definition step | Side-by-side screenshot test: dashboard vs. landing page. Same product family. |
| OAuth redirect destroying onboarding state | Onboarding implementation — before OAuth buttons are wired | Complete Linear OAuth within the wizard, verify return to correct step. |
| Landing CSS / Dashboard CSS scoping collision | Dashboard redesign — dark class strategy | Open all shadcn portals (Dialog, Dropdown) on both landing and dashboard. Correct tokens on both. |
| Realtime subscription leak | Activity timeline implementation | Mount/unmount activity feed component 3 times. Supabase channel count stays at 1. |
| Onboarding step not persisted | Onboarding implementation + DB schema | Refresh mid-onboarding. Resume at correct step. |
| Context feed dead-end empty state | Context feed implementation | Test 3 empty state branches. Each has a CTA. |
| Activity timeline N+1 query | Activity timeline + DB schema | Single query in Supabase logs per timeline page load. |
| Auth page dark theme with FOUC | Auth page redesign — first commit | Load `/login` on cold browser. Background stays dark throughout. |
| Hardcoded brand colors in components | Dashboard redesign — token audit | `grep -r "#00D4AA\|#0A0A0F\|#1C1C2E" apps/web/src/app/dashboard` returns zero results. |

---

## Sources

- Direct inspection of `/apps/web/src/app/globals.css`, `landing.css`, dashboard layout, auth layout, and sidebar — CSS variable scoping, existing OKLCH tokens, `.dark` class absence confirmed (HIGH confidence)
- [next-themes GitHub README](https://github.com/pacocoursey/next-themes) — FOUC cause, `suppressHydrationWarning`, `disableTransitionOnChange` (HIGH confidence)
- [FOUC Fixing in React and Next.js — Not A Number](https://notanumber.in/blog/fixing-react-dark-mode-flickering) — Inline script in `<head>`, hydration timing details (HIGH confidence)
- [shadcn/ui issue #5552 — ThemeProvider hydration error Next.js 15](https://github.com/shadcn-ui/ui/issues/5552) — Confirmed Next.js 15 + ThemeProvider hydration issues (HIGH confidence)
- [shadcn/ui Tailwind v4 docs](https://ui.shadcn.com/docs/tailwind-v4) — `@custom-variant dark (&:is(.dark *))`, OKLCH migration, `tw-animate-css` (HIGH confidence)
- [Supabase Realtime Limits](https://supabase.com/docs/guides/realtime/limits) — 200 connections free, 100 channels per connection (HIGH confidence)
- [Supabase Realtime Best Practices Discussion #21995](https://github.com/orgs/supabase/discussions/21995) — Single client instance, channel cleanup patterns (HIGH confidence)
- [NN/G Wizards: Definition and Design Recommendations](https://www.nngroup.com/articles/wizards/) — Step count, navigation, skip patterns (HIGH confidence)
- [OnboardJS: Supabase Onboarding Persistence](https://onboardjs.com/blog/supabase-onboarding-persistence-onboardjs) — Persistence patterns, state loss on refresh (MEDIUM confidence)
- [Applying Dark Mode in Next.js via CSS Variables — Codimite](https://codimite.ai/blog/applying-dark-mode-in-next-js-using-css-variables/) — Structural dark class approach (MEDIUM confidence)
- [DEV: Understanding & Fixing FOUC in Next.js App Router 2025](https://dev.to/amritapadhy/understanding-fixing-fouc-in-nextjs-app-router-2025-guide-ojk) — Background flash prevention patterns (MEDIUM confidence)
- [TanStack Query Infinite Queries docs](https://tanstack.com/query/latest/docs/framework/react/guides/infinite-queries) — Sequential refetch of all pages, memory management (HIGH confidence)
- [GitHub Discussion: Handling colors light/dark mode shadcn #2151](https://github.com/shadcn-ui/ui/discussions/2151) — CSS variable alias strategy for dark mode (HIGH confidence)

---
*Pitfalls research for: ContextOS v1.1 — dashboard redesign, onboarding flow, dark theme design system*
*Researched: 2026-03-04*
