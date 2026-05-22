---
phase: 42-landing-positioning-and-seo-launch-rewrite
reviewed: 2026-05-22T17:41:35Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - apps/web/src/app/(landing)/layout.tsx
  - apps/web/src/app/(landing)/page.tsx
  - apps/web/src/components/landing/CTASection.tsx
  - apps/web/src/components/landing/DecisionReceiptVisual.tsx
  - apps/web/src/components/landing/Features.tsx
  - apps/web/src/components/landing/Footer.tsx
  - apps/web/src/components/landing/Hero.tsx
  - apps/web/src/components/landing/HowItWorks.tsx
  - apps/web/src/components/landing/Integrations.tsx
  - apps/web/src/components/landing/Nav.tsx
  - apps/web/src/components/landing/ProblemSection.tsx
  - apps/web/src/components/landing/ProductDemo.tsx
  - apps/web/src/components/landing/TrustBar.tsx
  - apps/web/src/components/landing/__tests__/booking-cta.test.tsx
  - apps/web/src/components/landing/__tests__/landing-claims.test.tsx
  - apps/web/src/components/landing/__tests__/landing-hero.test.tsx
  - apps/web/src/components/landing/__tests__/landing-metadata.test.ts
  - apps/web/src/components/landing/__tests__/landing-sections.test.tsx
  - apps/web/src/components/landing/booking.ts
  - apps/web/src/components/landing/index.ts
  - apps/web/src/components/landing/landing-copy.ts
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
status: issues_found
---

# Phase 42: Code Review Report

**Reviewed:** 2026-05-22T17:41:35Z
**Depth:** standard
**Files Reviewed:** 21
**Status:** issues_found

## Summary

Reviewed Phase 42 source changes from `origin/main..HEAD`, excluding planning artifacts and unrelated dirty dashboard/Remotion worktree edits. The latest 42-03 pivot does simplify the rendered page order, and the landing test suite plus typecheck pass, but the SEO launch rewrite has a production metadata gap that leaves old social metadata/image copy in place.

Verification run during review:

- `cd apps/web && npx vitest run src/components/landing/__tests__` - passed, 6 files and 12 tests.
- `cd apps/web && npm run typecheck` - passed.
- `git diff --check origin/main..HEAD -- . ':!.planning/'` - passed.

## Remediation

- CR-01 fixed in `9d32038` by making the landing title absolute, adding landing-scoped OpenGraph/Twitter metadata, and adding `apps/web/src/app/(landing)/opengraph-image.tsx`.
- WR-01 fixed in `9d32038` by adding a page-level landing composition test that renders `LandingPage`.
- WR-02 fixed in `9d32038` by removing placeholder legal/security footer links until real routes exist.

Post-fix verification:

- `cd apps/web && npx vitest run src/components/landing/__tests__` - passed, 6 files and 13 tests.
- `cd apps/web && npm run typecheck` - passed.
- `cd apps/web && npm run lint` - passed with unrelated existing warnings.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: [BLOCKER] Landing social metadata still ships the old positioning

**File:** `apps/web/src/app/(landing)/layout.tsx:7`

**Issue:** The Phase 42 landing metadata only replaces the raw `title` and `description`. In Next metadata resolution, a string child title is still passed through the parent title template, so the approved title can resolve as `ContextOS | AI Decision Tracking for Engineering Teams | ContextOS` instead of the exact `LANDING_SEO.title`. The landing layout also does not override `openGraph` or `twitter`, so the root metadata remains `ContextOS - AI-generated context for engineering tickets` with the old "Stop context-switching, start shipping" copy, and `apps/web/src/app/opengraph-image.tsx` still renders the old "AI-generated context for every engineering ticket" image. The current `landing-metadata.test.ts` imports the raw object and misses the resolved metadata/social-card output, so this can ship while tests stay green.

**Fix:**

```ts
export const metadata: Metadata = {
  title: { absolute: LANDING_SEO.title },
  description: LANDING_SEO.description,
  openGraph: {
    title: LANDING_SEO.title,
    description: LANDING_SEO.description,
    url: 'https://contextos.pro',
    siteName: 'ContextOS',
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: LANDING_SEO.title,
    description: LANDING_SEO.description,
  },
}
```

Also update or add a landing-scoped `opengraph-image.tsx`, and extend metadata tests to assert OpenGraph/Twitter/image copy so the old positioning cannot remain outside `components/landing`.

## Warnings

### WR-01: [WARNING] Demo-first page composition is not covered by the new section test

**File:** `apps/web/src/components/landing/__tests__/landing-sections.test.tsx:41`

**Issue:** The test name says it verifies the page is "without the old explainer stack", but the test renders only `<ProductDemo />` at line 42. If `apps/web/src/app/(landing)/page.tsx` later re-adds `TrustBar`, `ProblemSection`, `HowItWorks`, or `Features`, every new 42-03 landing test still passes. That leaves the core user-directed pivot - `Hero -> ProductDemo -> Integrations -> CTASection -> Footer` - unguarded.

**Fix:** Add a page-level test that renders `LandingPage` with the existing `useInView`, PostHog, and Cal mocks, then asserts the expected section anchors and absence of old explainer headings.

```tsx
import LandingPage from '@/app/(landing)/page'

render(<LandingPage />)

expect(document.getElementById('demo')).toBeTruthy()
expect(document.getElementById('integrations')).toBeTruthy()
expect(document.getElementById('booking')).toBeTruthy()
expect(screen.queryByText('The Problem')).toBeNull()
expect(screen.queryByText('How It Works')).toBeNull()
expect(screen.queryByText('Features')).toBeNull()
```

### WR-02: [WARNING] Footer exposes broken legal/security placeholder links

**File:** `apps/web/src/components/landing/Footer.tsx:68`

**Issue:** The simplified launch footer renders `Privacy`, `Terms`, and `Security` as real anchors with `href="#"`. Keyboard and screen-reader users encounter links that advertise navigation but only jump to the top/current fragment, and launch visitors cannot reach the legal or security pages implied by the labels.

**Fix:** Replace the placeholders with real routes before launch, or remove the links until those pages exist.

```tsx
{[
  { label: 'Privacy', href: '/privacy' },
  { label: 'Terms', href: '/terms' },
  { label: 'Security', href: '/security' },
].map((item) => (
  <a key={item.label} href={item.href} className="text-xs text-[#3D4450] hover:text-[#6B7280] transition-colors">
    {item.label}
  </a>
))}
```

---

_Reviewed: 2026-05-22T17:41:35Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
