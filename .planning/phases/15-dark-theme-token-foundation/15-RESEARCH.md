# Phase 15: Dark Theme Token Foundation - Research

**Researched:** 2026-03-04
**Domain:** CSS design tokens, dark mode theming, Tailwind CSS v4, OKLCH color space, Radix UI portals, skeleton loading
**Confidence:** HIGH

## Summary

Phase 15 transforms the dashboard and auth surfaces from light/unstyled to a brand-tinted dark theme. The existing codebase is well-prepared: Tailwind v4 with `@custom-variant dark` is already configured, OKLCH tokens exist in `.dark {}` block, JetBrains Mono is loaded as `--font-mono`, and all dashboard components use semantic token classes (`bg-background`, `text-foreground`, etc.) that will auto-switch when `.dark` is applied to `<html>`.

The work divides into five pillars: (1) token expansion -- shift primary from blue-indigo hue 250 to teal hue 170 and add 4-level surface hierarchy; (2) DarkModeApplier -- a client component that adds `.dark` to `<html>` so Radix portals inherit dark tokens; (3) navigation restructure -- add Activity link, move Settings/Sign-out to avatar dropdown, switch active state to teal underline; (4) typography application -- apply `font-mono` to data identifiers and monospace uppercase tracking to section labels; (5) skeleton primitives -- shimmer-sweep `<Skeleton>` component replacing `animate-pulse` throughout.

**Primary recommendation:** This is entirely CSS + component work. No new dependencies are needed. The unified `radix-ui` v1.4.3 package already includes DropdownMenu for the avatar menu. All animations (DS-06 spring curves, DS-09 shimmer) can be CSS-only using `cubic-bezier()` with overshoot and `@keyframes` gradient sweep. Do not add Framer Motion or next-themes.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Keep blue-violet surface tint (hue 270) -- already non-generic, professional for daily use
- Primary color shifts from blue-indigo (hue 250) to teal (~hue 170) to match the landing page brand (#00D4AA)
- Teal used ONLY on actionable/status elements (DS-02) -- never as surface decoration
- 4-level surface hierarchy: background -> card -> elevated -> overlay with subtle lightness steps (~0.03-0.05 OKLCH apart) -- layers felt more than seen, depth reinforced by borders + shadows
- Must feel premium -- not neutral gray shadcn defaults, not flashy
- JetBrains Mono already loaded as --font-mono -- apply to all data identifiers (ticket IDs, timestamps, counts, API keys) per DS-03
- Monospace uppercase tracking pattern (from landing page) used on section labels ONLY -- sparingly applied as a signature element, not broadly
- Keep horizontal top bar (not vertical sidebar) -- 4 content links: Home, Context, Activity, Integrations
- Settings and Sign out live in an avatar dropdown menu (not in the main nav row)
- Active state: teal underline only, no background highlight -- clean and minimal like Vercel's nav
- Wordmark gets teal gradient treatment + logo matching the landing page
- Shimmer sweep animation (gradient sweeps left-to-right) -- premium feel, not pulse/fade
- One reusable `<Skeleton>` primitive component -- pages compose their own skeleton layouts from it
- Every dashboard page must have a structured skeleton matching its populated layout shape (DS-09)
- Dashboard grain more subtle than landing page (~0.8-1% opacity vs landing's 1.5%)
- Daily-use surface should have barely perceptible texture -- just enough for depth

### Claude's Discretion
- Animation approach: CSS-only (extend existing stagger-children) vs Framer Motion -- pick based on what DS-06 spring-curve requirements actually need
- Grain placement: main background only vs all surfaces -- pick what creates the best premium feel
- Loading skeleton exact dimensions and spacing
- DarkModeApplier implementation strategy (must apply .dark to html for Radix portals without breaking .landing-theme scoping)
- Exact OKLCH values for the 4 surface levels
- Error state styling

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DS-01 | Dashboard renders in dark mode by default with brand-tinted OKLCH tokens | DarkModeApplier component + expanded .dark token block with hue-270 surfaces and teal primary |
| DS-02 | Teal (#00D4AA) used only on actionable/status elements | Token design: --primary shifts to teal (~hue 170), used only in interactive/status contexts |
| DS-03 | JetBrains Mono applied to all data identifiers | Typography utility class `.font-mono` already available; apply to ticket IDs, timestamps, counts, API keys |
| DS-04 | 4-level surface hierarchy (background -> card -> elevated -> overlay) | New OKLCH tokens with ~0.03-0.05 lightness steps; add --elevated and --overlay CSS custom properties |
| DS-05 | Radix UI portals render correctly in dark mode | DarkModeApplier adds .dark to html element; portals render to document.body which is child of html |
| DS-06 | Spring-curve microinteractions on list items, status changes, completion | CSS-only approach: cubic-bezier with overshoot values + existing stagger-children pattern |
| DS-07 | Subtle grain texture on dashboard surfaces | Reuse existing noise-bg pattern at reduced opacity (~0.008-0.01 vs landing's 0.025) |
| DS-08 | Section labels use monospace uppercase tracking | CSS utility class matching landing .section-label pattern (font-mono, uppercase, tracking-[0.15em]) |
| DS-09 | All dashboard pages render structured skeleton loading states | Shimmer-sweep Skeleton primitive component; compose page-specific skeleton layouts |
| NAV-01 | Dashboard navigation restructured with all sections and active states | Add Activity link, move Settings/Sign-out to DropdownMenu avatar, teal underline active state |
</phase_requirements>

## Standard Stack

### Core (already installed -- no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Tailwind CSS | v4.0 | Utility CSS framework | Already configured with @custom-variant dark, OKLCH tokens, CSS-first config |
| radix-ui | v1.4.3 | Accessible UI primitives | Unified package already installed; includes DropdownMenu, Dialog, Sheet needed for nav |
| shadcn/ui | v3.8.5 (CLI) | Component primitives | Already configured (new-york style); add dropdown-menu, sheet components via CLI |
| lucide-react | v0.469.0 | Icons | Already in use throughout dashboard |
| class-variance-authority | v0.7.1 | Variant-based component styling | Already used in Button component |
| clsx + tailwind-merge | v2.1.1 / v2.6.0 | Class merging | Already used via cn() utility |

### Supporting (no new installs needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| next/font/google | built-in | Font loading | JetBrains Mono already loaded via this |
| tw-animate-css | v1.4.0 | Animation utilities | Already installed as devDependency |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| CSS-only animations | Framer Motion | FM adds ~30KB, requires React context, main-thread JS. CSS handles stagger + spring-curve via cubic-bezier overshoot. **Recommendation: stay CSS-only** (see DS-06 analysis below) |
| Manual DarkModeApplier | next-themes | next-themes is explicitly out of scope per REQUIREMENTS.md. Manual is simpler for dark-only (no toggle needed) |
| Custom skeleton | react-loading-skeleton | Extra dependency for something achievable with a single CSS keyframe + one component |

**Installation (new shadcn components only):**
```bash
cd apps/web
npx shadcn@latest add dropdown-menu
```

## Architecture Patterns

### Recommended Project Structure
```
apps/web/src/
  app/
    layout.tsx                    # Root layout -- add DarkModeApplier here
    globals.css                   # Token definitions, animations, utility classes
    dashboard/
      layout.tsx                  # Dashboard layout -- grain overlay applied here
      sidebar.tsx                 # RENAME/REFACTOR: becomes nav-bar.tsx or stays but is restructured
      page.tsx                    # Home -- update skeleton to shimmer
      context/page.tsx            # Context -- update skeleton to shimmer
      integrations/page.tsx       # Integrations -- update skeleton to shimmer
  components/
    ui/
      skeleton.tsx                # NEW: Shimmer skeleton primitive
      dropdown-menu.tsx           # NEW: Added via shadcn CLI for avatar menu
    dashboard/
      dark-mode-applier.tsx       # NEW: Client component to apply .dark class
      nav-bar.tsx                 # NEW or refactored from sidebar.tsx
```

### Pattern 1: DarkModeApplier (Client Component)
**What:** A minimal client component that adds `.dark` class to `<html>` on mount.
**When to use:** In root layout, renders nothing visible -- just a side-effect component.
**Why not in layout.tsx directly:** Root layout is a Server Component; `document` access requires client component.
**Example:**
```typescript
// Source: Standard Next.js pattern for class-based dark mode without next-themes
'use client'

import { useEffect } from 'react'

export function DarkModeApplier() {
  useEffect(() => {
    document.documentElement.classList.add('dark')
    return () => {
      document.documentElement.classList.remove('dark')
    }
  }, [])

  return null
}
```

**Critical detail:** Since `<html>` in root layout already has font variable classes (`${inter.variable} ${jetbrainsMono.variable}`), DarkModeApplier must ADD to existing classes, not replace them. `classList.add('dark')` does this correctly.

**Landing page coexistence:** The landing page uses `.landing-theme` class scoping (on a child div, not html). Adding `.dark` to html will NOT break landing styles because:
1. Landing CSS uses `.landing-theme` selector scoping (overrides shadcn vars within that scope)
2. Landing layout also sets inline `<style>html, body { background-color: #0A0A0F !important; }</style>`
3. The `.dark` token values will be active globally, but landing components use their own scoped variables

**FOUC prevention:** For a dark-only app (no toggle), add a `<script>` in the `<head>` to set the class before paint:
```typescript
// In root layout.tsx, add to <head>:
<script dangerouslySetInnerHTML={{
  __html: `document.documentElement.classList.add('dark')`
}} />
```
This prevents the flash of light theme on initial load.

### Pattern 2: OKLCH Token Hierarchy
**What:** 4-level surface tokens using OKLCH with blue-violet hue (270) and teal primary (170).
**When to use:** All `.dark {}` token definitions in globals.css.
**Example:**
```css
/* Source: Derived from existing .dark block + CONTEXT.md decisions */
.dark {
  /* 4-level surface hierarchy (hue 270 blue-violet) */
  /* ~0.03-0.05 lightness steps apart */
  --background: oklch(0.13 0.015 270);     /* Level 1: page background */
  --card: oklch(0.16 0.02 270);             /* Level 2: card surfaces */
  --elevated: oklch(0.19 0.02 270);         /* Level 3: elevated panels, popovers */
  --overlay: oklch(0.22 0.02 270);          /* Level 4: overlays, modals */

  /* Teal primary (hue ~170, matching #00D4AA) */
  --primary: oklch(0.75 0.18 170);
  --primary-foreground: oklch(0.13 0.015 270);

  /* Ring/focus uses teal too */
  --ring: oklch(0.75 0.18 170);

  /* Popover inherits elevated level */
  --popover: oklch(0.19 0.02 270);
  --popover-foreground: oklch(0.93 0.005 260);

  /* Borders: subtle, just visible */
  --border: oklch(0.26 0.015 270);
  --input: oklch(0.22 0.02 270);

  /* Text hierarchy */
  --foreground: oklch(0.93 0.005 260);
  --muted-foreground: oklch(0.55 0.02 260);

  /* Secondary/muted use surface level 3 */
  --secondary: oklch(0.19 0.02 270);
  --secondary-foreground: oklch(0.93 0.005 260);
  --muted: oklch(0.19 0.02 270);
  --accent: oklch(0.19 0.025 270);
  --accent-foreground: oklch(0.93 0.005 260);
}
```

**Note on exact values:** The OKLCH lightness values above are starting points. Fine-tune by visual inspection. The key constraints are:
- Hue 270 (blue-violet) for ALL surface tokens
- ~0.03-0.05 lightness increments between levels
- Teal primary at approximately oklch(0.75 0.18 170) to match #00D4AA
- Chroma kept LOW on surfaces (0.015-0.025) -- brand tint should be "felt more than seen"

### Pattern 3: Shimmer Skeleton
**What:** CSS-only shimmer animation using a gradient sweep.
**When to use:** All loading states across dashboard pages.
**Example:**
```css
/* Source: Standard CSS shimmer pattern */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton-shimmer {
  background: linear-gradient(
    90deg,
    var(--muted) 0%,
    oklch(0.25 0.02 270) 50%,
    var(--muted) 100%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  border-radius: var(--radius);
}
```

```typescript
// Skeleton.tsx component
import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn(
        "skeleton-shimmer rounded-md",
        className
      )}
      {...props}
    />
  )
}

export { Skeleton }
```

### Pattern 4: Section Label Typography
**What:** Monospace uppercase tracking pattern from landing page, applied to dashboard section labels.
**When to use:** Any section heading that acts as a category label (e.g., "Integrations", "Recent Activity").
**Example:**
```typescript
// Utility class approach (in globals.css)
// .section-label already exists in landing.css -- move pattern to globals.css
// or create a Tailwind utility class

// Usage in components:
<h3 className="font-mono text-xs uppercase tracking-[0.15em] text-muted-foreground">
  Integrations
</h3>
```

### Pattern 5: Spring-Curve CSS Animations (DS-06)
**What:** Cubic-bezier with overshoot for spring-like microinteractions.
**When to use:** List item appearance (stagger), status changes, completion states.
**Example:**
```css
/* Spring-curve easing (overshoot then settle) */
/* cubic-bezier(0.34, 1.56, 0.64, 1) -- standard spring overshoot */

.spring-in {
  animation: spring-fade-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

@keyframes spring-fade-in {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* Update existing stagger-children to use spring curve */
.stagger-children > * {
  animation: spring-fade-in 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}
```

### Anti-Patterns to Avoid
- **Using `dark:` prefix on the html element itself:** The current `@custom-variant dark (&:is(.dark *))` targets children of `.dark` only. Styles on the `.dark` element itself (like html) won't get dark variants applied. Consider updating to `(&:where(.dark, .dark *))` per official Tailwind v4 docs.
- **Hardcoded hex colors in components:** All colors must come from semantic tokens. Search for and replace any remaining hardcoded values like `bg-emerald-500` or `text-violet-600` in dashboard components.
- **Using animate-pulse for loading states:** Replace all existing `animate-pulse` with shimmer skeleton component for visual consistency.
- **Grain texture on all surfaces:** Too much grain causes visual fatigue on daily-use tools. Apply grain only to the main background layer, not on cards or elevated surfaces.
- **Teal on decorative elements:** Per DS-02, teal is for actionable/status ONLY. Never use it for borders, backgrounds, or decorative elements on the dashboard.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dropdown menu | Custom dropdown with useState | `npx shadcn@latest add dropdown-menu` | Keyboard navigation, focus management, portal rendering, accessibility (ARIA) |
| Color manipulation | JavaScript color conversion | OKLCH directly in CSS | Browser-native, no runtime cost, perceptually uniform |
| Theme toggle | Custom ThemeProvider context | DarkModeApplier (dark-only, no toggle) | App is dark-only per requirements; no user preference to manage |
| Accessible focus rings | Custom focus styles | Existing shadcn focus-visible patterns | Already configured in button.tsx and globals.css |
| Stacking context for portals | Custom z-index management | Radix Portal (renders to document.body) | Handles stacking automatically; dark class on html propagates |

**Key insight:** This phase is almost entirely CSS token work + one client component + navigation restructure. The existing stack handles everything. Zero new production dependencies needed.

## Common Pitfalls

### Pitfall 1: Flash of Light Theme (FOUC)
**What goes wrong:** Page renders with light (default) theme tokens for a split second before DarkModeApplier runs `classList.add('dark')`.
**Why it happens:** Client components hydrate after initial server render. The html element doesn't have `.dark` during SSR.
**How to avoid:** Add a blocking `<script>` tag in the root layout `<head>` that sets `document.documentElement.classList.add('dark')` before any paint occurs. This runs synchronously before React hydration.
**Warning signs:** White flash on page load/navigation, especially on slower connections.

### Pitfall 2: Landing Page Style Collision
**What goes wrong:** Adding `.dark` to html causes landing page to inherit dashboard dark tokens instead of its own `.landing-theme` scoped values.
**Why it happens:** Both `.dark` and `.landing-theme` define the same CSS custom property names (--background, --foreground, etc.).
**How to avoid:** The landing page's `.landing-theme` class defines its own overrides on a child div, which has higher specificity than `.dark` on html for elements inside that div. Verify by inspection that `.landing-theme` variables still win. The landing layout's inline `<style>` tag for html/body background also uses `!important`.
**Warning signs:** Landing page colors shift subtly when `.dark` is added to html.

### Pitfall 3: @custom-variant Selector Mismatch
**What goes wrong:** Current code uses `@custom-variant dark (&:is(.dark *))` which has two issues: (a) `:is()` has higher specificity than `:where()`, making overrides harder; (b) `.dark *` only targets CHILDREN, not the element with `.dark` class itself.
**Why it happens:** Likely generated from an older shadcn/Tailwind v4 template.
**How to avoid:** Update to the official recommended syntax: `@custom-variant dark (&:where(.dark, .dark *))`. This uses zero-specificity `:where()` and targets both the `.dark` element and its descendants.
**Warning signs:** `dark:` utilities not applying to direct properties on the html or body element.

### Pitfall 4: Radix Portal Not Inheriting Dark Tokens
**What goes wrong:** Dialog, DropdownMenu, or Sheet content renders with light theme.
**Why it happens:** Radix primitives portal content to `document.body` by default. If `.dark` is on a wrapper div instead of `<html>`, portaled content won't inherit.
**How to avoid:** DarkModeApplier MUST add `.dark` to `document.documentElement` (the `<html>` element), NOT to body or a wrapper div. Since `<body>` is a child of `<html>`, and Radix portals to `<body>`, all portaled content will be inside `.dark *`.
**Warning signs:** Dropdown menus or dialogs appearing with white/light backgrounds.

### Pitfall 5: Hardcoded Colors in Existing Components
**What goes wrong:** Some dashboard components use hardcoded Tailwind colors (e.g., `bg-emerald-500`, `text-violet-600`, `bg-green-500`) that don't respond to theme tokens.
**Why it happens:** Original components were built without a dark theme in mind.
**How to avoid:** Audit all dashboard components. Replace hardcoded colors with semantic tokens. Status indicators (connected = green, error = red) can keep hardcoded colors since they're semantic by nature, but verify they look good on dark backgrounds.
**Warning signs:** Bright, unstyled color patches that feel out-of-place in the dark theme.

### Pitfall 6: Shimmer Animation Performance
**What goes wrong:** Shimmer animation causes jank on pages with many skeleton elements.
**Why it happens:** Each skeleton element runs its own independent gradient animation, causing layout thrashing.
**How to avoid:** Use `background-attachment: fixed` on the shimmer gradient so all skeletons share the same viewport-relative gradient sweep. This creates visual coherence and reduces rendering work.
**Warning signs:** Stuttering or flickering during skeleton loading states.

## Code Examples

### DarkModeApplier with FOUC Prevention
```typescript
// apps/web/src/components/dashboard/dark-mode-applier.tsx
'use client'

import { useEffect } from 'react'

/**
 * Applies .dark class to <html> for Tailwind dark mode.
 * Dashboard is dark-only (no toggle).
 *
 * FOUC prevention: pair with inline <script> in root layout:
 * <script dangerouslySetInnerHTML={{ __html: `document.documentElement.classList.add('dark')` }} />
 */
export function DarkModeApplier() {
  useEffect(() => {
    // Ensure .dark is present (the inline script handles pre-hydration,
    // this handles any edge cases during client navigation)
    document.documentElement.classList.add('dark')
  }, [])

  return null
}
```

### Root Layout Integration
```typescript
// apps/web/src/app/layout.tsx -- modified
import { DarkModeApplier } from '@/components/dashboard/dark-mode-applier'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{
          __html: `document.documentElement.classList.add('dark')`
        }} />
      </head>
      <body className="font-sans antialiased">
        <SentryInit />
        <DarkModeApplier />
        {children}
      </body>
    </html>
  )
}
```

### Expanded Dark Token Block
```css
/* globals.css -- expanded .dark block */
.dark {
  /* === 4-level surface hierarchy (hue 270, blue-violet tint) === */
  --background: oklch(0.13 0.015 270);     /* L1: page bg */
  --card: oklch(0.16 0.02 270);            /* L2: cards */
  --elevated: oklch(0.19 0.02 270);        /* L3: elevated panels */
  --overlay: oklch(0.22 0.025 270);        /* L4: modals/overlays */

  --card-foreground: oklch(0.93 0.005 260);
  --popover: var(--elevated);
  --popover-foreground: oklch(0.93 0.005 260);
  --foreground: oklch(0.93 0.005 260);

  /* === Teal primary (matching #00D4AA brand) === */
  --primary: oklch(0.75 0.18 170);
  --primary-foreground: oklch(0.15 0.015 270);

  /* === Supporting tokens === */
  --secondary: var(--elevated);
  --secondary-foreground: oklch(0.93 0.005 260);
  --muted: var(--elevated);
  --muted-foreground: oklch(0.55 0.02 260);
  --accent: oklch(0.20 0.025 270);
  --accent-foreground: oklch(0.93 0.005 260);
  --destructive: oklch(0.65 0.2 25);

  /* === Borders === */
  --border: oklch(0.26 0.015 270);
  --input: oklch(0.22 0.02 270);
  --ring: oklch(0.75 0.18 170);

  /* === Sidebar tokens (nav bar) === */
  --sidebar: oklch(0.13 0.015 270);
  --sidebar-foreground: oklch(0.92 0.01 260);
  --sidebar-primary: oklch(0.75 0.18 170);
  --sidebar-primary-foreground: oklch(0.15 0.015 270);
  --sidebar-accent: oklch(0.19 0.025 270);
  --sidebar-accent-foreground: oklch(0.93 0.005 260);
  --sidebar-border: oklch(0.26 0.015 270);
  --sidebar-ring: oklch(0.75 0.18 170);
}
```

### Navigation Bar with Avatar Dropdown
```typescript
// Conceptual structure for restructured nav
const navItems = [
  { href: '/dashboard', label: 'Home' },
  { href: '/dashboard/context', label: 'Context' },
  { href: '/dashboard/activity', label: 'Activity' },       // NEW
  { href: '/dashboard/integrations', label: 'Integrations' },
]

// Active state: teal underline, no bg highlight
{active && (
  <span className="absolute bottom-0 left-3 right-3 h-[2px] rounded-full"
    style={{ backgroundColor: 'oklch(0.75 0.18 170)' }}
  />
)}

// Avatar dropdown (replaces inline Sign Out button)
<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <button className="h-7 w-7 rounded-full bg-primary/10 ...">
      {initials}
    </button>
  </DropdownMenuTrigger>
  <DropdownMenuContent align="end">
    <DropdownMenuItem>Settings</DropdownMenuItem>
    <DropdownMenuSeparator />
    <DropdownMenuItem onClick={handleSignOut}>Sign out</DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```

### Shimmer Skeleton Component
```typescript
// apps/web/src/components/ui/skeleton.tsx
import { cn } from "@/lib/utils"

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("skeleton-shimmer rounded-md", className)}
      {...props}
    />
  )
}

export { Skeleton }
```

```css
/* In globals.css */
@keyframes shimmer-sweep {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.skeleton-shimmer {
  background: linear-gradient(
    90deg,
    oklch(0.19 0.02 270) 0%,
    oklch(0.24 0.02 270) 50%,
    oklch(0.19 0.02 270) 100%
  );
  background-size: 200% 100%;
  animation: shimmer-sweep 1.5s ease-in-out infinite;
}
```

### Grain Texture (Dashboard-Specific)
```css
/* Dashboard grain -- more subtle than landing (0.008-0.01 opacity vs 0.025) */
.dashboard-grain::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  opacity: 0.008;
  background-image: url("data:image/svg+xml,..."); /* same SVG as landing */
  background-repeat: repeat;
  background-size: 200px 200px;
}
```

## DS-06 Animation Decision (Claude's Discretion)

**Recommendation: CSS-only. Do NOT add Framer Motion.**

Rationale:
1. DS-06 requires spring-curve microinteractions on: (a) list item stagger appearance, (b) status changes, (c) completion states
2. The existing `stagger-children` CSS class already handles stagger. Updating its `cubic-bezier()` to include overshoot (`cubic-bezier(0.34, 1.56, 0.64, 1)`) creates a spring feel
3. Status changes and completion states need simple scale/opacity transitions that CSS handles natively
4. Framer Motion would add ~30KB (gzipped) for marginal benefit on these specific use cases
5. The CSS `linear()` easing function is supported in all major browsers (Chrome 113+, Firefox 112+, Safari 17.2+) and can create more complex spring curves if needed
6. The project is a desktop-first internal tool -- the sophisticated physics simulation Framer Motion excels at is not needed here

**Grain Placement Recommendation:** Main background only. Cards and elevated surfaces should be clean. The grain on the background layer creates subtle depth differentiation; adding it to cards makes the interface feel noisy on daily use.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| HSL color tokens | OKLCH color tokens | Tailwind v4 (Jan 2025) | Perceptually uniform lightness, better for dark theme consistency |
| tailwind.config.js darkMode: 'class' | @custom-variant dark in CSS | Tailwind v4 | CSS-first, no config file needed |
| Individual @radix-ui/* packages | Unified `radix-ui` package | Radix v1.0 (2024) | Single import, smaller bundle |
| react-loading-skeleton library | CSS-only shimmer with @keyframes | 2024-2025 trend | Zero dependencies, better perf |
| next-themes for dark mode | Script-based dark class + DarkModeApplier | When dark-only (no toggle) | Simpler, no hydration mismatch |

**Deprecated/outdated:**
- `tailwind.config.js` for theme configuration -- Tailwind v4 is CSS-first, no config file
- Individual `@radix-ui/react-*` packages -- use unified `radix-ui` package
- `animate-pulse` for loading -- shimmer sweep is the modern premium pattern

## @custom-variant Fix Required

**Current (problematic):**
```css
@custom-variant dark (&:is(.dark *));
```

**Recommended (per official Tailwind v4 docs):**
```css
@custom-variant dark (&:where(.dark, .dark *));
```

**Why:**
1. `:is()` has the specificity of its most specific argument, making overrides harder. `:where()` has zero specificity.
2. `.dark *` only targets descendants. The `.dark` element itself (html) won't get `dark:` utilities. Adding `.dark` to the selector fixes this.

This should be updated as part of the token work.

## Open Questions

1. **Exact OKLCH values for teal primary**
   - What we know: Landing page uses #00D4AA which converts to approximately `oklch(0.79 0.16 171)`
   - What's unclear: Whether the landing page's exact value works well as a primary button color on dark surfaces (contrast ratio for text)
   - Recommendation: Start with `oklch(0.75 0.18 170)`, verify WCAG contrast against both `--primary-foreground` (dark) and white text, adjust lightness if needed

2. **Activity page route**
   - What we know: NAV-01 requires Activity link in navigation
   - What's unclear: Whether `/dashboard/activity` page exists or needs a placeholder
   - Recommendation: Create a minimal placeholder page (`page.tsx` with skeleton) since Phase 18 builds the actual activity timeline. The nav link should work now; the page content comes later.

3. **Auth page dark styling scope**
   - What we know: Auth pages (`/login`, `/signup`) use the root layout but not the dashboard layout
   - What's unclear: Whether auth pages should get dark styling in THIS phase or Phase 16 (AUTH-01, AUTH-02 are Phase 16)
   - Recommendation: Auth pages will automatically inherit dark tokens once DarkModeApplier adds `.dark` to html. No extra work needed in this phase. Phase 16 handles the redesign.

## Sources

### Primary (HIGH confidence)
- Tailwind CSS v4 official docs: dark mode `@custom-variant` syntax -- [tailwindcss.com/docs/dark-mode](https://tailwindcss.com/docs/dark-mode)
- Radix UI Portal docs: renders to `document.body` by default -- [radix-ui.com/primitives/docs/utilities/portal](https://www.radix-ui.com/primitives/docs/utilities/portal)
- Can I Use: CSS `linear()` easing function browser support (Chrome 113+, Safari 17.2+, Firefox 112+) -- [caniuse.com](https://caniuse.com/mdn-css_types_easing-function_linear-function)
- Codebase inspection: globals.css, layout.tsx, sidebar.tsx, landing.css, package.json -- all read directly

### Secondary (MEDIUM confidence)
- OKLCH color space guide for dark theme tokens -- [oklch.org/posts/ultimate-oklch-guide](https://oklch.org/posts/ultimate-oklch-guide)
- Josh Comeau: Springs and Bounces in Native CSS with linear() -- [joshwcomeau.com](https://www.joshwcomeau.com/animation/linear-timing-function/)
- Evil Martians: OKLCH in CSS -- [evilmartians.com](https://evilmartians.com/chronicles/oklch-in-css-why-quit-rgb-hsl)
- BoldVanta: Designing Luminance-First Color Systems with OKLCH -- [boldvanta.com](https://www.boldvanta.com/design/designing-luminance-cefirst-color-systems-with-oklch-tokens-ramps-and-real-ceworld-pitfalls.html)

### Tertiary (LOW confidence)
- None -- all findings verified with primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- verified via package.json, no new deps needed
- Architecture: HIGH -- patterns derived from existing codebase structure and official docs
- Token values: MEDIUM -- OKLCH values are starting points; exact visual tuning required during implementation
- Pitfalls: HIGH -- verified via codebase inspection and official docs
- Animation approach: HIGH -- CSS browser support verified via Can I Use

**Research date:** 2026-03-04
**Valid until:** 2026-04-04 (30 days -- stable domain, no fast-moving dependencies)
