---
phase: 42
slug: landing-positioning-and-seo-launch-rewrite
status: complete
created: 2026-05-22
---

# Phase 42 - Pattern Map

This map links each planned landing rewrite target to the closest existing analogs in the codebase.

## Target Files And Existing Analogs

| Planned File | Role | Closest Existing Analog | Pattern To Reuse |
|--------------|------|-------------------------|------------------|
| `apps/web/src/components/landing/landing-copy.ts` | Shared launch copy and metadata constants | `apps/web/src/components/landing/booking.ts` | Keep landing constants in a small server-safe module with plain string exports. |
| `apps/web/src/app/(landing)/layout.tsx` | Next metadata source | current `apps/web/src/app/(landing)/layout.tsx` | Export typed `Metadata`; import only server-safe constants; keep `PostHogProvider` and `landing.css` import unchanged. |
| `apps/web/src/components/landing/booking.ts` | Booking CTA target and labels | current `booking.ts` | Keep `BOOKING_SECTION_ID`, `BOOKING_SECTION_HREF`, `CAL_BOOKING_LINK`, and `CAL_BOOKING_LAYOUT` stable; update CTA label only. |
| `apps/web/src/components/landing/Hero.tsx` | First viewport copy, CTAs, product proof visual | current `Hero.tsx` | Preserve PostHog CTA capture and progressive entrance motion; replace ticket-first Remotion visual with an inspectable Decision Receipt visual. |
| `apps/web/src/components/landing/DecisionReceiptVisual.tsx` | New hero proof primitive | `Features.tsx` `DecisionMockup` and `GraphMockup` | Use inline React/SVG and landing theme colors; keep the graph to 4-6 readable nodes; avoid a large decorative network. |
| `apps/web/src/components/landing/ProblemSection.tsx` | Pain narrative | current before/after structure | Keep asymmetric section structure and before/after framing; replace time metrics and coding bottleneck with lost-decision questions. |
| `apps/web/src/components/landing/HowItWorks.tsx` | Workflow explanation | current three-step layout | Keep alternating step layout; rewrite steps to tools -> decisions -> sources -> graph/context. Remove "AI synthesis complete" as a vague claim. |
| `apps/web/src/components/landing/Features.tsx` | Capability proof cards | current bento grid | Elevate `Decision tracking`, `Knowledge graph`, and source-backed receipts; soften/remove unsupported trust copy. |
| `apps/web/src/components/landing/ProductDemo.tsx` | Product proof / sample trail | current browser-frame mockup | Replace "demo video coming soon" with crawlable sample decision trail content. |
| `apps/web/src/components/landing/Integrations.tsx` | Supported source surfaces | current integrations grid | Keep the 8 live integrations shown now; do not introduce count-based 9-integration claims unless Slack Huddles is represented separately. |
| `apps/web/src/components/landing/TrustBar.tsx` | Above-fold integration trust strip | current `TrustBar.tsx` and `Integrations.tsx` | Include GitLab and Fathom if the page foregrounds them elsewhere, or avoid count claims. |
| `apps/web/src/components/landing/CTASection.tsx` | Booking conversion section | current inline Cal.com section | Keep the Cal embed; change surrounding copy to promise seeing the buyer's decision graph from their own workspace. |
| `apps/web/src/components/landing/Footer.tsx` | Final brand positioning | current footer | Replace ticket-only "context pages" copy with decision-memory positioning. |
| `apps/web/src/components/landing/__tests__/*.test.*` | Regression coverage | `booking-cta.test.tsx`, `remotion-player.test.tsx` | Mock PostHog, `next/dynamic`, `useInView`, and Cal embed the same way existing landing tests do. |

## Important Existing Contracts

### Booking Constants

`booking.ts` is already the single source of truth for the booking anchor and Cal embed:

```ts
export const BOOKING_SECTION_ID = "booking";
export const BOOKING_SECTION_HREF = `#${BOOKING_SECTION_ID}`;
export const BOOKING_CTA_LABEL = "Book a Call";
export const CAL_BOOKING_LINK = "daulet";
export const CAL_BOOKING_LAYOUT = "month_view";
```

Plan 42 should keep the anchor and Cal config stable, while changing `BOOKING_CTA_LABEL` to `See your decision graph`.

### Landing Metadata

The current landing metadata is ticket/productivity-first:

```ts
export const metadata: Metadata = {
  title: 'ContextOS - Stop gathering context. Start shipping code.',
  description:
    'Engineers waste 2-6 hours per ticket hunting through Slack, Notion, and meeting notes. ContextOS auto-generates everything you need to know - before you write a single line.',
}
```

The plan should replace it with the approved SEO title and description from `42-UI-SPEC.md`.

### Hero CTA Analytics

`Hero.tsx` and `Nav.tsx` already guard PostHog calls with try/catch:

```ts
try {
  posthog?.capture("cta_hero_book_call_click");
} catch {
  /* silent */
}
```

Keep this non-blocking analytics pattern. Rename event names only if tests and analytics expectations are updated together.

### Landing Tests

`booking-cta.test.tsx` already demonstrates the needed mocking style:

```ts
vi.mock('posthog-js/react', () => ({
  usePostHog: () => ({
    capture: vi.fn(),
  }),
}))
```

Use the same pattern for hero, section, and claims tests. Do not mount real Remotion or Cal.com in landing copy tests.

### Visual Styling

Landing styles are scoped under `.landing-theme` in `apps/web/src/app/landing.css`. Plan changes should use the existing tokens:

- `--color-teal: #49d6b5`
- `--color-navy: #0A0A0F`
- `--color-surface: #0F0F18`
- `--color-text-muted: #6B7280`
- `--color-text-secondary: #9CA3AF`

Avoid dashboard token edits. Phase 42 is landing-only.

## Risk Notes For Executors

- `apps/web/src/components/landing/RemotionPlayer.tsx` and `apps/web/src/components/landing/__tests__/remotion-player.test.tsx` are already dirty in the worktree. Do not revert or casually rewrite them. The hero can stop depending on Remotion without deleting the Remotion files.
- `apps/web/src/components/landing/__tests__/booking-cta.test.tsx` currently expects `Book a Call`; Plan 42-01 must update that assertion when `BOOKING_CTA_LABEL` changes.
- Avoid adding a `meta keywords` tag. The phase explicitly rejects it.
- Do not add a live action-layer UI. Task creation, doc drafts, owner confirmation, and PR comments are future-tense teaser copy only.
- Do not keep `SOC 2 compliant architecture` unless a source-backed company/security artifact is added in the same phase.
