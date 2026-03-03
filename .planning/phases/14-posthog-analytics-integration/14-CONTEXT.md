# Phase 14: PostHog Analytics + Live Waitlist - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase adds PostHog to the landing page and wires the existing waitlist form to capture signups as PostHog events. No backend/database needed for the waitlist -- PostHog IS the backend for signup tracking.

Scope:
1. PostHog JS SDK setup in the Next.js app (landing pages only)
2. Page view tracking on landing page
3. Waitlist form wired to PostHog `capture('waitlist_signup', { email })`
4. Basic event tracking for key interactions (CTA clicks, section views)

Out of scope:
- No Supabase waitlist table
- No email confirmation flow
- No feature flags (can add later in a separate phase)
- No PostHog on the dashboard/app pages (landing only for now)

</domain>

<decisions>
## Implementation Decisions

### Waitlist Approach
- LOCKED: Use PostHog events for waitlist signups (no database table)
- LOCKED: Track `waitlist_signup` event with email property
- LOCKED: View/export signups from PostHog dashboard

### SDK Setup
- PostHog JS SDK (`posthog-js`) installed in the Next.js app
- Initialize PostHog only on landing pages (not dashboard)
- Use environment variable for PostHog API key (`NEXT_PUBLIC_POSTHOG_API_KEY`)

### Events to Track
- `$pageview` — automatic page views on landing page
- `waitlist_signup` — email submitted via CTA form, with `{ email }` property
- Section scroll visibility (optional — can use PostHog autocapture)

### Claude's Discretion
- PostHog provider component placement (landing layout vs app-wide with conditional init)
- Whether to use `posthog-js` directly or `posthog-js/react` provider
- Autocapture on/off decision
- Error handling for failed PostHog calls (should be silent/non-blocking)

</decisions>

<specifics>
## Specific Ideas

- The CTASection.tsx already has a working form with email state and handleSubmit — just needs a `posthog.capture()` call added
- Hero.tsx has a "Join the Waitlist" CTA link that scrolls to #waitlist section — could track this click too
- Landing page is at `apps/web/src/app/(landing)/` with its own layout
- All landing components are client-side ("use client") so PostHog JS works directly

</specifics>

<deferred>
## Deferred Ideas

- Feature flags infrastructure (separate phase if needed)
- PostHog on dashboard/app pages
- Session recordings
- A/B testing on landing page copy
- Supabase waitlist table for direct DB queries

</deferred>

---

*Phase: 14-posthog-analytics-integration*
*Context gathered: 2026-03-04 via conversation*
