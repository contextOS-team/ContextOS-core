# Coding Conventions

**Analysis Date:** 2026-03-12

## Naming Patterns

**Files:**
- Frontend: `kebab-case.tsx` for components (`generation-progress.tsx`, `integration-card.tsx`), `kebab-case.ts` for modules (`sync-progress.ts`, `ticket-provider.ts`, `context-feed.ts`)
- Backend Python: `snake_case.py` for all files (`github_linking.py`, `synthesis.py`, `linking.py`)
- Test files: Frontend uses `__tests__/kebab-case.test.ts`; backend uses `tests/test_<module>.py`

**Functions:**
- Frontend TypeScript: `camelCase` for all functions (`computeSyncState`, `detectTicketProvider`, `apiFetch`, `formatRelativeTime`)
- Backend Python: `snake_case` for all functions (`find_related_content`, `generate_context_page`, `decode_supabase_jwt`)
- Private/internal Python helpers are prefixed with `_` (`_find_explicit_refs`, `_find_hybrid_matches`, `_make_test_settings`)

**Variables:**
- Frontend: `camelCase` (`accessToken`, `ticketIdentifier`, `syncProgress`)
- Backend: `snake_case` (`mock_session`, `workspace_id`, `ticket_identifier`)
- Module-level constants: `UPPER_SNAKE_CASE` in both Python (`WEIGHT_EXPLICIT`, `HYBRID_SEARCH_LIMIT`, `TEST_JWT_SECRET`, `TEST_WORKSPACE_ID`) and TypeScript (`BACKEND_URL`, `SOURCE_LABELS`)

**Types/Classes/Interfaces:**
- Frontend TypeScript interfaces: `PascalCase` (`GenerationProgressProps`, `SyncState`, `ComputedSync`, `ProviderStatus`)
- Frontend type literals: `PascalCase` for types, `camelCase` for `type` keyword aliases
- Backend Python dataclasses and Pydantic models: `PascalCase` (`LinkedItem`, `LinkingResult`, `TicketProxy`, `UserContext`)
- SQLModel table classes: `PascalCase` (`GithubPullRequest`, `LinearTicket`, `ContextPage`)

**React Components:**
- Named exports (not default) for feature components: `export function GenerationProgress(...)`, `export function StepIcon(...)`
- `'use client'` directive at top of client components

## Code Style

**Formatting:**
- Frontend: No `.prettierrc` detected — relies on ESLint/editor defaults. Single quotes for strings in TypeScript (`'use client'`, import paths use single quotes).
- Backend: Ruff with `line-length = 100`, `target-version = "py312"` (`/Users/dauletashikbayev/Developer/ContextOS-core/backend/pyproject.toml`)

**Linting:**
- Frontend: ESLint extending `next/core-web-vitals` and `next/typescript` (`/Users/dauletashikbayev/Developer/ContextOS-core/apps/web/eslint.config.mjs`)
- Backend: Ruff (linting + formatting) and mypy with `strict = true` (`/Users/dauletashikbayev/Developer/ContextOS-core/backend/pyproject.toml`)

**TypeScript:**
- Strict mode enabled (`"strict": true` in `/Users/dauletashikbayev/Developer/ContextOS-core/apps/web/tsconfig.json`)
- `type` imports are used for type-only symbols: `import type { ActivityEvent } from '../types'`
- Path alias `@/` maps to `src/`; always use it for cross-directory imports

## Import Organization

**Frontend TypeScript order (observed pattern):**
1. React/Next.js framework imports (`'react'`, `'next/navigation'`)
2. Third-party packages (`'lucide-react'`, `'sonner'`)
3. Internal `@/components/ui/*` (shadcn components)
4. Internal `@/components/*` (feature components)
5. Internal `@/lib/*` (utilities, API client)
6. Relative path imports (same-directory types/helpers)

**Backend Python order:**
1. Standard library (`logging`, `uuid`, `dataclasses`, `datetime`)
2. Third-party (`fastapi`, `sqlalchemy`, `pydantic`, `pytest`)
3. Internal `src.*` imports
4. Test-only: `from tests.conftest import TEST_*`

**Path Aliases:**
- Frontend: `@/*` → `src/*` (configured in `tsconfig.json` and `vitest.config.ts`)

## Error Handling

**Frontend:**
- `apiFetch` throws `Error` with message `"API error {status}: {text}"` on non-ok responses (`/Users/dauletashikbayev/Developer/ContextOS-core/apps/web/src/lib/api.ts`)
- SSE stream errors are surfaced via `setGeneration({ status: 'error', ... })` — no thrown exceptions in UI components
- Toast notifications via `sonner` for user-facing errors

**Backend:**
- Auth errors raise `HTTPException(status_code=401)` via `get_current_user` in `/Users/dauletashikbayev/Developer/ContextOS-core/backend/src/dependencies.py`
- Route-level 404s use `raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=...)`
- JWT decode errors are caught (`except JWTError`) and re-raised as `HTTPException`
- Low-level services do not raise HTTP exceptions — they raise domain exceptions; routers translate to HTTP
- `try/except` used narrowly around external API calls; errors logged before raising

## Logging

**Backend:**
- Each module declares its own logger: `logger = logging.getLogger(__name__)`
- Standard Python `logging` module used throughout (structlog is a dependency but stdlib `logging` is the active pattern in most modules)
- Logger is always module-level, never passed as argument

**Frontend:**
- No structured logging — `console.error` / `console.log` used sparingly in error paths

## Comments

**When to Comment:**
- Module-level docstrings on all Python files summarizing purpose and coverage (e.g., `"""Tests for the linking engine.\n\nCovers:\n- ...`"""`)
- Function-level docstrings on all public Python functions, one-line summary style
- JSDoc on exported TypeScript functions (`apiFetch`, `computeSyncState`, `formatRelativeTime`)
- Inline comments explain non-obvious logic: scoring weights, edge cases, bug fixes

**Docstring style (Python):**
```python
def get_current_user(...) -> UserContext:
    """Decode JWT, look up user profile and workspace membership.

    Returns UserContext with user_id, email, workspace_id.
    Raises 401 if token is invalid or user not found.
    """
```

**Section separators:**
Both Python tests and TypeScript files use dashed comment banners to group related blocks:
```python
# ---------------------------------------------------------------------------
# Unit tests for decode_supabase_jwt
# ---------------------------------------------------------------------------
```
```typescript
// ---------------------------------------------------------------------------
// detectTicketProvider
// ---------------------------------------------------------------------------
```

## Function Design

**Size:** Functions are small and single-purpose. Pure computation logic is extracted into separate utility modules (`sync-progress.ts`, `ticket-provider.ts`) to allow unit testing without framework dependencies.

**Parameters:**
- Python: named parameters with type annotations; functions avoid `**kwargs` except in test helpers
- TypeScript: single `Props` interface for React components; plain object params for utility functions

**Return Values:**
- TypeScript: explicit return types on exported functions
- Python: all public functions annotated with `-> ReturnType`; `-> None` is explicit

## Module Design

**Frontend Exports:**
- Named exports only; no default exports for feature code
- `@/lib/api.ts` exports both functions and interfaces from a single file (flat API client pattern)
- Barrel files: not used for `@/lib`; UI components use individual imports

**Backend Module Pattern:**
```python
# module-level logger
logger = logging.getLogger(__name__)

# module-level constants
WEIGHT_EXPLICIT = 1.0

# dataclasses for data structures
@dataclass
class LinkedItem: ...

# public async functions
async def find_related_content(session, workspace_id, ticket): ...

# private helpers prefixed with _
async def _find_explicit_refs(...): ...
```

**SQLModel Models:**
- All table models extend `BaseModel` (from `/Users/dauletashikbayev/Developer/ContextOS-core/backend/src/models/base.py`) which provides `id: UUID`, `created_at`, `updated_at`, `deleted_at`
- Soft deletes via `deleted_at` field — never hard-delete records
- `table=True` flag marks ORM-mapped models; response schemas use `table=False` (plain Pydantic)

---

*Convention analysis: 2026-03-12*
