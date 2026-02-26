# Phase 08: Dashboard UI/UX Redesign

## Goal

Transform the ContextOS dashboard from a scaffolded prototype into a polished, Linear-inspired developer dashboard with a collapsible sidebar, indigo accent color, and an integration health hub that shows the product's value.

## Scope

Frontend-only changes. No backend modifications.

### Design Decisions
- Linear-inspired visual direction (dark sidebar, clean layout, indigo accents)
- Sidebar navigation (replaces top nav bar)
- Integration health hub (replaces placeholder home page)

### Files to Modify/Create
| File | Action |
|------|--------|
| `apps/web/src/app/globals.css` | Modify (theme tokens) |
| `apps/web/src/app/dashboard/sidebar.tsx` | Create (sidebar nav) |
| `apps/web/src/app/dashboard/layout.tsx` | Modify (sidebar layout) |
| `apps/web/src/app/dashboard/page.tsx` | Rewrite (health hub) |
| `apps/web/src/app/dashboard/integrations/integration-card.tsx` | Modify (card redesign) |
| `apps/web/src/app/dashboard/integrations/page.tsx` | Modify (grid + header) |
| `apps/web/src/app/dashboard/sign-out-button.tsx` | Delete (logic moved to sidebar) |

### Files Unchanged
- slack-channels.tsx, github-repos.tsx, fathom-connect.tsx
- All UI primitives (button, card, input, label)
- api.ts, utils.ts

## Dependencies
- Phase 1 (Foundation - auth UI exists)
- No backend changes required

## Success Criteria
1. Dashboard loads without errors
2. Sidebar nav works with collapse toggle (240px <-> 60px)
3. Active nav item highlighted on correct page
4. Home page shows welcome greeting, setup progress ring, integration status grid
5. Integration cards redesigned in 2-col layout
6. Quick connect buttons trigger OAuth flows
7. Disconnect and expandable settings still work
8. Sign out from sidebar works
