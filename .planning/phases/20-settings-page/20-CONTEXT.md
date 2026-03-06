# Phase 20: Settings Page - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can manage API keys, edit workspace name, and view team members from a dedicated settings page accessible via the avatar dropdown. Integrations stay at their own route; settings links to them. Team invites and role management are v2 (TEAM-01, TEAM-02).

</domain>

<decisions>
## Implementation Decisions

### Page layout
- Stacked sections on a single scrollable page (matches dashboard home pattern)
- Sections: General (workspace name), API Keys, Team, Integrations (link only)
- Use existing `section-label` headings, `space-y-6` rhythm, `rounded-xl border bg-card` containers
- No tabs, no sidebar nav -- keep pattern consistency with existing dashboard pages

### API key creation
- User must name the key (e.g., "MCP Server", "CI Pipeline") -- name is required
- Keys use `cos_` prefix (e.g., `cos_a1b2c3d4e5f6g7h8...`)
- After creation, full key shown inline in a highlighted box with copy button and "won't be shown again" warning
- Dismiss to return to key list -- not a modal
- Key list shows: name, prefix (`cos_a1b2...`), created date, revoke button
- Key display uses JetBrains Mono (DS-03)

### API key revocation
- Click "Revoke" on a key row opens a confirmation dialog
- Dialog text: "Revoke '[key name]'? This key will stop working immediately. Cannot be undone."
- Cancel / Revoke buttons

### Workspace editing
- Name-only editing (slug stays immutable)
- Explicit save button, disabled until value changes
- Success feedback via Sonner toast
- No danger zone section (no delete workspace)

### Team members
- Read-only list showing: avatar initials, full name, email, role badge (Owner/Member)
- Section header: "TEAM . N members" with count in muted text
- Uses same container pattern as key list (rounded-xl border bg-card, divide-y)

### Integrations link
- Settings page includes an "Integrations" section at the bottom
- Shows "Manage your connected services" with a link to /dashboard/integrations
- Integrations page stays at its own route and nav item -- not moved into settings

### Claude's Discretion
- Skeleton loading state design (must match populated layout per DS-09)
- Empty state for API keys (no keys yet)
- Exact spacing within sections
- Error handling patterns

</decisions>

<specifics>
## Specific Ideas

- API key prefix `cos_` follows Stripe's `sk_` pattern -- short, identifiable in config files
- Team member display mirrors the avatar initials pattern already used in the top nav sidebar
- The "won't be shown again" warning on key creation is standard security practice (GitHub, Linear, Stripe all do this)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Card`, `CardContent` (`@/components/ui/card`): Used for integration cards, can wrap settings sections
- `Button` (`@/components/ui/button`): Primary and outline variants available
- `Input`, `Label` (`@/components/ui/input`, `@/components/ui/label`): For workspace name editing and key name input
- `Skeleton` (`@/components/ui/skeleton`): For loading states
- `DropdownMenu` components: Available if needed for key actions
- `section-label` CSS class: Monospace uppercase headings used on dashboard home
- `animate-fade-in-up`, `animate-scale-in`: Entrance animations
- Sonner toaster: Already integrated for toast notifications

### Established Patterns
- Dashboard pages use `'use client'` with `useCallback`/`useEffect` for data fetching
- `apiFetch<T>()` wrapper in `@/lib/api.ts` for authenticated backend calls
- `formatRelativeTime()` utility in `@/lib/utils` for timestamp display
- `getInitials()` function in sidebar.tsx for avatar initials
- `displayName()` utility for safe name display
- Confirmation via `window.confirm()` for disconnect (integration cards) -- but revocation should use a proper dialog component

### Integration Points
- Settings link already exists in avatar dropdown at `/dashboard/settings` (sidebar.tsx:117)
- Backend: `GET /api/workspaces/current` exists -- needs `PATCH` endpoint for name update
- Backend: No API key endpoints or table yet -- needs new migration + CRUD endpoints
- Backend: `workspace_members` table exists -- needs a list endpoint for team view
- MCP server: Uses `CONTEXTOS_API_KEY` env var with Bearer auth -- API key validation needs to work with this

</code_context>

<deferred>
## Deferred Ideas

- Team member invites via email -- TEAM-01 (v2)
- Role-based access control (admin/member) -- TEAM-02 (v2)
- API key usage metrics per key -- TEAM-03 (v2)
- Workspace slug editing -- adds URL-breaking risk, defer
- Workspace deletion / danger zone -- defer until multi-workspace support

</deferred>

---

*Phase: 20-settings-page*
*Context gathered: 2026-03-06*
