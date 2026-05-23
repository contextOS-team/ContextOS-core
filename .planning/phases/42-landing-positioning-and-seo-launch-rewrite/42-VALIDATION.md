---
phase: 42
slug: landing-positioning-and-seo-launch-rewrite
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-22
---

# Phase 42 - Validation Strategy

> Per-phase validation contract for the launch landing rewrite.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest `^4.0.18` |
| **Config file** | `apps/web/vitest.config.ts` |
| **Quick run command** | `cd apps/web && npm run typecheck` |
| **Full suite command** | `cd apps/web && npm run typecheck && npx vitest run` |
| **Estimated runtime** | ~45-90 seconds |

---

## Sampling Rate

- **After every task commit:** Run `cd apps/web && npm run typecheck`
- **After every plan wave:** Run the plan-specific Vitest command plus `cd apps/web && npm run typecheck`
- **Before `$gsd-verify-work`:** `cd apps/web && npm run typecheck && npx vitest run` must be green
- **Max feedback latency:** 90 seconds for targeted landing tests

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 42-01-01 | 01 | 1 | LAND-05 | T-42-01 | Metadata uses supported public positioning only; no meta keywords | unit/static | `cd apps/web && npx vitest run src/components/landing/__tests__/landing-metadata.test.ts` | No - W0 | pending |
| 42-01-02 | 01 | 1 | LAND-04 | T-42-02 | CTA copy promises a useful booking artifact, not a product action that does not exist | render | `cd apps/web && npx vitest run src/components/landing/__tests__/booking-cta.test.tsx` | Existing - update | pending |
| 42-02-01 | 02 | 2 | LAND-04, LAND-08 | T-42-03 | Hero visual uses fake/demo evidence only and shows verification state | render | `cd apps/web && npx vitest run src/components/landing/__tests__/landing-hero.test.tsx` | No - W0 | pending |
| 42-03-01 | 03 | 3 | LAND-06, LAND-07 | T-42-04 | Future action-layer claims are clearly future-tense; unsupported trust claims are absent | render/static | `cd apps/web && npx vitest run src/components/landing/__tests__/landing-sections.test.tsx src/components/landing/__tests__/landing-claims.test.tsx` | No - W0 | pending |
| 42-03-02 | 03 | 3 | LAND-05, LAND-08 | T-42-05 | Visible copy is crawlable React text and decision proof is visible on desktop/mobile | manual + typecheck | `cd apps/web && npm run typecheck` | N/A | pending |

*Status: pending, green, red, flaky*

---

## Wave 0 Requirements

- [ ] `apps/web/src/components/landing/__tests__/landing-metadata.test.ts` - asserts landing metadata title/description and no meta keywords.
- [ ] `apps/web/src/components/landing/__tests__/landing-hero.test.tsx` - asserts hero H1, badge, category proof line, CTA labels, Decision Receipt fields, source chips, affected systems, and verification state.
- [ ] `apps/web/src/components/landing/__tests__/landing-sections.test.tsx` - asserts problem/product/workflow/differentiation/booking copy foregrounds current MVP capabilities.
- [ ] `apps/web/src/components/landing/__tests__/landing-claims.test.tsx` - guards against banned phrases and unsupported claims such as `SOC 2 compliant architecture`, `2-6 hours`, `2 minutes`, `AI-native OS`, `company brain`, and live action-layer promises.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Hero and Decision Receipt visual fit desktop and mobile without overlapping text | LAND-04, LAND-08 | DOM tests cannot prove visual hierarchy, overlap, or first-viewport composition | Run the dev server, inspect `/` at desktop and mobile widths, confirm H1/CTA/Decision Receipt/source chips/status/affected systems are visible and readable. |
| Booking section remains usable after CTA copy changes | LAND-04 | Cal.com iframe behavior depends on third-party embed runtime | Open the booking section and confirm the inline Cal embed still appears under the revised promise. |
| Copy tone avoids unsupported launch claims | LAND-06, LAND-07 | Some claims require human judgment against current product/company state | Read the full landing page and confirm action-layer items are future-tense and trust/security copy is supportable. |

---

## Validation Sign-Off

- [x] All tasks have automated verify commands or Wave 0 test dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all missing references
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-22
