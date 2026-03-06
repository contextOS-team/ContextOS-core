# Phase 20: Settings Page - Research

**Researched:** 2026-03-06
**Domain:** Full-stack settings page (Next.js dashboard + FastAPI backend + Supabase schema)
**Confidence:** HIGH

## Summary

Phase 20 implements a settings page with four sections: General (workspace name editing), API Keys (create/revoke), Team (read-only member list), and Integrations (link only). The implementation spans three layers: a Supabase migration for the `api_keys` table, FastAPI backend endpoints for API key CRUD + workspace PATCH + team list, and a Next.js dashboard page at `/dashboard/settings`.

The project has mature patterns for all three layers. Dashboard pages follow a `'use client'` pattern with `useCallback`/`useEffect` for data fetching via `apiFetch<T>()`. The backend uses FastAPI routers with `get_current_user` dependency injection yielding `UserContext(user_id, email, workspace_id)`. Database migrations are numbered sequentially (latest is `00015`). The next migration should be `00016`.

**Primary recommendation:** Build backend-first (migration + endpoints), then frontend. The settings page has no Realtime requirements, no complex state management, and no new dependencies -- it reuses existing UI components (Card, Button, Input, Label, Skeleton, Sonner) and needs only one new Radix primitive: AlertDialog for the revoke confirmation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Stacked sections on a single scrollable page (matches dashboard home pattern)
- Sections: General (workspace name), API Keys, Team, Integrations (link only)
- Use existing `section-label` headings, `space-y-6` rhythm, `rounded-xl border bg-card` containers
- No tabs, no sidebar nav -- keep pattern consistency with existing dashboard pages
- API key creation: user must name the key, keys use `cos_` prefix, full key shown inline (not modal) with copy button and "won't be shown again" warning, key list shows name/prefix/created date/revoke button, JetBrains Mono for key display
- API key revocation: click "Revoke" opens confirmation dialog with "Revoke '[key name]'? This key will stop working immediately. Cannot be undone." and Cancel/Revoke buttons
- Workspace editing: name-only (slug immutable), explicit save button disabled until value changes, success feedback via Sonner toast, no danger zone
- Team members: read-only list with avatar initials, full name, email, role badge (Owner/Member), section header "TEAM . N members"
- Integrations link: section at bottom with "Manage your connected services" linking to /dashboard/integrations

### Claude's Discretion
- Skeleton loading state design (must match populated layout per DS-09)
- Empty state for API keys (no keys yet)
- Exact spacing within sections
- Error handling patterns

### Deferred Ideas (OUT OF SCOPE)
- Team member invites via email -- TEAM-01 (v2)
- Role-based access control (admin/member) -- TEAM-02 (v2)
- API key usage metrics per key -- TEAM-03 (v2)
- Workspace slug editing -- adds URL-breaking risk, defer
- Workspace deletion / danger zone -- defer until multi-workspace support
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SET-01 | User can create and revoke API keys (show full key once on creation, then prefix-only) | Backend: new `api_keys` table + CRUD endpoints. Frontend: API key section with create form, key list, revoke confirmation dialog. Crypto: SHA-256 hashing of raw key, store only hash + prefix. |
| SET-02 | User can edit workspace name | Backend: PATCH endpoint on existing `/api/workspaces/current`. Frontend: inline form with save button + Sonner toast. |
| SET-03 | User can view connected team members | Backend: new GET endpoint listing `workspace_members` joined with `profiles`. Frontend: member list with initials, name, email, role badge. |
| SET-04 | Settings page accessible from dashboard navigation | Already wired: sidebar.tsx line 117 has Settings link to `/dashboard/settings`. Just needs the page to exist at that route. |
</phase_requirements>

## Standard Stack

### Core (already installed -- no new dependencies)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | ^15.2.0 | App router, dashboard page | Already the framework |
| FastAPI | (pyproject.toml) | Backend REST endpoints | Already the backend framework |
| SQLModel | (pyproject.toml) | ORM model for api_keys | Project pattern for all models |
| Supabase | Local + hosted | Database + RLS | Already the database |
| radix-ui | ^1.4.3 | AlertDialog for revoke confirmation | Already installed, used for DropdownMenu |
| sonner | ^1.7.0 | Toast notifications | Already installed and configured |
| lucide-react | ^0.469.0 | Icons (Key, Copy, Check, etc.) | Already installed |

### New UI Component Needed
| Component | Source | Purpose |
|-----------|--------|---------|
| AlertDialog | `radix-ui` (already installed) | Revoke confirmation dialog per CONTEXT.md decision |

The `radix-ui` package (v1.4.3) is already installed and exports `AlertDialog` as a subpath. The existing `DropdownMenu` component demonstrates the import pattern: `import { AlertDialog as AlertDialogPrimitive } from "radix-ui"`. A new `alert-dialog.tsx` shadcn-style wrapper should be created in `@/components/ui/` following the exact same pattern as `dropdown-menu.tsx`.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| AlertDialog | `window.confirm()` | CONTEXT.md explicitly requires a proper dialog component with Cancel/Revoke buttons. Integration card uses window.confirm, but settings revocation warrants better UX. |
| Custom hash function | bcrypt/argon2 | SHA-256 is sufficient for API key hashing (keys are high-entropy random tokens, not passwords). Stripe, GitHub, and Linear all use SHA-256 for API key hashing. |

**No new npm or pip installs required.**

## Architecture Patterns

### Recommended Project Structure
```
supabase/migrations/
  00016_api_keys.sql              # New table + RLS

backend/src/
  models/api_key.py               # SQLModel for api_keys table
  services/api_key.py             # Business logic (generate, hash, list, revoke)
  routers/workspaces.py           # Extend with PATCH /current, GET /current/members, api key CRUD

apps/web/src/
  app/dashboard/settings/
    page.tsx                      # Main settings page (single file, stacked sections)
  components/ui/
    alert-dialog.tsx              # New Radix AlertDialog wrapper
  lib/
    api.ts                        # Add settings API functions
```

### Pattern 1: Dashboard Page Structure (established)
**What:** Client component with useCallback/useEffect data fetching, skeleton loading state, error handling
**When to use:** Every dashboard page follows this pattern
**Example:**
```typescript
// Source: apps/web/src/app/dashboard/page.tsx (existing pattern)
'use client'

import { useCallback, useEffect, useState } from 'react'

export default function SettingsPage() {
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = useCallback(async () => {
    setError(null)
    try {
      const [workspace, keys, members] = await Promise.all([
        getWorkspace(),
        listApiKeys(),
        listMembers(),
      ])
      // set state
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load settings')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  if (isLoading) return <SettingsSkeleton />
  // render sections
}
```

### Pattern 2: Backend Router + Service Layer (established)
**What:** Router defines endpoints, service contains business logic, both use UserContext dependency
**When to use:** All backend features
**Example:**
```python
# Source: backend/src/routers/workspaces.py (existing pattern)
@router.patch("/current")
async def update_workspace(
    body: dict,
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    # call service layer
```

### Pattern 3: API Key Security (industry standard)
**What:** Generate random key, return full key once, store SHA-256 hash + prefix
**When to use:** API key creation
**Example:**
```python
import secrets
import hashlib

def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, hash)."""
    raw = secrets.token_hex(32)  # 64 hex chars
    full_key = f"cos_{raw}"
    prefix = f"cos_{raw[:8]}"  # cos_a1b2c3d4
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash

def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of key hash."""
    return hmac.compare_digest(
        hashlib.sha256(provided_key.encode()).hexdigest(),
        stored_hash
    )
```

### Pattern 4: Stacked Section Layout (from CONTEXT.md decisions)
**What:** Single scrollable page with section-label headings and card containers
**When to use:** Settings page layout
**Example:**
```tsx
// Matches dashboard home page pattern
<div className="space-y-6 animate-fade-in-up">
  {/* General section */}
  <div>
    <h3 className="section-label mb-3">General</h3>
    <div className="rounded-xl border bg-card overflow-hidden">
      {/* workspace name form */}
    </div>
  </div>

  {/* API Keys section */}
  <div>
    <h3 className="section-label mb-3">API Keys</h3>
    <div className="rounded-xl border bg-card overflow-hidden divide-y divide-border">
      {/* key list rows */}
    </div>
  </div>
</div>
```

### Anti-Patterns to Avoid
- **Storing raw API keys in the database:** Only store SHA-256 hash + prefix. The full key is returned once at creation time and never again.
- **Using tabs or sidebar nav for settings sections:** CONTEXT.md explicitly says no tabs, no sidebar nav -- stacked sections matching the dashboard home pattern.
- **Using window.confirm() for revocation:** CONTEXT.md says to use a proper dialog component. Use Radix AlertDialog.
- **Creating the key display as a modal:** CONTEXT.md says inline, not modal. Show the created key inline in a highlighted box.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Confirmation dialog | Custom dialog with backdrop/trap | Radix AlertDialog via `@/components/ui/alert-dialog.tsx` | Focus trapping, escape handling, screen reader support |
| Toast notifications | Custom notification system | Sonner (already integrated) | Already working with dark theme styling |
| Cryptographic key generation | Custom random string | `secrets.token_hex(32)` (Python stdlib) | Cryptographically secure, no dependency needed |
| API key hashing | Custom hash or bcrypt | `hashlib.sha256` (Python stdlib) | API keys are high-entropy; SHA-256 is industry standard (Stripe, GitHub) |
| Copy to clipboard | Custom implementation | `navigator.clipboard.writeText()` | Browser-native, no library needed |
| Avatar initials | New function | Reuse `getInitials()` from sidebar.tsx | Already handles edge cases (full name vs email) |

**Key insight:** This phase has zero new dependencies. Everything needed is either in the existing stack (Radix, Sonner, Lucide) or in Python/JS standard libraries (secrets, hashlib, navigator.clipboard).

## Common Pitfalls

### Pitfall 1: API Key Shown After Page Refresh
**What goes wrong:** User creates a key, full key is shown, user refreshes page, key is lost forever.
**Why it happens:** The full key only exists in the creation response -- it's not stored.
**How to avoid:** Make the UX crystal clear with "won't be shown again" warning. Use a visually distinct highlighted box. Provide a copy button. Only clear the created-key state when user explicitly dismisses.
**Warning signs:** If the key creation response is stored in a `useRef` or persisted anywhere beyond component state.

### Pitfall 2: Race Condition on Workspace Name Save
**What goes wrong:** User double-clicks save, two PATCH requests fire, second one fails or causes confusion.
**Why it happens:** No loading state on the save button.
**How to avoid:** Disable the save button while the PATCH request is in flight. Show loading spinner. Re-enable on success or error.
**Warning signs:** Button not disabled during save operation.

### Pitfall 3: Stale Key List After Creation/Revocation
**What goes wrong:** User creates or revokes a key but the list doesn't update.
**Why it happens:** API key list not refreshed after mutation.
**How to avoid:** After successful create/revoke, refetch the key list or optimistically update local state.
**Warning signs:** Separate state for key list not being updated after mutations.

### Pitfall 4: Missing RLS on api_keys Table
**What goes wrong:** Users can see/modify other workspaces' API keys via Supabase client.
**Why it happens:** Forgot to add RLS policies.
**How to avoid:** Migration must include `ENABLE ROW LEVEL SECURITY` and a policy using `get_user_workspace_ids(auth.uid())` (the existing helper function from migration 00015).
**Warning signs:** Missing ENABLE ROW LEVEL SECURITY in migration.

### Pitfall 5: AlertDialog Not Rendering in Dark Mode
**What goes wrong:** Radix portal renders outside the `.dark` class scope.
**Why it happens:** Portals attach to document.body which may not have the dark class.
**How to avoid:** The project already solved this with `DarkModeApplier` adding `.dark` to the `<html>` element, and the `:where(.dark, .dark *)` custom variant. AlertDialog portals will inherit correctly as long as the component follows the same pattern as DropdownMenu.
**Warning signs:** Not using the Portal component from Radix.

### Pitfall 6: MCP Server API Key Validation Not Wired
**What goes wrong:** API keys are created in settings but the MCP server's `CONTEXTOS_API_KEY` env var doesn't validate against the database.
**Why it happens:** MCP server currently passes `API_KEY` as a Bearer token but backend only validates Supabase JWTs.
**How to avoid:** This is a known gap. For Phase 20, create the API keys table and CRUD. The MCP server integration (validating `cos_*` keys on the backend auth layer) can be a follow-up task or handled within this phase as an optional enhancement.
**Warning signs:** Assuming the MCP server will magically start working with created API keys.

## Code Examples

Verified patterns from existing codebase:

### Database Migration Pattern
```sql
-- Source: supabase/migrations/00012_onboarding_and_activity.sql (pattern)
-- Next migration: 00016_api_keys.sql

CREATE TABLE public.api_keys (
  id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid        NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
  created_by   uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name         text        NOT NULL,
  key_prefix   text        NOT NULL,  -- cos_a1b2c3d4
  key_hash     text        NOT NULL,  -- SHA-256 of full key
  revoked_at   timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_api_keys_workspace
  ON public.api_keys (workspace_id, revoked_at);

CREATE INDEX idx_api_keys_hash
  ON public.api_keys (key_hash) WHERE revoked_at IS NULL;

ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workspace_api_keys" ON public.api_keys
  FOR ALL USING (
    workspace_id IN (SELECT public.get_user_workspace_ids(auth.uid()))
  );
```

### Backend API Endpoint Pattern (apiFetch wrapper)
```typescript
// Source: apps/web/src/lib/api.ts (extend with these)
export interface ApiKeyResponse {
  id: string
  name: string
  key_prefix: string
  created_at: string
}

export interface ApiKeyCreatedResponse extends ApiKeyResponse {
  key: string  // Full key, shown once only
}

export function listApiKeys(): Promise<{ keys: ApiKeyResponse[] }> {
  return apiFetch<{ keys: ApiKeyResponse[] }>('/api/workspaces/current/api-keys')
}

export function createApiKey(name: string): Promise<ApiKeyCreatedResponse> {
  return apiFetch<ApiKeyCreatedResponse>('/api/workspaces/current/api-keys', {
    method: 'POST',
    body: JSON.stringify({ name }),
  })
}

export function revokeApiKey(keyId: string): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(`/api/workspaces/current/api-keys/${keyId}`, {
    method: 'DELETE',
  })
}

export function updateWorkspaceName(name: string): Promise<{ name: string }> {
  return apiFetch<{ name: string }>('/api/workspaces/current', {
    method: 'PATCH',
    body: JSON.stringify({ name }),
  })
}

export interface TeamMember {
  user_id: string
  full_name: string | null
  email: string
  role: string
  created_at: string
}

export function listTeamMembers(): Promise<{ members: TeamMember[] }> {
  return apiFetch<{ members: TeamMember[] }>('/api/workspaces/current/members')
}
```

### Clipboard Copy with Feedback
```tsx
// Common pattern for copy-to-clipboard with icon swap
const [copied, setCopied] = useState(false)

async function handleCopy(text: string) {
  await navigator.clipboard.writeText(text)
  setCopied(true)
  setTimeout(() => setCopied(false), 2000)
}

// In JSX:
<button onClick={() => handleCopy(fullKey)}>
  {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
</button>
```

### Section Label Pattern (existing)
```tsx
// Source: apps/web/src/app/dashboard/page.tsx
// section-label CSS class: font-mono 0.7rem uppercase tracking-widest muted-foreground
<h3 className="section-label mb-3">API Keys</h3>
```

### Skeleton Loading Pattern (existing)
```tsx
// Source: apps/web/src/app/dashboard/page.tsx
// Matches populated layout structure with Skeleton components
<div className="space-y-6 animate-fade-in-up">
  <Skeleton className="h-3 w-28 mb-3" />
  <div className="rounded-xl border border-border overflow-hidden divide-y divide-border">
    {Array.from({ length: 3 }).map((_, i) => (
      <div key={i} className="px-4 py-3">
        <Skeleton className="h-4 w-48" />
      </div>
    ))}
  </div>
</div>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `window.confirm()` for destructive actions | Radix AlertDialog | Established in CONTEXT.md decision | Better UX, accessibility, dark mode support |
| Store full API keys encrypted | Store only SHA-256 hash + prefix | Industry standard (Stripe, GitHub, Linear) | More secure -- even database breach doesn't expose keys |
| Separate settings routes (tabs) | Single scrollable page | CONTEXT.md decision | Simpler, matches existing dashboard patterns |

**Current in this project:**
- `radix-ui` v1.4.3 (monorepo package with all primitives including AlertDialog)
- Tailwind CSS v4 with `@custom-variant dark` using `:where(.dark, .dark *)`
- shadcn pattern: functional components wrapping Radix primitives with `cn()` utility

## Open Questions

1. **MCP Server API Key Validation**
   - What we know: MCP server sends `CONTEXTOS_API_KEY` as Bearer token. Backend currently only validates Supabase JWTs via `decode_supabase_jwt()`.
   - What's unclear: Should Phase 20 also add an alternative auth path in the backend that validates `cos_*` API keys against the `api_keys` table?
   - Recommendation: Create the table and CRUD endpoints. Defer the backend auth middleware change (adding API key auth as an alternative to JWT) to a separate task or note it as an optional enhancement. The MCP server will work once the auth path is added, but the settings page itself doesn't need it.

2. **Clipboard API Availability**
   - What we know: `navigator.clipboard.writeText()` requires HTTPS or localhost. The dashboard runs on both.
   - What's unclear: Edge cases with permissions (some browsers prompt on first clipboard access).
   - Recommendation: Use `navigator.clipboard.writeText()` with a try/catch fallback. Not worth adding a clipboard library for one button.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `apps/web/src/app/dashboard/page.tsx` -- dashboard page pattern
- Codebase analysis: `apps/web/src/app/dashboard/sidebar.tsx` -- settings link already exists (line 117)
- Codebase analysis: `backend/src/routers/workspaces.py` -- existing GET /current endpoint
- Codebase analysis: `backend/src/dependencies.py` -- UserContext auth pattern
- Codebase analysis: `backend/src/models/user.py` -- WorkspaceMember model (role, user_id, workspace_id)
- Codebase analysis: `backend/src/models/workspace.py` -- Workspace model (name, slug)
- Codebase analysis: `supabase/migrations/00015_fix_workspace_members_rls.sql` -- latest migration number
- Codebase analysis: `supabase/migrations/00012_onboarding_and_activity.sql` -- RLS policy pattern using `get_user_workspace_ids()`
- Codebase analysis: `apps/web/src/lib/api.ts` -- apiFetch wrapper pattern
- Codebase analysis: `apps/web/src/components/ui/dropdown-menu.tsx` -- Radix component wrapper pattern
- Codebase analysis: `packages/mcp-server/src/index.ts` -- MCP server API key usage pattern
- Codebase analysis: `apps/web/src/app/globals.css` -- section-label CSS class definition (line 314)

### Secondary (MEDIUM confidence)
- API key hashing with SHA-256 is industry standard for high-entropy tokens (Stripe, GitHub documentation)
- `secrets.token_hex()` is the recommended Python stdlib function for cryptographic token generation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all components already in the project, no new dependencies
- Architecture: HIGH -- follows established patterns exactly (dashboard page, FastAPI router, Supabase migration)
- Pitfalls: HIGH -- identified from codebase analysis and industry patterns
- API key security: HIGH -- SHA-256 hashing of high-entropy tokens is well-established

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable -- no fast-moving dependencies)
