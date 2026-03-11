# Testing Patterns

**Analysis Date:** 2026-03-12

## Test Frameworks

### Frontend (TypeScript)

**Runner:**
- Vitest 4.x
- Config: `/Users/dauletashikbayev/Developer/ContextOS-core/apps/web/vitest.config.ts`
- Environment: `node` (no jsdom — DOM rendering is not tested)
- Path alias: `@/` resolved to `src/`

**Assertion Library:**
- Vitest built-in (`expect`, matchers from `vitest`)

**Run Commands:**
```bash
# From apps/web/
npx vitest              # Run all tests (watch mode)
npx vitest run          # Single run (CI)
npx vitest run --coverage  # With coverage
```

### Backend (Python)

**Runner:**
- pytest with pytest-asyncio
- Config: `[tool.pytest.ini_options]` in `/Users/dauletashikbayev/Developer/ContextOS-core/backend/pyproject.toml`
- `asyncio_mode = "auto"` — all async test functions run automatically without `@pytest.mark.asyncio` in most files
- `testpaths = ["tests"]`

**Coverage:**
- pytest-cov available as dev dependency

**Run Commands:**
```bash
# From backend/
pytest                     # Run all tests
pytest tests/test_linking.py  # Run single file
pytest -k "test_synthesis"    # Run matching tests
pytest --cov=src              # With coverage
```

## Test File Organization

### Frontend

**Location:** Co-located in `__tests__/` subdirectories next to the source code:
```
apps/web/src/
├── app/dashboard/activity/
│   └── __tests__/
│       └── formatters.test.ts
├── components/onboarding/
│   └── __tests__/
│       └── step-ticket-provider-logic.test.ts
└── lib/
    └── __tests__/
        ├── sync-progress.test.ts
        └── ticket-provider.test.ts
```

**Naming:** `<module-name>.test.ts` matching the source file name.

### Backend

**Location:** All tests in `/Users/dauletashikbayev/Developer/ContextOS-core/backend/tests/`
**Naming:** `test_<module>.py` matching the source module (e.g., `test_linking.py` for `src/services/linking.py`)
**Shared fixtures:** `/Users/dauletashikbayev/Developer/ContextOS-core/backend/tests/conftest.py`

```
backend/
├── src/
│   └── services/linking.py
└── tests/
    ├── conftest.py          # Shared fixtures (auth, settings, session, client)
    ├── test_linking.py
    ├── test_synthesis.py
    └── test_auth.py
```

## Test Structure

### Frontend Suite Organization

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { ActivityEvent } from '../types'
import { formatEventDescription } from '../formatters'

// Helper factory function (NOT a test fixture)
function mockEvent(overrides: Partial<ActivityEvent> = {}): ActivityEvent {
  return {
    id: 'evt-1',
    workspace_id: 'ws-1',
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Section grouping with comment banners
// ---------------------------------------------------------------------------

describe('formatEventDescription', () => {
  it('sync_started with integration metadata returns "{integration} sync started"', () => {
    const event = mockEvent({ event_type: 'sync_started', metadata: { integration: 'Linear' } })
    expect(formatEventDescription(event)).toBe('Linear sync started')
  })
})
```

**Patterns:**
- `describe` blocks named after the function being tested
- `it` descriptions are full sentences describing input and expected output
- `beforeEach`/`afterEach` used for `vi.useFakeTimers()` / `vi.useRealTimers()` pairs
- Factory helper functions (`mockEvent`, `makeStatuses`) defined at module scope, not inside tests

### Backend Test Organization

```python
"""Tests for the context page synthesis service.

Covers:
- Context page generation with mocked LLM
- Stale marking
- Prompt building from ticket and sources
- Upsert behavior (create and update)
"""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from tests.conftest import TEST_WORKSPACE_ID


def _make_mock_ticket() -> MagicMock:
    """Create a mock LinearTicket."""
    ticket = MagicMock()
    ticket.id = uuid4()
    ...
    return ticket


@pytest.mark.asyncio
async def test_generate_context_page_creates_new() -> None:
    """Should create a new context page when none exists."""
    mock_session = AsyncMock()
    ...
    assert result.status == "ready"
```

**Patterns:**
- Module docstring listing what is covered
- Private `_make_*` factory functions for test data (prefix `_`)
- `@pytest.mark.asyncio` used explicitly in some files; `asyncio_mode = "auto"` handles most cases
- All test functions have return type annotation `-> None`
- Test function docstrings in "Should ..." form

## Mocking

### Frontend

**Framework:** Vitest's `vi` object

```typescript
import { vi, beforeEach, afterEach } from 'vitest'

// Fake timers for time-dependent logic
beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-02-28T15:42:00Z'))
})
afterEach(() => {
  vi.useRealTimers()
})
```

**What to Mock:** Time-dependent behavior (`Date.now()`, `new Date()`); external API calls (via `vi.fn()` or module mocking).

**What NOT to Mock:** Pure functions, data transformations, business logic — these are tested directly with real implementations.

**Key approach:** Since `vitest.config.ts` uses `environment: 'node'`, UI tests extract pure logic into helper functions that can be tested without React rendering. See `/Users/dauletashikbayev/Developer/ContextOS-core/apps/web/src/components/onboarding/__tests__/step-ticket-provider-logic.test.ts` for the pattern of replicating component decision logic as pure functions for testing.

### Backend

**Framework:** `unittest.mock` — `MagicMock`, `AsyncMock`, `patch`

**Session mocking pattern (used in almost all tests):**
```python
mock_session = AsyncMock()

# Single query returning a scalar
mock_result = MagicMock()
mock_result.scalar_one_or_none.return_value = some_object

# Query returning multiple rows
mock_list_result = MagicMock()
mock_list_result.scalars.return_value.all.return_value = [item1, item2]

# Raw SQL returning tuples
mock_raw_result = MagicMock()
mock_raw_result.fetchall.return_value = [(uuid4(), "slack_message", ...)]

# Chain multiple queries in order
mock_session.execute.side_effect = [
    mock_result,       # 1st call
    mock_list_result,  # 2nd call
    mock_raw_result,   # 3rd call
]
```

**Context manager patching:**
```python
with patch(
    "src.services.linking.generate_embedding",
    new_callable=AsyncMock,
    return_value=[0.1] * 768,
):
    items = await _find_hybrid_matches(mock_session, WORKSPACE_ID, ticket)
```

**Model mocking:**
```python
def _make_ticket(identifier: str = "CON-16") -> MagicMock:
    """Create a mock LinearTicket that passes isinstance checks."""
    ticket = MagicMock(spec=LinearTicket)  # spec= ensures isinstance works
    ticket.id = uuid4()
    ticket.workspace_id = WORKSPACE_ID
    ticket.identifier = identifier
    return ticket
```

**FastAPI dependency override pattern (HTTP tests):**
```python
@pytest.fixture()
def app(mock_settings, mock_session):
    from src.db import get_session
    from src.main import app as fastapi_app

    async def _mock_get_session():
        yield mock_session

    fastapi_app.dependency_overrides[get_session] = _mock_get_session
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()
```

**What to Mock:** Database sessions, external API calls, LLM clients, embedding generation, OAuth HTTP calls.

**What NOT to Mock:** Business logic functions, Pydantic model validation, pure data transformations.

## Fixtures and Factories

### Frontend

**Test Data:** Module-scope factory functions returning typed objects with safe defaults:
```typescript
// Minimal factory with overrides pattern
const DISCONNECTED: ProviderStatus = {
  status: 'disconnected',
  external_name: null,
  connected_at: null,
}

function makeStatuses(
  overrides: Partial<IntegrationStatusResponse> = {},
): IntegrationStatusResponse {
  return {
    linear: DISCONNECTED,
    jira: DISCONNECTED,
    ...overrides,
  }
}
```

**Location:** Defined at the top of each test file; not shared across test files.

### Backend

**Shared Fixtures:** `/Users/dauletashikbayev/Developer/ContextOS-core/backend/tests/conftest.py` provides:
- `mock_settings` — injects test `Settings` instance into config singleton
- `mock_session` — `AsyncMock(spec=AsyncSession)` for DB calls
- `app` — FastAPI app with `get_session` overridden
- `client` — sync `TestClient`
- `async_client` — async `httpx.AsyncClient`
- `valid_token`, `expired_token` — pre-signed JWT strings
- `valid_auth_header`, `expired_auth_header` — ready-to-use header dicts
- `_reset_settings` — `autouse=True` fixture that clears settings singleton before/after every test

**Per-file fixtures:** Individual test files define additional `@pytest.fixture()` for module-specific context (e.g., `slack_settings`, `slack_app`, `mock_context_page`).

**Test constants (conftest):**
```python
TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-only"
TEST_USER_ID = "11111111-1111-1111-1111-111111111111"
TEST_WORKSPACE_ID = "22222222-2222-2222-2222-222222222222"
TEST_EMAIL = "test@example.com"
```

## Coverage

**Requirements:** No enforced coverage threshold detected.

**View Coverage:**
```bash
# Backend
pytest --cov=src --cov-report=html

# Frontend
npx vitest run --coverage
```

## Test Types

**Unit Tests (Frontend):**
- Scope: Pure functions — formatters, state machines, URL builders
- No DOM, no React, no external calls
- Files: `apps/web/src/lib/__tests__/`, `apps/web/src/app/dashboard/activity/__tests__/`

**Unit Tests (Backend):**
- Scope: Service functions with fully mocked DB sessions and external services
- No real database or HTTP calls
- Files: `backend/tests/test_linking.py`, `backend/tests/test_synthesis.py`, most test files

**Integration Tests (Backend):**
- Scope: FastAPI route handlers tested via `TestClient` / `AsyncClient`
- DB session mocked; HTTP layer (FastAPI middleware, routing, auth) is real
- Files: `backend/tests/test_auth.py`, `backend/tests/test_context_api.py`, `backend/tests/test_slack.py`

**E2E Tests:** Not present.

## Common Patterns

### Async Testing (Backend)

```python
# pytest-asyncio with asyncio_mode = "auto" — decorator optional
@pytest.mark.asyncio
async def test_find_explicit_refs_linked_prs() -> None:
    mock_session = AsyncMock()
    # ... setup ...
    items = await _find_explicit_refs(mock_session, WORKSPACE_ID, ticket)
    assert len(items) == 1
```

### Error / Exception Testing

```python
# Backend: pytest.raises
def test_jwt_decode_invalid_token(mock_settings) -> None:
    from src.auth import decode_supabase_jwt
    with pytest.raises(JWTError):
        decode_supabase_jwt("not-a-valid-jwt")

# Backend: HTTP error via TestClient
def test_get_context_page_not_found(client, valid_auth_header, mock_session) -> None:
    mock_session.execute.return_value.scalar_one_or_none.return_value = None
    resp = client.get("/api/context/MISSING-1", headers=valid_auth_header)
    assert resp.status_code == 404
```

### Collecting SSE Stream Events (Backend)

```python
async def _collect_events(stream) -> list[dict]:
    """Drain an async SSE generator into a list."""
    events = []
    async for event in stream:
        if event.data:
            events.append(json.loads(event.data))
    return events
```

### Test Isolation

Backend tests use `autouse=True` fixture `_reset_settings` in `conftest.py` to reset the settings singleton between every test, preventing `.env` values from leaking into tests. Per-test fixtures that override `dependency_overrides` always call `.clear()` in teardown.

---

*Testing analysis: 2026-03-12*
