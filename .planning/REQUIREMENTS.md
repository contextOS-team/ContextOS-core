# Requirements: ContextOS v1.1 Dashboard & Onboarding

**Defined:** 2026-03-04
**Core Value:** When an engineer picks up a ticket, they immediately have the full story -- where the feature came from, what was discussed in Slack, and a ready-to-paste AI prompt.

## v1.1 Requirements

Requirements for the dashboard redesign and onboarding milestone. Each maps to roadmap phases.

### Design System

- [ ] **DS-01**: Dashboard renders in dark mode by default with brand-tinted OKLCH tokens (not neutral gray shadcn defaults)
- [ ] **DS-02**: Teal (#00D4AA) used only on actionable/status elements — never as decoration
- [ ] **DS-03**: JetBrains Mono applied to all data identifiers (ticket IDs, timestamps, counts, API keys)
- [ ] **DS-04**: 4-level surface hierarchy (background → card → elevated → overlay) with consistent token usage
- [ ] **DS-05**: Radix UI portals (Dialog, Dropdown, Sheet) render correctly in dark mode via DarkModeApplier
- [ ] **DS-06**: Spring-curve microinteractions on list item appearance (stagger), status changes, and completion states
- [ ] **DS-07**: Subtle grain texture on dashboard surfaces matching the landing page aesthetic
- [ ] **DS-08**: Section labels use monospace uppercase tracking pattern from landing page
- [ ] **DS-09**: All dashboard pages render structured skeleton loading states matching the populated layout

### Navigation

- [ ] **NAV-01**: Dashboard navigation restructured to hold all sections (context feed, activity, integrations, settings) with clear active state indicators

### Onboarding

- [ ] **ONB-01**: User sees a 4-step onboarding wizard after first signup before accessing dashboard
- [ ] **ONB-02**: Step 1: user names their workspace (single text input)
- [ ] **ONB-03**: Step 2: user connects Linear (required, cannot proceed without)
- [ ] **ONB-04**: Step 3: user optionally connects additional sources (Slack, GitHub, Notion, Fathom) from a grid
- [ ] **ONB-05**: Step 4: user sees their first generated context page with realistic mock fallback if pipeline unavailable
- [ ] **ONB-06**: OAuth redirect preserves wizard state via cookie (user returns to correct step after OAuth callback)
- [ ] **ONB-07**: Onboarding progress persists across browser refreshes (database-backed state)
- [ ] **ONB-08**: Animated checkmark confirmation when integration connects successfully
- [ ] **ONB-09**: Server-side onboarding gate prevents dashboard access until onboarding complete

### Dashboard Home

- [ ] **HOME-01**: Dashboard home page shows a summary view with recent context pages, integration health, and activity preview

### Context Feed

- [ ] **FEED-01**: User can browse all generated context pages in a scrollable list view
- [ ] **FEED-02**: User can filter context pages by status (All/Ready/Generating/Stale/Error)
- [ ] **FEED-03**: User can search context pages by free text (title, ticket ID)
- [ ] **FEED-04**: Context feed shows real-time status updates via Supabase Realtime
- [ ] **FEED-05**: Context page detail is a route-based view (/dashboard/context/[id]) with copy-prompt and regenerate actions
- [ ] **FEED-06**: Empty states show what a populated feed looks like with one clear CTA

### Activity Timeline

- [ ] **ACT-01**: User sees a chronological feed of workspace events (syncs, context generated, integrations connected)
- [ ] **ACT-02**: Events display with type-specific icons, relative timestamps, and day-group dividers
- [ ] **ACT-03**: Activity timeline updates in real-time via Supabase Realtime
- [ ] **ACT-04**: Activity events table exists with 30-day retention policy

### Settings & Team

- [ ] **SET-01**: User can create and revoke API keys (show full key once on creation, then prefix-only)
- [ ] **SET-02**: User can edit workspace name
- [ ] **SET-03**: User can view connected team members
- [ ] **SET-04**: Settings page accessible from dashboard navigation

### Auth Redesign

- [ ] **AUTH-01**: Login and signup pages use dark theme matching the dashboard brand identity
- [ ] **AUTH-02**: Auth pages use the same teal accent, typography, and surface tokens as dashboard

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Theme & Customization

- **THEME-01**: Light/dark mode toggle for user preference
- **THEME-02**: Custom brand color configuration per workspace

### Advanced Feed

- **FEED-07**: Context feed right-panel split view (inline detail alongside list)
- **FEED-08**: Keyboard navigation for context feed (j/k/Enter/Esc/r/c)
- **FEED-09**: Stale reason indicator on context pages

### Team Management

- **TEAM-01**: Team member invites via email
- **TEAM-02**: Role-based access control (admin/member)
- **TEAM-03**: API key usage metrics per key

### Auth

- **AUTH-03**: Social OAuth login (Google, GitHub)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Jira integration | Only Linear is supported as task tracker in v1. Add when Jira support is built |
| Email onboarding drip | Marketing infrastructure overhead for a dogfooding team |
| Video tutorials in onboarding | Developers skip them; goes stale on every UI change |
| Onboarding checklist widget in dashboard | Visual noise once setup is complete |
| next-themes ThemeProvider | Dark mode is a brand decision, not a user toggle. Unnecessary dependency |
| @tanstack/react-query | Premature before caching problems exist |
| Mobile responsive polish | Desktop-first internal tool |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DS-01 | Phase 15 | Pending |
| DS-02 | Phase 15 | Pending |
| DS-03 | Phase 15 | Pending |
| DS-04 | Phase 15 | Pending |
| DS-05 | Phase 15 | Pending |
| DS-06 | Phase 15 | Pending |
| DS-07 | Phase 15 | Pending |
| DS-08 | Phase 15 | Pending |
| DS-09 | Phase 15 | Pending |
| NAV-01 | Phase 15 | Pending |
| AUTH-01 | Phase 16 | Pending |
| AUTH-02 | Phase 16 | Pending |
| ACT-04 | Phase 16 | Pending |
| ONB-07 | Phase 16 | Pending |
| ONB-09 | Phase 16 | Pending |
| ONB-01 | Phase 17 | Pending |
| ONB-02 | Phase 17 | Pending |
| ONB-03 | Phase 17 | Pending |
| ONB-04 | Phase 17 | Pending |
| ONB-05 | Phase 17 | Pending |
| ONB-06 | Phase 17 | Pending |
| ONB-08 | Phase 17 | Pending |
| ACT-01 | Phase 18 | Pending |
| ACT-02 | Phase 18 | Pending |
| ACT-03 | Phase 18 | Pending |
| FEED-01 | Phase 19 | Pending |
| FEED-02 | Phase 19 | Pending |
| FEED-03 | Phase 19 | Pending |
| FEED-04 | Phase 19 | Pending |
| FEED-05 | Phase 19 | Pending |
| FEED-06 | Phase 19 | Pending |
| HOME-01 | Phase 19 | Pending |
| SET-01 | Phase 20 | Pending |
| SET-02 | Phase 20 | Pending |
| SET-03 | Phase 20 | Pending |
| SET-04 | Phase 20 | Pending |

**Coverage:**
- v1.1 requirements: 36 total
- Mapped to phases: 36
- Unmapped: 0

---
*Requirements defined: 2026-03-04*
*Last updated: 2026-03-04 after roadmap creation (phases 15-20 mapped)*
