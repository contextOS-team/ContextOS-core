# Stack Research

**Domain:** Dashboard redesign — guided onboarding, dark-theme design system, context feed, activity timeline, team settings
**Researched:** 2026-03-04
**Confidence:** HIGH

> **Scope note:** This file covers ONLY net-new additions for the next milestone.
> Existing validated stack (Next.js 15, React 19, TypeScript, Tailwind v4, shadcn/ui + Radix, CVA, clsx, tailwind-merge,
> Inter + JetBrains Mono, Supabase Auth, @supabase/ssr, @supabase/supabase-js, PostHog, Sentry, FastAPI, Supabase
> PostgreSQL, lucide-react, sonner, tw-animate-css) is NOT repeated here.

---

## Recommended Stack

### Core Technologies (New)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| react-hook-form | ^7.71.2 | Multi-step onboarding form state | Uncontrolled inputs, minimal re-renders per step — shadcn/ui's official form docs use this. Per-step Zod schema validation via `trigger()` before advancing. Zero dependencies on existing stack. |
| @hookform/resolvers | ^5.2.2 | Zod v4 → react-hook-form bridge | Version 5.x added automatic Zod v3/v4 runtime detection. Required companion to react-hook-form for schema validation. `zodResolver` is the shadcn/ui-prescribed pattern. |
| zod | ^4.3.6 | Per-step and final schema validation | Already used in MCP server. Add to `apps/web`. v4 is 14x faster string parsing vs v3, 1.9 KB gzipped with `zod/mini`. Use full `zod` import for compatibility — @hookform/resolvers 5.x handles both. |
| motion | ^12.34.5 | Onboarding step transitions, timeline animations | The successor to framer-motion (same package, renamed). `tw-animate-css` already installed covers enter/exit for static elements; motion adds layout animations (step-to-step slide), height:auto transitions, and gesture-based interactions that CSS keyframes cannot do. Add ONLY because the onboarding wizard requires animated step transitions and the activity timeline needs staggered entry. Do NOT use motion for everything — keep tw-animate-css for simple fade/scale. |
| @stepperize/react | ^6.1.0 | Onboarding wizard step state machine | Type-safe `defineStepper` + `useStepper` hook. Handles step navigation, validation gating, and progress tracking without coupling step state to form state. Composable with shadcn/ui components. Lightweight (~2 KB). Alternative: hand-rolled stepper with useState — use @stepperize/react only if onboarding has 4+ steps with conditional branching. |

**Confidence:** HIGH — versions verified against npm registry (2026-03-04). react-hook-form + zod + @hookform/resolvers is the prescribed shadcn/ui pattern. motion is the production-standard for complex React animation.

---

### Supporting Libraries (New)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| nuqs | ^2.8.9 | URL-synced filter state for context feed | Context feed has type + status + search filters. nuqs gives `useQueryState` (identical to `useState` but stored in URL). Enables shareable filtered views, browser back/forward, and RSC re-render triggering (`shallow: false`). 6 KB gzipped. Use for every filter/search param in the dashboard — do NOT use `useState` for URL-representable state. |
| date-fns | ^4.1.0 | Timestamp formatting in timeline + feed | Activity timelines show relative times ("2 minutes ago", "Mar 4") and absolute timestamps on hover. date-fns v4 is tree-shakable, immutable, and 22 MB unpacked but only what you import ships. Use `formatDistanceToNow`, `format`, `parseISO`. Alternative: dayjs (670 KB unpacked) — use dayjs if bundle size becomes critical. date-fns is the shadcn/ui DatePicker default so it's the consistent choice. |

**Confidence:** HIGH — nuqs 2.8.9 verified on npm. date-fns 4.1.0 verified on npm. Both integrate with existing Next.js 15 App Router without configuration.

---

### Design System Additions (Zero New Dependencies)

These are CSS-only additions to the existing Tailwind v4 + `globals.css` setup. No new npm packages.

#### 1. Unified Dark Theme Tokens

**Problem:** Landing page uses hex-based dark tokens scoped under `.landing-theme`. Dashboard uses light-default oklch tokens in `:root` with a `.dark` override. The new dashboard milestone requires the app to be dark-first (matching the landing brand direction), but the two themes currently cannot share tokens without duplication.

**Solution:** Extend `globals.css` with dashboard-specific dark variables in `.dark` and a semantic token layer that both landing and dashboard reference. Do NOT merge landing.css into globals.css — landing isolation is intentional.

```css
/* In globals.css — extend the existing .dark block */
.dark {
  /* Existing oklch tokens stay. Add semantic brand aliases: */
  --brand-teal: #00D4AA;          /* matches landing --color-teal */
  --brand-teal-muted: rgba(0,212,170,0.12);
  --brand-surface-0: #0A0A0F;    /* deepest layer = landing --color-navy */
  --brand-surface-1: #0F0F18;    /* card surfaces = landing --color-surface */
  --brand-surface-2: #141420;    /* elevated surfaces = landing --color-surface-2 */
  --brand-border-subtle: rgba(255,255,255,0.07);
}
```

This creates a shared vocabulary between landing.css and dashboard components without requiring a CSS-in-JS library or a new design token tool. Tailwind v4 `@theme` consumes these via `var(--brand-teal)` in utility definitions.

**Confidence:** HIGH — Tailwind v4 CSS-first architecture verified. This pattern is documented in the Tailwind v4 `@theme` guide.

#### 2. Dashboard Force-Dark

The dashboard layout needs to run permanently in dark mode regardless of OS preference. In `globals.css`:

```css
/* Force dashboard into dark mode — no OS preference dependency */
.dashboard-theme {
  color-scheme: dark;
}
```

Apply `className="dashboard-theme dark"` to the dashboard root layout `<div>` (already `flex flex-col min-h-screen`). This forces all Tailwind `.dark:` variants and the existing `.dark` token block without a theme toggle library.

**Why not `next-themes`?** next-themes (a common suggestion) adds a ThemeProvider, hydration flash mitigation, and localStorage for user preference. The milestone does not require a light/dark toggle — the dashboard is permanently dark. next-themes is overkill and adds 3 KB for a feature not needed.

**Confidence:** HIGH — this is the zero-dependency approach for force-dark in Next.js App Router.

#### 3. Shadcn/ui Components to Add

The following shadcn/ui components are copy-pasted via CLI — no npm packages:

```bash
# Add these via shadcn CLI (they use already-installed Radix primitives)
npx shadcn@latest add progress      # Onboarding step progress bar
npx shadcn@latest add command       # Context feed search/filter (cmdk-powered)
npx shadcn@latest add select        # Filter dropdowns in context feed
npx shadcn@latest add badge         # Status chips in activity timeline
npx shadcn@latest add separator     # Timeline dividers
npx shadcn@latest add avatar        # Team settings user avatars
npx shadcn@latest add tabs          # Settings page sections
npx shadcn@latest add dialog        # Confirmation modals in onboarding/settings
npx shadcn@latest add skeleton      # Loading states in feed/timeline
npx shadcn@latest add scroll-area   # Scrollable context feed with custom scrollbar
```

`command` uses `cmdk` (version ^1.1.1, already a Radix ecosystem dependency). The Command component provides the search-as-you-type context feed filter with keyboard navigation at zero additional npm cost.

**Confidence:** HIGH — all listed components are in the current shadcn/ui registry (verified 2026-03-04).

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `next-themes` | Overkill for a force-dark dashboard with no user toggle. Adds ThemeProvider, hydration SSR complexity, localStorage wiring. | Force dark with `.dark` class on layout root. |
| `@tanstack/react-virtual` | Context feed at MVP scale will have <500 items. Virtualization adds significant implementation complexity (fixed row heights or measured rows) for zero perceptible benefit at this data volume. | Native browser scroll + CSS `overflow-y: auto`. Revisit if feed exceeds 2000 items. |
| `framer-motion` | Renamed to `motion`. Using both in package.json is redundant. | `motion` (^12.34.5). |
| `@tanstack/react-query` | Supabase client already supports subscriptions and direct async calls. Adding TanStack Query before the app has caching problems is premature. The existing `useState` + `useEffect` + Supabase client pattern works and is already established in the codebase. | Supabase client + `useEffect`. Revisit when cache invalidation complexity grows. |
| `react-spring` | Heavier spring-physics library. motion already covers all animation needs with the same capabilities. | `motion` |
| `dayjs` | date-fns v4 already recommended. Two date libraries in the bundle is waste. | `date-fns` ^4.1.0 |
| `react-query` (v3 alias) | Old package name. Use `@tanstack/react-query` if/when added. | N/A |
| Full `zod` schema in `apps/web` via separate npm install if MCP already has it | pnpm workspace: `apps/web` and `packages/mcp-server` have separate `node_modules`. Add `zod` to `apps/web/package.json` explicitly. | `pnpm add zod --filter @contextos/web` |
| Icon libraries beyond lucide-react | Mixing Heroicons, Phosphor, etc. with lucide-react creates visual inconsistency and bundle bloat. | `lucide-react` (already installed). If a specific icon is missing, add it as an inline SVG. |
| CSS-in-JS (styled-components, emotion) | Not compatible with Next.js 15 Server Components. Already on Tailwind v4 — adding CSS-in-JS now would be a fundamental conflict. | Tailwind v4 + CSS custom properties. |

---

## Installation

```bash
# Add to apps/web — form libraries for onboarding wizard
pnpm add react-hook-form @hookform/resolvers zod --filter @contextos/web

# Add for animated step transitions and timeline entrance animations
pnpm add motion --filter @contextos/web

# Add for URL-synced context feed filters
pnpm add nuqs --filter @contextos/web

# Add for timestamp display in timeline and feed
pnpm add date-fns --filter @contextos/web

# Add for onboarding step state machine (evaluate after scoping 4+ steps)
pnpm add @stepperize/react --filter @contextos/web

# shadcn components (run from apps/web)
cd apps/web
npx shadcn@latest add progress command select badge separator avatar tabs dialog skeleton scroll-area
```

---

## Integration Points with Existing Stack

### Tailwind v4 + motion

motion's `animate` prop is CSS-property based and works alongside Tailwind classes. Use motion for JS-driven animations (step transitions, stagger sequences), keep Tailwind utilities + `tw-animate-css` for CSS-only states.

```tsx
// Pattern: motion for step transitions, Tailwind for state styling
import { motion, AnimatePresence } from 'motion/react'

<AnimatePresence mode="wait">
  <motion.div
    key={currentStep}
    initial={{ opacity: 0, x: 20 }}
    animate={{ opacity: 1, x: 0 }}
    exit={{ opacity: 0, x: -20 }}
    transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    className="rounded-xl border border-border bg-card p-6"
  >
    {stepContent}
  </motion.div>
</AnimatePresence>
```

### react-hook-form + @stepperize/react + zod

Decouple step navigation (stepperize) from form state (react-hook-form). Each step validates independently before advancing.

```tsx
// Pattern: validate current step before calling stepper.next()
const form = useForm({ resolver: zodResolver(combinedSchema), mode: 'onChange' })
const stepper = useStepper({ initialStep: 'workspace' })
const stepSchemas = { workspace: workspaceSchema, team: teamSchema, integrations: integrationsSchema }

async function handleNext() {
  const stepFields = getFieldsForStep(stepper.current.id)
  const valid = await form.trigger(stepFields) // validates only current step fields
  if (valid) stepper.next()
}
```

### nuqs + Supabase client (context feed)

nuqs manages URL filter state. Supabase client fetches on filter change. No TanStack Query layer needed.

```tsx
// Pattern: URL-synced filters driving Supabase fetch
const [type, setType] = useQueryState('type', parseAsString)
const [status, setStatus] = useQueryState('status', parseAsString)
const [search, setSearch] = useQueryState('q', parseAsString)

useEffect(() => {
  let query = supabase.from('context_pages').select('*').order('created_at', { ascending: false })
  if (type) query = query.eq('type', type)
  if (status) query = query.eq('status', status)
  if (search) query = query.ilike('title', `%${search}%`)
  query.then(({ data }) => setItems(data ?? []))
}, [type, status, search])
```

### Supabase Realtime (activity timeline)

No new library. Use existing `@supabase/supabase-js` channel API in a `'use client'` component with `useEffect` cleanup. The activity timeline subscribes to `postgres_changes` on `context_pages` (and `context_generation_jobs` for status updates).

```tsx
// Pattern: realtime subscription for activity timeline — uses existing installed @supabase/supabase-js
useEffect(() => {
  const channel = supabase
    .channel('activity-timeline')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'context_pages' },
      (payload) => setItems(prev => [payload.new, ...prev].slice(0, 50))
    )
    .subscribe()
  return () => { supabase.removeChannel(channel) }
}, [])
```

### Design Token Sharing (landing ↔ dashboard)

Shared teal brand values are defined once in `.dark` block of `globals.css`. Landing page continues to use its scoped `.landing-theme` class with the same hex values. When the dashboard is eventually opened alongside the landing page (same browser session, same Next.js app), there is no token conflict because landing tokens are scoped under `.landing-theme` and dashboard tokens are scoped under `.dark`.

---

## "Not Generic AI Slop" Design Decisions

These are non-code patterns that inform implementation decisions for the milestone:

### 1. Information Density Over Whitespace Theater
The existing dashboard is sparse. Developer tools (Linear, Vercel, Raycast) pack information. Target: context feed shows title + source + status + timestamp + 1-line preview in a single compact row (not a card with 80px of padding).

### 2. Mono Font for Data, Sans for Prose
Already established in design tokens. Enforce consistently: timestamps, IDs, counts, status codes → `font-mono` (JetBrains Mono). Labels, descriptions → `font-sans` (Inter). Never swap these.

### 3. Teal as a Signal, Not a Theme
Use `--brand-teal` only for actionable elements (active state indicators, primary CTA, progress fill, generation status pulse). Do not use it decoratively. Overuse is the AI slop signal.

### 4. Status as Dot + Label, Not a Badge Rainbow
Activity timeline status: `●` dot with semantic color + short label. Not pill badges with 5 different color variants. Three states: `bg-brand-teal` (ready), `bg-amber-500` (generating), `bg-red-500` (failed).

### 5. No Hero Illustrations or Empty State Art
Empty states should be functional: "No context pages yet — connect Linear to start" with a single action button. No SVG illustrations, no Lottie animations, no undraw.co artwork. These are the strongest signals of template-sourced UI.

### 6. Onboarding Progress: Steps Not Percentages
The onboarding wizard shows step numbers (1 of 3, 2 of 3) not a percentage bar. Developers understand discrete steps. The `<Progress>` component is used for context generation status (0–100% job completion), not for onboarding navigation.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| motion ^12.34.5 | tw-animate-css only | If wizard transitions are simple enter/fade with no layout animation. The existing tw-animate-css is sufficient for static page elements. Add motion only when you need AnimatePresence for unmounting or height:auto transitions. |
| @stepperize/react | Custom useState stepper | For <4 step wizards with no conditional branching, a simple `const [step, setStep] = useState(0)` with an array of step components is sufficient. @stepperize adds value when steps have metadata (titles, descriptions, validation state) and when steps can branch conditionally. |
| nuqs for URL filter state | useState (ephemeral) | If filters should NOT persist across navigation (e.g., a one-time modal filter). For the context feed, URL persistence is correct behavior. |
| date-fns | dayjs | If total bundle size becomes critical and you need only a few date operations. dayjs is 670 KB unpacked vs 22 MB for date-fns, but date-fns tree-shakes to only what's imported. At the current scale, the difference is negligible. |
| zod ^4.3.6 | zod ^3.x | Only if @hookform/resolvers <5.2.0 is pinned. Version 5.x automatically handles both Zod 3 and 4. Since we're installing fresh, go straight to Zod v4. |

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| react-hook-form ^7.71.2 | zod ^4.3.6 via @hookform/resolvers ^5.2.2 | resolvers v5.x added Zod v4 automatic runtime detection. Do not use resolvers <5.0.0 with Zod v4. |
| @hookform/resolvers ^5.2.2 | zod ^4.3.6 (and ^3.25.0+) | v5 uses `zod/v4/core` subpath import — requires zod >=3.25.0 for v3 OR any zod v4. |
| motion ^12.34.5 | React ^19.0.0 | Motion 12.x explicitly supports React 19. Import from `'motion/react'` not `'framer-motion'`. |
| nuqs ^2.8.9 | Next.js ^15.2.0 | nuqs v2 supports Next.js >=14.2.0 including 15.x App Router. Requires NuqsAdapter in layout. |
| @stepperize/react ^6.1.0 | React ^19.0.0 | No React version pinning issues — pure hooks and TypeScript. |
| date-fns ^4.1.0 | TypeScript ^5.7.0 | date-fns v4 ships with TypeScript types. No @types/date-fns needed. |
| shadcn Command (cmdk ^1.1.1) | React ^19.0.0 | cmdk v1.x requires React 18+. React 19 is compatible. |

---

## Stack Patterns by Variant

**If onboarding wizard has 3 steps or fewer with no conditional branching:**
- Skip `@stepperize/react`
- Use `const [step, setStep] = useState<'workspace' | 'team' | 'done'>('workspace')`
- Save the dependency

**If context feed needs real-time updates (items appearing as context generates):**
- No new library needed
- Use existing `@supabase/supabase-js` Realtime with `postgres_changes` on `context_pages` table
- Combine with nuqs filter state: filter stays in URL, new items pushed via WebSocket

**If team settings page requires complex multi-field updates:**
- Use react-hook-form already installed for onboarding — same instance pattern
- No additional state management library

**If auth page redesign requires animated transitions between login/magic-link modes:**
- Use motion's `AnimatePresence` (already added for onboarding)
- Single install, multiple use points across dashboard

**If context feed grows beyond 500 items:**
- Add `@tanstack/react-virtual` at that point
- Current MVP scope does not justify it

---

## Sources

- [npm registry: react-hook-form 7.71.2](https://www.npmjs.com/package/react-hook-form) — version verified 2026-03-04 (HIGH confidence)
- [npm registry: @hookform/resolvers 5.2.2](https://www.npmjs.com/package/@hookform/resolvers) — version verified 2026-03-04 (HIGH confidence)
- [npm registry: zod 4.3.6](https://www.npmjs.com/package/zod) — version verified 2026-03-04 (HIGH confidence)
- [npm registry: motion 12.34.5](https://www.npmjs.com/package/motion) — version verified 2026-03-04 (HIGH confidence)
- [npm registry: nuqs 2.8.9](https://www.npmjs.com/package/nuqs) — version verified 2026-03-04 (HIGH confidence)
- [npm registry: @stepperize/react 6.1.0](https://www.npmjs.com/package/@stepperize/react) — version verified 2026-03-04 (HIGH confidence)
- [npm registry: date-fns 4.1.0](https://www.npmjs.com/package/date-fns) — version verified 2026-03-04 (HIGH confidence)
- [npm registry: cmdk 1.1.1](https://www.npmjs.com/package/cmdk) — version verified 2026-03-04 (HIGH confidence)
- [shadcn/ui: React Hook Form docs](https://ui.shadcn.com/docs/forms/react-hook-form) — prescribed zodResolver pattern (HIGH confidence)
- [shadcn/ui: Command component](https://ui.shadcn.com/docs/components/radix/command) — cmdk-based search (HIGH confidence)
- [Zod v4 release notes](https://zod.dev/v4) — performance benchmarks, @zod/mini, versioning (HIGH confidence)
- [motion/react installation](https://motion.dev/docs/react-installation) — React 19 compatibility, AnimatePresence (HIGH confidence)
- [nuqs: Type-safe search params](https://nuqs.dev) — Next.js 15 App Router adapter (HIGH confidence)
- [Stepperize GitHub](https://github.com/damianricobelli/stepperize) — composable step state, shadcn integration (MEDIUM confidence)
- [Tailwind CSS v4 @theme docs](https://tailwindcss.com/docs/theme) — CSS-first design tokens, dark mode (HIGH confidence)
- [Supabase Realtime: Subscribing to DB changes](https://supabase.com/docs/guides/realtime/subscribing-to-database-changes) — postgres_changes pattern (HIGH confidence)
- [LogRocket: Best React animation libraries 2026](https://blog.logrocket.com/best-react-animation-libraries/) — motion recommendation, bundle comparison (MEDIUM confidence)
- [@hookform/resolvers + Zod v4 support thread](https://github.com/react-hook-form/resolvers/issues/799) — v5.x compatibility confirmation (HIGH confidence)

---
*Stack research for: ContextOS dashboard redesign milestone (onboarding, dark theme, context feed, activity timeline, team settings, auth redesign)*
*Researched: 2026-03-04*
