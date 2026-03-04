# Feature Research

**Domain:** Developer tool dashboard redesign — onboarding, context feed, activity timeline, settings, auth, dark design system
**Researched:** 2026-03-04
**Confidence:** MEDIUM-HIGH

---

## Competitive Reference Analysis

This milestone targets four capability areas. The following products represent state-of-the-art patterns for each:

| Reference Product | Why Relevant |
|-------------------|--------------|
| **Linear** | Sets the bar for developer tool dark UI, minimal onboarding, dense list views, LCH color systems |
| **Vercel** | Best-in-class deployment dashboard: project cards with live previews, tab-state icons, filterable logs |
| **PostHog 3000** | Explicitly redesigned to feel like a dev tool — dark mode, data density, command palette, side panels |
| **Supabase** | Emerald-on-dark brand applied to a dense data tool; activity logs, real-time feeds, settings patterns |
| **Clerk** | Auth page dark mode as of 2025; brand identity in login flow |
| **Raycast** | Dark surfaces with abstract noisy overlays, bold red accent; abstains from generic blue gradients |

---

## What Makes a Dashboard Feel Crafted vs. AI-Generated

This is the central question of the milestone. Evidence from Linear's redesign blog, PostHog's "What if PostHog looked like a dev tool?" and PostHog's engineer design guide, combined with the LogRocket analysis of "Linear design" as a trend, converges on six specific signals.

### The Six Signals

**1. Deliberate surface hierarchy**
Crafted dark UIs use 3-4 distinct surface levels (background → card → elevated card → overlay), all derived from a single base color shifted in lightness — not arbitrary hex values per component. The existing `globals.css` already does this with OKLCH: `background: oklch(0.12)`, `card: oklch(0.17)`, `input: oklch(0.25)`. The gap is inconsistent application — some components bypass the token system. Enforce the token hierarchy strictly.

**2. Typography with one deliberate break**
Generic: Inter everywhere, uniform weight. Crafted: Inter for body + one intentional variation. Linear uses Inter Display for headings. PostHog recommends IBM Plex Sans for "tech-forward" density. The existing stack already loads Inter with JetBrains Mono for code. The move is: use `font-display` / `tracking-tight` / heavier weight on h1-h2, and reserve `font-mono` (JetBrains Mono) for all identifiers — ticket IDs, timestamps, API keys, token counts. This one rule makes a dashboard read like a tool.

**3. Monospace for data, proportional for prose**
Every number that represents system state — ticket identifiers, timestamps, token counts, sync counts, API key prefixes, error codes — should render in JetBrains Mono. Proportional fonts on data values look unintentional; monospace signals the designer knew what the number meant.

**4. Semantic accent color, not decorative**
Generic: teal everywhere for brand. Crafted: teal appears exactly where the system is active, successful, or primary-action. Status dots, connected integration borders (already in the current dashboard code), CTA buttons. Muted/gray for everything else. The ContextOS landing page uses teal extensively; the dashboard should treat teal as a signal, not decoration.

**5. Microinteractions at interaction boundaries**
Linear uses spring-curve animations (`cubic-bezier(0.16, 1, 0.3, 1)`) — the existing codebase already uses this exact curve in `animate-fade-in-up`. The gap is: this animation only fires on page mount. Extend it to list item appearance (stagger), status changes (scale-in), and completion states (checkmark draw). These 3 uses are enough. More than 5 distinct animation contexts reads as over-engineered.

**6. Empty states that show what will be there**
Generic: "No data yet." Crafted: shows a faded/ghost version of what a populated state looks like, with exactly one primary action. Vercel shows a project card with "Deploy your first project." Linear shows a blank issue list with a keyboard shortcut hint. The principle: every empty state teaches the user what success looks like and gives them one unambiguous next step.

---

## Feature Landscape

### Capability 1: Guided Onboarding

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Step-by-step setup flow before dashboard access | Users expect product-gated tools to walk them through prerequisites. Linear, Clerk, Supabase all do this. Shipping users straight to a blank dashboard is a churn event | MEDIUM | Route: `/onboarding` → redirect to `/dashboard` only after all required steps complete. Steps: workspace name → connect Linear → connect Slack → trigger first context. Do not require all integrations; require at least Linear |
| Progress indicator with step count | Users need to know how far they are. "Step 2 of 4" reduces drop-off more than any other single UI element in onboarding research | LOW | Numbered stepper at top, not a progress bar. Steppers communicate meaning (what this step does); bars communicate only completion percentage |
| Integration OAuth step within onboarding | Connecting integrations inside the flow (not as a separate detour) is the standard. Supabase does this for DB setup; Clerk for provider selection | MEDIUM | Reuse existing OAuth connect functions. Show connection confirmation in-step (green checkmark, external account name) before proceeding |
| Skip / defer option for non-critical integrations | Slack, GitHub, Fathom are valuable but not required to see the core product. Blocking on all integrations kills conversion | LOW | Mark Linear as required (with lock icon), others as optional with "Add later" links. This mirrors Vercel's "Deploy now, configure later" philosophy |
| Contextual explanation per step | Each step needs one sentence explaining WHY, not just what. "Connect Linear so ContextOS can pull your team's tickets" is better than "Connect Linear" | LOW | 15-20 words max. Teal accent on the key verb. Already the style of the landing page problem section |
| Return-to-onboarding state on incomplete setup | If user closes mid-onboarding, they must return to the same step, not restart. Supabase preserves onboarding progress in user metadata | LOW | Store `onboarding_step` in Supabase user metadata. Middleware checks this before redirecting to dashboard |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| First context generation as the final onboarding step | The "aha moment" for ContextOS is seeing an actual context page generated for a real ticket. Showing this inside onboarding (not after) converts users from "I connected some integrations" to "I saw the product work" | MEDIUM | After Linear + Slack connect, show a ticket picker or auto-select the most recent assigned ticket. Trigger generation, show a live progress bar (LangGraph steps: "Fetching Linear data... Pulling Slack context... Synthesizing..."), then reveal the context page. This is the money moment |
| Animated completion state for each integration step | When OAuth succeeds and returns, the step visually resolves (checkmark draw animation, integration name appears, accent color activates). This mirrors Linear's "cinematic transition" onboarding noted in multiple analyses | LOW | SVG checkmark stroke animation (stroke-dashoffset), 400ms spring curve. Not a spinner — a draw animation communicates finality |
| Workspace name personalization from first step | Ask for workspace/team name in step 1. Use it in the onboarding copy from step 2 onward ("Connecting Acme's Linear workspace"). Creates immediate ownership and reduces feel of generic setup | LOW | Single text input, no validation beyond non-empty. Store in `workspaces.name`. Already a DB column |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Video tutorial in onboarding | "Users need to learn the product" | Videos are skipped by 80%+ of users in B2B tools. Developer users explicitly prefer reading docs. Videos add CDN costs and go stale on every UI change | Write one tight onboarding tooltip per step (15-20 words). Link to docs from settings, not onboarding |
| Onboarding checklist widget in dashboard | "Persistent reminder to complete setup" | A floating checklist in an otherwise focused dashboard is visual noise once setup is complete. It's appropriate for CRM tools (many optional setup items) but not for a tool with 2-3 required steps | Use banner on dashboard home if Linear is not connected. Auto-dismiss banner once connected. No persistent widget |
| Email drip sequence triggered from onboarding | "Re-engage users who don't complete setup" | This is a marketing infrastructure problem (requires sending infra, unsubscribe handling, GDPR compliance) for a product in dogfooding. The team is the user. | When multi-team use begins, add PostHog funnel tracking and manual outreach first. Email automation is v3+ |
| Multi-step form with validation before OAuth | "Collect team size, use case, role before connecting" | Every question before the value moment increases drop-off. Developer tools that ask qualifying questions in onboarding (vs. after) perform measurably worse | Skip the questionnaire entirely. You're dogfooding — you know the use case |

---

### Capability 2: Dark Theme Dashboard Redesign

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Dark mode as default (not a toggle) | ContextOS's landing is `#0A0A0F` navy-black. Defaulting the dashboard to light mode creates a jarring brand contradiction. Developers expect dark-first for internal tools | LOW | The existing `globals.css` has a complete `.dark` theme block. The issue is it's not the default — need `<html class="dark">` in layout. Remove the light-mode defaults or set dark as system-matched default |
| Surface hierarchy with 3-4 levels | A single `--background` color for everything flattens the UI. PostHog 3000 uses 3 levels; Linear uses 3-4. Without elevation, cards float on nothing | LOW | Currently have: `background: oklch(0.12)`, `card: oklch(0.17)`, `input: oklch(0.25)`. Need a 4th: `elevated-card: oklch(0.20)` for hover states and overlays. This is a single token addition |
| Teal primary as signal color, not decoration | The brand primary is `oklch(0.60 0.18 250)` — a strong teal. Applied everywhere it reads as MS Teams. Applied only on active/interactive states it reads as Linear | LOW | Audit every `text-primary` and `bg-primary` usage. Teal should appear on: active nav items, connected integration borders, CTA buttons, status indicators. Nowhere else |
| Consistent border token usage | Generic dark UIs use `border-border` inconsistently, sometimes adding `bg-muted/40` overlays that create muddy mid-tones | LOW | One rule: cards use `border` token (`oklch(0.28)`), hover states use `border-border/60`, focus states use `ring` token (teal). Never mix border and background tokens on the same element |
| Type scale that distinguishes heading from body | Current dashboard uses `text-2xl font-bold` for page titles and `text-sm` for everything else. No intermediate scale for section headers creates visual monotony | LOW | Add `text-xs uppercase tracking-[0.08em] font-medium text-muted-foreground` for section labels (already used partially in the current dashboard home). Add `text-base font-semibold` for card headers. Reserve `text-2xl` for page-level headings only |
| JetBrains Mono for identifiers and data | Ticket IDs, timestamps, token counts, API keys, sync counts — all proportional today. Context engineers will notice | LOW | Already loaded in `layout.tsx`. Add utility class: `font-mono tabular-nums` to all identifier/count/timestamp elements. The current dashboard uses it on one element — extend systematically |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Noise texture layer on interactive cards | Raycast and the ContextOS landing page both use grain overlays. Applied to interactive card backgrounds (not static surfaces), it adds tactility that reads as handcrafted. This is the single most-commented-on technique in "crafted vs generic" analysis | LOW | Already built: `.noise-bg::before` in `globals.css`. The problem is it's 0.015 opacity (nearly invisible). On cards: raise to 0.025-0.04 on hover, 0 at rest. The texture should appear when the user interacts, not as a static background |
| Dot grid pattern on empty-state backgrounds | The landing page uses a CSS dot grid extensively. Bringing it into the dashboard only on empty states (no context pages, no activity) creates continuity between landing and app. Users who came from the landing recognize the pattern as "home" | LOW | CSS radial-gradient dot grid: `background-image: radial-gradient(circle, oklch(0.35 0.02 250) 1px, transparent 1px)`, `background-size: 24px 24px`. Apply only to empty-state panels, not general backgrounds |
| Gradient text on page-level headings only | The landing uses gradient text pervasively. In the dashboard, restricting it to exactly one element per page (the page heading or a key metric) makes it feel like intentional branding rather than template overuse | LOW | Tailwind utility: `bg-gradient-to-r from-foreground to-foreground/60 bg-clip-text text-transparent`. Use on `<h1>` only — or on the connected integration count ("3 sources active") |
| Brand-colored left border on connected integrations | Already implemented in the current dashboard (`border-l-2 border-l-violet-500` for Linear, etc.). This is a pattern worth keeping and extending: it creates a visual link between the integration's brand identity and its connected state. Not generic | ALREADY BUILT | Keep this pattern. Ensure it extends to activity timeline events (source-colored left border per event type) |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Light/dark mode toggle in dashboard | "User preference" | Adds a theme provider, `next-themes`, localStorage sync, and system preference detection. The audience is the founding team — they can tolerate dark-only for the dogfood phase | Ship dark-only for v1.1. Add system-preference detection (not a toggle) in v2 when external users onboard |
| Glassmorphism / frosted glass effects | "Premium, modern look" | Glassmorphism requires bright background colors to be readable. On a dark `oklch(0.12)` background, blur effects produce visual mud, not clarity. Linear and PostHog explicitly moved away from this | Use surface elevation (different background lightness) instead of blur for depth. Blur only works on modals over content, not as a general card style |
| Heavy gradients on dashboard cards | "Matches the landing page energy" | Landing page gradients work because they're on a marketing surface (large, slow-scroll, brand-first). Dashboard cards are repeated UI elements — heavy gradients cause visual fatigue after 30 seconds of use | Reserve gradients for: page heading text, the onboarding completion illustration, and the empty state illustration. Use flat tinted backgrounds for all cards |
| Animation on every interaction | "Polished feel" | Over-animated dashboards feel slow and immature. PostHog 3000's animation philosophy: entrance animations only, not repeated-interaction animations. Hover effects should be CSS transitions, not Framer Motion sequences | Framer Motion for: page-level route transitions, onboarding step transitions, context page generation progress. CSS transitions for: hover states, focus rings, status dots |

---

### Capability 3: Context Feed UX

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Browsable feed of all context pages with status | The existing context page is a lookup tool (type a ticket ID). Users expect to browse. Every document-centric tool (Notion, Linear, GitHub) shows a list first | MEDIUM | Replace the lookup tab with a paginated list view. Cards show: ticket identifier (mono), title, status dot (ready/generating/stale/error), generation timestamp (mono, relative), integration sources used (small brand logos). Sorted by generated_at DESC |
| Status filtering | Users need to find stale or errored pages quickly. Vercel's deployment list shows status filter pills as the primary filter control | LOW | Filter pills: All / Ready / Generating / Stale / Error. Pill design: rounded-full, active = teal bg, inactive = outline. No dropdown — inline pills take one click |
| Free-text search across ticket identifiers and titles | Developers search by ticket ID. The expected interaction: type "CON-16" and see that ticket's context page | LOW | Client-side filter against the fetched list (not a new API call) for small datasets. For >100 pages, debounce to a search API endpoint |
| Detail view without leaving the feed | Clicking a context page should expand it (side panel or route) without losing list position. Linear's split view is the reference | MEDIUM | Option A (simpler): route to `/dashboard/context/[id]` with a back button. Option B (premium): slide-in right panel with the list still visible. Start with Option A for v1.1, design for Option B in v2 |
| Copy AI prompt button on detail view | Already spec'd in v1.0 and must be in this view. One-click copy, confirmation toast | LOW | Sonner toast: "Copied to clipboard" with a 2s auto-dismiss. Button should be the most prominent element on the detail view, not a secondary action |
| Regenerate button on detail view | Already spec'd in v1.0 | LOW | Secondary button, shows spinner during generation, triggers the existing generation endpoint |
| Source attribution in detail view | Sources list already implemented in context/page.tsx. Keep and improve visual design | LOW | Source chips with brand icons (Linear/Slack/Fathom) rather than text type labels. Color-coded by source type |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Generation progress with named steps | When generating, show "Fetching Linear ticket... Pulling Slack threads... Running AI synthesis..." rather than a generic spinner. This is the same experience Linear shows during their AI label generation | MEDIUM | Supabase Realtime subscription to the `context_generation_jobs` table. Map job step names to user-readable labels. Each step animates in as it starts. This works because the LangGraph pipeline already has named nodes |
| Stale indicator with reason | "Stale" means something changed since last generation. Show WHAT changed: "2 new Slack messages since last generation" or "Ticket updated 3 hours ago." Vercel shows deployment status reason inline | MEDIUM | Requires backend to compute `stale_reason` when marking stale. Frontend shows it as a hover tooltip on the stale status dot |
| Keyboard navigation in the feed | Developer tools users expect `j/k` for next/prev, `Enter` to open, `Esc` to close, `r` to regenerate, `c` to copy prompt. PostHog 3000's redesign explicitly added keyboard-first navigation as a differentiator | MEDIUM | useEffect + keydown listeners on the feed page. Only activate when not in a text input. This is a 50-line implementation but takes careful state management |
| Source count as feed metadata | Show how many sources contributed to each context page in the feed card ("3 sources: Linear, Slack, Fathom"). Surfaces the quality of the context at a glance | LOW | Count sources by type from the sources array. Render as small brand logos (16px) in the feed card. Already have brand logo components |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Infinite scroll | "Better than pagination for browsing" | Infinite scroll destroys URL shareability, breaks back-button behavior, and requires complex intersection observer management. For a tool where most users have <50 context pages, pagination is cleaner | Use simple numbered pagination or "Load more" button. 20 pages per batch |
| Inline editing of context page content | "Let me fix AI mistakes" | Documented anti-feature from v1.0 research. Turns generated artifact into a wiki. Defeats the purpose | Provide "Generate with hint" input on the regenerate action. One text field: "What should be different?" Feed as a prompt suffix |
| Saved search / smart folders | "I want to see all context pages for Project X" | Premature organization layer. The team has <50 context pages. Add grouping only when the list becomes unmanageable | Filter by status (already planned). Add Linear project/label filter in v1.5 if the team requests it |

---

### Capability 4: Activity Timeline

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Reverse-chronological feed of system events | Every operations dashboard (Vercel, Supabase, PostHog, Sentry) shows an activity/event log. Users expect to know what the system has done | MEDIUM | Events: context page generated, context page stale, integration connected/disconnected, webhook received, sync completed, error occurred. Store in a `workspace_events` table (event_type, metadata, created_at) |
| Event type icons with source color | Activity feeds without icons look like server logs. Each event type needs a distinct icon and color. The aubergine.co activity feed guide explicitly recommends lightweight icons per event type | LOW | Map event types to lucide-react icons: Sparkles (context generated), AlertCircle (error), Link (integration connected), RefreshCw (sync), Clock (stale). Color = source brand color (teal for ContextOS events, violet for Linear, etc.) |
| Relative timestamps with absolute on hover | "5 minutes ago" is the standard for recent events. Absolute timestamp on hover covers the power-user need without cluttering the feed | LOW | `formatRelativeTime` already exists in `lib/utils.ts`. Add `title={absoluteTimestamp}` attribute for hover. Already used in the current dashboard |
| Event grouping by day | GitHub's activity feed, Linear's changelog, and Vercel's deployment log all group events by date header (Today, Yesterday, March 3). Without grouping, long feeds become unreadable | LOW | Date separator component: `text-xs text-muted-foreground/50 uppercase tracking-widest border-b border-border/30 py-2 mb-2`. Insert between events when date changes |
| Empty state when no activity | A blank white panel is worse than an empty state message. Every best-practice guide mentions this | LOW | Empty state: dot grid background, Sparkles icon, "No activity yet. Connect Linear to start generating context." — one call to action |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Real-time feed via Supabase Realtime | The existing dashboard already plans Supabase Realtime for context page status. Extending it to the activity feed means new events appear without refresh. This is the experience PostHog 3000 and Supabase logs deliver | MEDIUM | Subscribe to `workspace_events` channel filtered by `workspace_id`. Prepend new events at the top with a slide-down animation (stagger-children pattern). Supabase Realtime is already in the stack; this is schema + subscription work |
| Left border color coding by event type/source | Each activity item has a 2px left border in the source's brand color (teal for synthesis, violet for Linear, emerald for Slack). Same pattern as the integration status list. Creates visual scanning rhythm without needing to read the icon every time | LOW | Same `border-l-2` pattern already used in the integration list. Extend: `border-l-emerald-500` for Slack events, `border-l-violet-500` for Linear events, `border-l-primary` for ContextOS events |
| Clickable events that link to the relevant entity | Tapping a "Context page generated" event navigates to that context page. Tapping "Integration connected" navigates to integrations settings. GitHub's activity feed does this; most internal tools don't bother | LOW | Add `link_to` field to the workspace_events record. Route to `/dashboard/context/[id]` or `/dashboard/integrations` as appropriate. Render the event item as a subtle `<Link>` wrapper |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full audit log with user attribution | "Who did what?" | The product is single-user per workspace during dogfooding. Multi-user audit logging adds schema complexity (actor_id, IP, user agent) before there are multiple actors | Seed the event table with `actor_type: 'system' | 'user'` field but don't display attribution in UI until multi-user |
| Filterable activity log with saved filters | "I only want to see errors" | For a feed of <100 events/day during dogfooding, filtering by type adds UI complexity not yet needed. Build the simple version first | Filter by event category (All / Errors / Integrations / Context) only when the team asks for it. Don't pre-build |
| Download activity log as CSV | "Compliance / audit export" | This product is not being used for compliance. CSV export is a procurement checkbox for enterprise tools | Not applicable for v1.1 or v2. Add only if an enterprise customer asks |

---

### Capability 5: Team Settings

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Workspace name editing | Every SaaS product allows changing the workspace name | LOW | Single text input + save button. Update `workspaces.name`. Confirmation toast on success |
| API key management (list, create, revoke) | The MCP server requires API keys. Users need to see existing keys, create new ones, and revoke compromised keys. Supabase and Clerk both surface API key management in settings | LOW | Table with columns: name, key prefix (e.g. `ctx_...`), created date, last used date, revoke button. Generate button creates a new key. Full key shown once on creation with a copy button (same pattern as GitHub PATs) |
| Integration management (disconnect) | Already exists at `/dashboard/integrations`. Settings is the expected home for this | LOW | Move integration connection status and disconnect actions here, or add a link from settings to integrations. Don't duplicate — link |
| Notification preferences (webhook failure alerts) | When synthesis fails or a webhook is rejected, the user needs to know. Email or in-app toggle | LOW | Simple toggle list: "Email me on synthesis errors", "Email me on integration disconnection". Store in `workspaces.notification_prefs JSONB`. Use Supabase Edge Function or FastAPI to send via Resend/Postmark |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| API key usage metrics per key | Show the last-used timestamp and a rough call count (last 24h, last 7d) per API key. Clerk does this. Gives the user confidence the MCP server is actually calling the API | MEDIUM | Track API key usage events in Redis (increment on each call, expire after 30d). Surface in settings table. This is 30 lines of FastAPI middleware + a settings query |
| Webhook health indicator | Show a "Webhook status" panel: last webhook received from each integration (Linear / Slack), timestamp, success/failure status. When webhooks stop flowing, users currently have no visibility | LOW | Query `webhook_events` table for last received per source. Green dot = received in last 2 hours. Yellow = 2-24h. Red = 24h+. This is a read-only status display |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Team member invites and role management | "We'll have multiple users" | Single-workspace dogfooding. Building invite flows, role-based permissions, and member removal before there are 2+ teams is YAGNI. Linear, Supabase, and Vercel all built this after their founding teams had product-market fit | Add a placeholder "Team" section in settings that says "Coming soon — invite your team." No implementation. |
| SSO / SAML configuration | "Enterprise teams need SSO" | Supabase Auth supports SSO via third-party providers, but configuring SAML is a multi-week project for a product not yet past internal dogfooding | Supabase's Auth provider list already includes Google OAuth for a future v2 addition. SAML is v3+ |
| Custom domain / white-labeling | "Our company wants contextos.acme.com" | No external customers yet. Custom domain adds Vercel project configuration, DNS management UI, and SSL certificate management | Not applicable for v1.1 |

---

### Capability 6: Auth Page Redesign

#### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Dark background matching dashboard | The current auth pages use `Card` (white background) centered on a light background. Users going from the landing page (`#0A0A0F`) to login see a jarring white flash. Clerk's 2025 dark mode dashboard and Supabase's auth pages both match their product's dark theme | LOW | Set auth layout background to `oklch(0.12)` (same as dashboard `--background`). Style the form card to `oklch(0.17)` (card surface). Remove the default light Card component and build a custom auth form panel |
| Brand logo at top of form | Every developer tool auth page (Vercel, Supabase, Clerk, Linear) shows the product logo above the form. The current auth page has no logo | LOW | Add the ContextOS wordmark (or logo mark) above the form. Use the same `text-[15px] font-semibold tracking-[-0.02em]` as the nav bar wordmark |
| Consistent error state styling | The current login page uses `bg-destructive/10 p-3 rounded-md` for errors. This should match the dashboard's error banner style | LOW | Use the same error component as the dashboard: `border-destructive/20 bg-destructive/5 flex items-center gap-3 rounded-xl px-4 py-3` |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Subtle brand illustration or dot-grid backdrop | Split-layout auth pages (form on left, brand visual on right) are the premium pattern for B2B tools. Even Vercel's login is centered-form with brand color background. ContextOS could add the dot-grid pattern on the auth background for continuity with the landing page | LOW | Add the CSS dot grid background to the auth layout (same radial-gradient technique as landing). This creates visual continuity: landing → login → dashboard feels like one product, not three separate tools |
| Magic link as primary, password as secondary | The current login shows both forms with equal prominence. Most developer tools (Supabase's own dashboard, Vercel, Netlify) default to magic link or SSO. For internal tools with no password requirements, magic link should be the hero action | LOW | Reorder: magic link form first, "Or sign in with password" as a collapsed section below. This better matches how the founding team actually authenticates |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Social OAuth buttons (Google, GitHub) | "Faster login for developers" | Supabase Auth supports these natively, but adding social providers requires: redirect URI registration per provider, environment variables, testing on each provider, and edge cases around account merging. For a 3-person founding team where you control who has accounts, this is unnecessary complexity | Add Google OAuth in v1.5 when external users onboard. GitHub OAuth in v2. For now: magic link covers the use case |
| "Remember me" checkbox | "Users expect this" | Supabase sessions are persistent by default (30-day token). There is no session expiry problem to solve. Adding a visible "Remember me" checkbox implies there's a problem that doesn't exist | Remove cognitive noise. Don't add UI for a non-problem |
| Multi-step auth wizard | "Welcome to ContextOS → Enter email → Enter password → 2FA" | Three steps for login is friction. The current single-form approach is correct. Only split into steps if adding MFA, which is not planned | Keep single-form. If MFA is added in v2, then a step UI makes sense |

---

## Feature Dependencies

```
[Onboarding Flow]
    └──requires──> [Supabase user metadata (onboarding_step)]
    └──requires──> [Linear OAuth (existing)]
    └──requires──> [Slack OAuth (existing)]
    └──requires──> [Context generation trigger (existing)]
    └──enables──>  [Dashboard access] (gate until step 3+ complete)

[Context Feed (list view)]
    └──requires──> [Context pages in DB (from v1.0)]
    └──requires──> [Supabase Realtime (for live status)]
    └──enables──>  [Context detail view]
        └──requires──> [Copy AI prompt (existing)]
        └──requires──> [Regenerate (existing)]

[Activity Timeline]
    └──requires──> [workspace_events table (new schema)]
    └──requires──> [Event emission from: webhooks, OAuth, synthesis pipeline]
    └──enhances──> [Supabase Realtime (reuse subscription pattern from context feed)]
    └──enables──>  [Webhook health indicator (in settings)]

[Dark Theme Design System]
    └──requires──> [globals.css token audit]
    └──blocks──>   [All other UI work in this milestone]
    └──enables──>  [Auth page redesign, Dashboard home redesign, Context feed, Activity timeline]

[Auth Page Redesign]
    └──requires──> [Dark theme tokens (above)]
    └──independent of──> [All feature work (can ship any time)]

[Team Settings]
    └──requires──> [API keys table (v1.0)]
    └──requires──> [webhook_events table (for health indicator)]
    └──requires──> [workspace_events table (reuse from activity timeline)]
    └──independent of──> [Context feed, Activity timeline]

[Onboarding "Aha Moment" step]
    └──requires──> [Context generation pipeline (Phase 4)]
    └──requires──> [Linear OAuth connected (Phase 2)]
    └──note──> This is the highest-risk dependency: if Phase 4 is not complete, the aha-moment step cannot show a real context page. Plan a fallback: show a demo/mock context page if no real ticket is available
```

### Dependency Notes

- **Dark theme must ship first:** Every UI feature in this milestone builds on the dark token system. If tokens are inconsistent, every component built on top will need rework. Token audit + dark-default must be the first PR of this milestone.
- **Onboarding depends on Phase 4 for the aha moment:** The most valuable onboarding step (first context generation) requires the synthesis pipeline to be working. If this milestone runs before Phase 4 completes, build onboarding steps 1-3 and gate step 4 on Phase 4 readiness.
- **Activity timeline requires a new DB table:** `workspace_events` does not exist yet. This needs a migration before any event emission code can be written. Schema work should happen in the first sprint alongside token audit.
- **Context feed (list) replaces the existing lookup tab:** The current context/page.tsx has a "Ticket Context" tab that requires knowing a ticket ID. The feed replaces this as the primary entry point. The lookup tab becomes a secondary action (or moves to settings for power users).

---

## MVP Definition

### Launch With (this milestone)

Features needed for the dashboard to feel like a product, not a prototype.

- [ ] **Dark mode as default** — Remove the jarring light/dark contradiction with the landing page. Zero-effort token change.
- [ ] **JetBrains Mono on all identifiers** — Single CSS audit pass. Makes the dashboard read like a developer tool instantly.
- [ ] **Guided onboarding flow (steps 1-3: workspace name, Linear, Slack)** — Users must be walked to the product; they won't walk themselves.
- [ ] **Auth page dark redesign** — First impression. Cannot ship a white card login for a dark-brand product.
- [ ] **Context feed list view** — Replace lookup-only with browsable list. Core dashboard functionality.
- [ ] **Context feed detail with copy + regenerate** — Existing functionality, new visual design.
- [ ] **Activity timeline (basic, non-real-time)** — Shows the system is alive. Builds trust. Polling is acceptable for v1.1.
- [ ] **workspace_events table + event emission** — Backend prerequisite for timeline. Emit on: synthesis complete, synthesis error, integration connected/disconnected.
- [ ] **Settings: API key management** — Required for MCP users. Already spec'd in v1.0 but not in dashboard yet.

### Add After Validation (v1.1.x)

- [ ] **Supabase Realtime for activity timeline** — Upgrade polling to live updates once the basic timeline ships and is being used.
- [ ] **Onboarding step 4: first context generation** — Add the aha-moment step once Phase 4 pipeline is stable.
- [ ] **Context feed keyboard navigation (j/k/Enter/Esc)** — Developer delight feature. Add when the team is using the feed daily and keyboard shortcuts feel natural to add.
- [ ] **Stale reason indicator on context pages** — Adds context to "stale" status. Requires backend work to compute the reason.
- [ ] **Animated integration connection confirmation** — SVG checkmark draw in onboarding. Adds craft; defer until core flow works.
- [ ] **Settings: webhook health indicator** — Once the team has run the product for 2+ weeks and wants visibility into webhook health.

### Future Consideration (v2+)

- [ ] **Light/dark mode system preference detection** — When external users onboard. Not needed for dogfooding team.
- [ ] **Context feed right-panel split view** — Premium UX upgrade over route-based detail. Add when team requests faster navigation.
- [ ] **Team member invites** — When second team onboards.
- [ ] **Social OAuth (Google/GitHub)** — When external users create accounts.
- [ ] **API key usage metrics** — When MCP server usage is established enough to want per-key analytics.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Dark mode as default | HIGH | LOW | P1 |
| JetBrains Mono on identifiers | HIGH | LOW | P1 |
| Auth page dark redesign | HIGH | LOW | P1 |
| workspace_events table + event emission | HIGH | LOW | P1 |
| Guided onboarding (steps 1-3) | HIGH | MEDIUM | P1 |
| Context feed list view | HIGH | MEDIUM | P1 |
| Context feed detail view (redesigned) | HIGH | LOW | P1 |
| Activity timeline (polling) | MEDIUM | MEDIUM | P1 |
| Settings: API key management | HIGH | LOW | P1 |
| Surface hierarchy token audit | HIGH | LOW | P1 |
| Onboarding step 4 (first context gen) | HIGH | MEDIUM | P2 |
| Supabase Realtime for activity timeline | MEDIUM | LOW | P2 |
| Context feed keyboard navigation | MEDIUM | LOW | P2 |
| Stale reason indicator | MEDIUM | MEDIUM | P2 |
| Animated onboarding completion states | LOW | LOW | P2 |
| Settings: webhook health indicator | MEDIUM | LOW | P2 |
| API key usage metrics | LOW | MEDIUM | P3 |
| Context feed right-panel split view | MEDIUM | HIGH | P3 |
| Light/dark mode toggle | LOW | MEDIUM | P3 |
| Team member invites | LOW | HIGH | P3 |
| Notification preferences | LOW | MEDIUM | P3 |

**Priority key:**
- P1: Must have for this milestone to feel "done"
- P2: Should have, add in the second sprint once P1 is stable
- P3: Nice to have, future milestone

---

## Competitor Feature Analysis: Onboarding

| Onboarding Pattern | Linear | Vercel | Supabase | Clerk | ContextOS Approach |
|--------------------|--------|--------|----------|-------|-------------------|
| Steps before dashboard access | Yes (workspace setup) | Yes (first project) | Yes (project creation) | Yes (framework selection) | **Yes — Linear connect required as gate** |
| Integration setup in-flow | Partial (GitHub import optional) | Yes (GitHub/GitLab import) | Yes (Vercel environment sync) | Yes (provider selection) | **Yes — OAuth steps 2 and 3** |
| Aha moment in onboarding | Yes (first issue created) | Yes (first deploy live) | Yes (first query runs) | Yes (first sign-in works) | **Yes — first context page generated (step 4)** |
| Skip options for optional steps | Yes | Yes | Yes | Yes | **Yes — Slack/GitHub/Fathom skippable** |
| Progress indicator type | Step dots | Step list | Progress bar | Step tabs | **Numbered stepper (step X of Y)** |
| Return-to-onboarding on incomplete | Yes | Yes | Yes | Yes | **Yes — stored in user metadata** |

## Competitor Feature Analysis: Dashboard Dark Theme

| Visual Pattern | Linear | PostHog 3000 | Vercel | Supabase | ContextOS Target |
|----------------|--------|--------------|--------|----------|-----------------|
| Default mode | Dark | Dark | Light (system) | Dark option | **Dark (forced default)** |
| Surface levels | 4 | 3 | 2 | 3 | **4 (add elevated-card token)** |
| Accent color usage | Purple on active states only | Red on active/brand only | None (mono) | Emerald on status | **Teal on status/CTA only** |
| Monospace in data | Yes (identifiers) | Yes (events, IDs) | Yes (commit SHAs) | Yes (UUIDs, queries) | **Yes (all identifiers)** |
| Texture/noise overlay | No | No | No | No | **Yes (on interactive card hover)** |
| Gradient text | No (in product) | No (in product) | No | No | **Yes (h1 only, or key metric)** |

---

## Sources

- [Linear UI Redesign — linear.app/now](https://linear.app/now/how-we-redesigned-the-linear-ui) — LCH color system, Inter Display, inverted-L chrome refinement (HIGH confidence, official)
- [PostHog 3000 redesign — X/Twitter announcement](https://x.com/posthog/status/1737140231713734926) — dark mode, data density, side panels, command palette (HIGH confidence, official)
- [PostHog "What if PostHog looked like a dev tool?"](https://posthog.com/blog/posthog-as-a-dev-tool) — philosophy behind dev-tool aesthetics, command palette, Cmd+Shift+K (MEDIUM confidence, CSS-only page response)
- [PostHog "An engineer's guide to vibe design"](https://newsletter.posthog.com/p/an-engineers-guide-to-vibe-design) — hierarchy, contrast, balance, consistency, alignment, proximity; font recommendations, tight/standard/loose spacing, elevation options (HIGH confidence, full article retrieved)
- [Vercel dashboard redesign](https://vercel.com/blog/dashboard-redesign) — project previews, deployment status in tab icons, filterable logs, git metadata display, 1.2s FMP improvement (HIGH confidence, official)
- [LogRocket: Linear design trend](https://blog.logrocket.com/ux-design/linear-design/) — dark mode characteristics, typography boldness, color reduction, single-direction flow, minimal CTAs (HIGH confidence, full article retrieved)
- [Aubergine.co: Designing chronological activity feeds](https://www.aubergine.co/insights/a-guide-to-designing-chronological-activity-feeds) — actor/icon/description/timestamp components, lazy loading, filtering, new activity indicators (HIGH confidence, full article retrieved)
- [growthdives.com: Linear onboarding](https://www.growthdives.com/p/the-onboarding-linear-built-without) — one input per step, minimal animations, no growth tricks, trust over tricks (MEDIUM confidence, paywalled, summary from search results)
- [fmerian.medium.com: Linear FTUX](https://fmerian.medium.com/delightful-onboarding-experience-the-linear-ftux-cf56f3bc318c) — step structure, workspace creation flow (LOW confidence, 403 blocked)
- [shadcn/ui Theming](https://ui.shadcn.com/docs/theming) — OKLCH variable patterns, dark mode implementation (HIGH confidence, official)
- [PostHog "What makes a dev tool feel crafted"](https://www.linkedin.com/posts/j-hawkins_what-if-posthog-looked-like-a-dev-tool-activity-7140477511817158656-uA2P) — confirmed dark mode, density, side panels as the three pillars (MEDIUM confidence, LinkedIn summary)
- Existing codebase: `/apps/web/src/app/globals.css`, `/apps/web/src/app/dashboard/page.tsx`, `/apps/web/src/app/dashboard/sidebar.tsx`, `/apps/web/src/app/dashboard/context/page.tsx` — current design system tokens, existing patterns, gaps (HIGH confidence, direct inspection)

---

*Feature research for: ContextOS v1.1 dashboard redesign, onboarding, dark design system*
*Researched: 2026-03-04*
