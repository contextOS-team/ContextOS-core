# Phase 13: Adopt Orchids Landing Page into apps/web - Context

**Gathered:** 2026-03-03
**Status:** Ready for planning

<domain>
## Phase Boundary

Bring the standalone Orchids landing page (10-section dark-themed marketing page) into the existing apps/web Next.js app as the public-facing marketing page at `/`. The dashboard app at `/dashboard` remains untouched. This is a waitlist-only landing page — no connection to the authenticated app yet.

</domain>

<decisions>
## Implementation Decisions

### Routing strategy
- Landing page lives at `/`, replacing the current redirect to `/dashboard`
- Dashboard stays at `/dashboard`, accessible directly but not linked from landing
- Single scrollable page with anchor links (#features, #how-it-works, #integrations)
- No "Sign In" or auth links on the landing page — waitlist only for now
- Waitlist form implementation deferred to a later decision

### Theme coexistence
- Route-based isolation: landing page gets its own `layout.tsx` with dark theme, dashboard keeps its existing layout
- Root layout stays minimal (fonts only, shared between both)
- Separate `landing.css` file imported only in the landing layout — no changes to dashboard CSS
- Remove `orchids-visual-edits` package and `<VisualEditsMessenger />` component

### Dependency reconciliation
- Rewrite all `@radix-ui/*` individual package imports to use the unified `radix-ui` package already in apps/web
- Do not add individual `@radix-ui/*` packages

### Content and copy
- Remove Testimonials section entirely (no real testimonials yet)
- Trust bar becomes "Integrates with" bar showing Linear, Slack, GitHub, Notion, Fathom logos (real integrations)
- Main CTA is waitlist email capture — no sign-up or sign-in links
- Nav contains anchor links to page sections + waitlist CTA only

### Claude's Discretion
- Whether to keep or replace framer-motion (weigh bundle size vs animation quality)
- Audit all Orchids dependencies (recharts, cmdk, embla-carousel, react-hook-form, zod) and strip anything not genuinely used by the landing page components
- Nav anchor link selection and ordering
- Footer content and links

</decisions>

<specifics>
## Specific Ideas

- User has `contextos.pro` and `app.contextos.pro` domains — future-ready for domain split (landing at root, dashboard at app subdomain) but not implementing that split now
- Trust bar should show actual integration logos (Linear, Slack, GitHub, Notion, Fathom) rather than fake company logos

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/web/src/app/layout.tsx`: Root layout with Inter + JetBrains Mono fonts, Sentry init — landing layout will sit alongside this
- `apps/web/src/middleware.ts`: Supabase session middleware — landing page should pass through without auth checks
- `apps/web/src/components/icons/`: Existing icon components that may include integration logos

### Established Patterns
- Next.js App Router with route groups: `(auth)` for login/signup, `dashboard/` for authenticated app
- Tailwind CSS v4 with `tw-animate-css` and shadcn/ui theme tokens
- `radix-ui` unified package (not individual `@radix-ui/*` packages)

### Integration Points
- `apps/web/src/app/page.tsx`: Currently redirects to `/dashboard` — will be replaced with landing page
- `apps/web/src/app/globals.css`: Dashboard theme — landing page should NOT modify this file
- Landing page components go in `apps/web/src/components/landing/` (new directory)
- Landing-specific CSS in `apps/web/src/app/landing.css` or similar, imported only by landing layout

### Source Codebase
- Orchids landing page at `orchids-contextos-landing-page-design/` with 10 section components:
  Nav, Hero, TrustBar, ProblemSection, HowItWorks, Features, ProductDemo, Testimonials (remove), Integrations, CTASection, Footer
- Orchids globals.css has teal brand vars, grain textures, glow utilities, custom animations
- Orchids uses `"use client"` on interactive components (Hero with scroll tracking)

</code_context>

<deferred>
## Deferred Ideas

- Unify dashboard theme to teal brand (future phase — rebrand dashboard to match landing aesthetic)
- Domain split: `contextos.pro` for landing, `app.contextos.pro` for dashboard (infrastructure change)
- Waitlist form backend implementation (Supabase table or external service)
- Auth links on landing page (add "Sign In" when app is ready for public access)

</deferred>

---

*Phase: 13-adopt-orchids-landing-page-into-apps-web*
*Context gathered: 2026-03-03*
