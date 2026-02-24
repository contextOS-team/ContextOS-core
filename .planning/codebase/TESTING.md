# Testing Patterns

**Analysis Date:** 2026-02-24

## Current State

Testing infrastructure is configured but implementation is minimal. This document establishes patterns for new tests as the project evolves.

## Test Frameworks

### Backend (Python)

**Runner:**
- pytest
- Config: Not yet created (uses pytest defaults)

**Async Testing:**
- pytest-asyncio for async function testing
- Installed as dev dependency in `backend/pyproject.toml`

**Run Commands:**
```bash
cd backend && . .venv/bin/activate
pytest                           # Run all tests
pytest -v                        # Verbose output
pytest -k test_name              # Run specific test
pytest --cov=src                 # With coverage
pytest -x                        # Stop on first failure
pytest -s                        # Show print statements
```

### Frontend (TypeScript/React)

**Not yet configured** - Framework decision pending. When implemented, likely options:
- Vitest (fast, ESM-native, Vite-like syntax)
- Jest (traditional, broad ecosystem)

**Type Testing:**
```bash
cd apps/web && pnpm typecheck   # TypeScript compilation
```

### MCP Server (TypeScript)

**Not yet configured** - Tests can be added to `packages/mcp-server/`.

## Test File Organization

### Backend

**Location Pattern:**
```
backend/
├── src/
│   ├── api/
│   │   ├── routes.py
│   │   └── test_routes.py          # Co-located with source
│   ├── agents/
│   │   ├── ticket_agent.py
│   │   └── test_ticket_agent.py
│   └── config.py
└── tests/                           # Alternative: integration tests
    ├── conftest.py                  # Shared fixtures
    └── test_integration.py
```

**Naming:**
- Test files: `test_*.py` or `*_test.py`
- Test functions: `test_<function_or_behavior_name>`
- Test classes: `Test<ClassName>`

### Frontend

**Location Pattern (proposed):**
```
apps/web/src/
├── components/
│   ├── Button.tsx
│   ├── Button.test.ts              # Co-located unit tests
│   └── __tests__/
│       └── Button.integration.test.ts
├── lib/
│   ├── utils.ts
│   └── utils.test.ts
└── __tests__/
    └── setup.ts                    # Shared test utilities
```

**Naming:**
- Unit tests: `Component.test.ts` (co-located)
- Integration tests: `__tests__/Feature.integration.test.ts`
- E2E tests: `e2e/` directory (when Playwright/Cypress added)

## Backend Test Structure

### Basic Test Pattern

**File: `backend/src/api/test_routes.py`**

```python
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

from src.main import app
from src.config import Settings


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
async def async_client():
    """Create an async test client."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_returns_ok(self, client):
        """Health endpoint should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestAsyncEndpoint:
    """Test endpoints with async operations."""

    @pytest.mark.asyncio
    async def test_context_synthesis(self, async_client):
        """Synthesizing context should return generated page."""
        response = await async_client.post(
            "/api/context/synthesize",
            json={"ticket_id": "123", "workspace_id": "ws-1"}
        )
        assert response.status_code == 200
        assert "content" in response.json()
```

### Fixture Patterns

**File: `backend/tests/conftest.py`**

```python
import pytest
from unittest.mock import Mock, patch

from src.config import Settings


@pytest.fixture
def mock_settings():
    """Provide mock settings."""
    settings = Mock(spec=Settings)
    settings.ENVIRONMENT = "test"
    settings.ANTHROPIC_API_KEY = "test-key"
    return settings


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    with patch("src.api.routes.supabase") as mock:
        yield mock


@pytest.fixture
def mock_anthropic():
    """Mock Anthropic Claude client."""
    with patch("src.synthesis.client.Anthropic") as mock:
        yield mock
```

### Database Testing

**Pattern: Use test database or fixtures**

```python
import pytest
from supabase import create_client

# Option 1: Mock database operations
@pytest.fixture
def mock_db():
    """Mock database client."""
    from unittest.mock import Mock
    return Mock()


# Option 2: Real test database (for integration tests)
@pytest.fixture
def supabase_test_client():
    """Connect to test Supabase instance."""
    return create_client(
        url="http://localhost:54321",  # Local Supabase
        key="test-key"
    )
```

### Async Test Pattern

```python
import pytest

class TestAsyncSynthesis:
    """Tests for async synthesis operations."""

    @pytest.mark.asyncio
    async def test_synthesis_generates_summary(self):
        """Should generate context summary for ticket."""
        from src.synthesis import synthesize_context

        result = await synthesize_context(
            ticket_id="linear-123",
            workspace_id="ws-1"
        )
        assert result is not None
        assert result.title is not None
        assert result.content is not None

    @pytest.mark.asyncio
    async def test_synthesis_handles_missing_ticket(self):
        """Should raise error for missing ticket."""
        from src.synthesis import synthesize_context

        with pytest.raises(ValueError):
            await synthesize_context(
                ticket_id="nonexistent",
                workspace_id="ws-1"
            )
```

## Frontend Test Structure

### Unit Test Pattern (Proposed)

**File: `apps/web/src/components/Button.test.ts`**

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";

describe("Button Component", () => {
  it("renders with label", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: /click me/i })).toBeInTheDocument();
  });

  it("handles click events", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Click</Button>);

    const button = screen.getByRole("button");
    await userEvent.click(button);

    expect(onClick).toHaveBeenCalledOnce();
  });

  it("supports disabled state", () => {
    render(<Button disabled>Disabled</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});
```

### Hook Test Pattern (Proposed)

**File: `apps/web/src/hooks/useWorkspace.test.ts`**

```typescript
import { renderHook, act } from "@testing-library/react";
import { useWorkspace } from "./useWorkspace";

describe("useWorkspace Hook", () => {
  it("loads workspace data", async () => {
    const { result } = renderHook(() => useWorkspace("ws-1"));

    expect(result.current.loading).toBe(true);

    // Wait for async load
    await act(async () => {
      await vi.waitFor(() => expect(result.current.loading).toBe(false));
    });

    expect(result.current.workspace).toBeDefined();
  });

  it("handles fetch errors", async () => {
    const { result } = renderHook(() => useWorkspace("invalid"));

    await act(async () => {
      await vi.waitFor(() => expect(result.current.loading).toBe(false));
    });

    expect(result.current.error).toBeDefined();
  });
});
```

## Mocking Patterns

### Backend Mocking

**Mock External APIs:**

```python
import pytest
from unittest.mock import patch, AsyncMock

@pytest.mark.asyncio
async def test_sync_linear_tickets():
    """Test Linear API sync without making real requests."""
    with patch("src.ingestion.linear.LinearClient") as mock_client:
        mock_client.return_value.get_tickets = AsyncMock(
            return_value=[
                {
                    "id": "ticket-1",
                    "title": "Fix auth bug",
                    "status": "In Progress"
                }
            ]
        )

        from src.ingestion.linear import sync_linear_tickets

        tickets = await sync_linear_tickets(workspace_id="ws-1")
        assert len(tickets) == 1
        assert tickets[0]["title"] == "Fix auth bug"
```

**Mock Database:**

```python
@pytest.fixture
def mock_supabase():
    """Mock Supabase operations."""
    from unittest.mock import Mock
    mock = Mock()
    mock.table.return_value.select.return_value.execute.return_value.data = []
    return mock
```

### Frontend Mocking

**Mock API Calls:**

```typescript
import { vi } from "vitest";
import * as api from "@/lib/api";

describe("Context Synthesis", () => {
  it("fetches context data", async () => {
    vi.spyOn(api, "fetchContext").mockResolvedValueOnce({
      id: "ctx-1",
      title: "Bug Fix Context",
      content: "...",
    });

    // Test component that uses fetchContext
    // ...
  });
});
```

**Mock Supabase:**

```typescript
import { createClient } from "@supabase/supabase-js";
import { vi } from "vitest";

vi.mock("@supabase/supabase-js", () => ({
  createClient: vi.fn(() => ({
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
    },
    from: vi.fn(() => ({
      select: vi.fn().mockResolvedValue({ data: [] }),
    })),
  })),
}));
```

## What to Mock / What NOT to Mock

### Backend

**DO Mock:**
- External API calls (Linear, Slack, Notion)
- Anthropic Claude API (expensive)
- Redis operations (test in isolation)
- Email/notification services

**DO NOT Mock:**
- Pydantic validation
- Local business logic
- Database schema validation (use test DB fixtures)
- Configuration/Settings

### Frontend

**DO Mock:**
- API calls to backend
- Supabase auth and data operations
- Analytics (PostHog, Sentry)
- Browser APIs (localStorage, fetch)

**DO NOT Mock:**
- Component rendering
- React hooks internals
- Built-in browser events
- TypeScript types

## Coverage Goals

### Backend

**Current Target:** Not enforced yet

**Recommended:**
- Critical paths (API routes, synthesis): 80%+
- Utilities: 70%+
- Integration tests: Critical workflows only

**Generate Coverage:**
```bash
cd backend && . .venv/bin/activate
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Frontend

**Current Target:** Not configured

**Recommended:**
- Components: 60%+ (focus on user interactions)
- Hooks: 70%+ (critical to app behavior)
- Utils: 80%+

**Note:** Code coverage is a guide, not a goal. Prioritize testing critical paths and error cases.

## Common Test Patterns

### Testing API Endpoints

```python
class TestCreateContext:
    """Test context creation endpoint."""

    def test_create_requires_auth(self, client):
        """Unauthenticated requests should fail."""
        response = client.post("/api/context", json={})
        assert response.status_code == 401

    def test_create_with_ticket(self, client, mock_auth_header):
        """Should create context for valid ticket."""
        response = client.post(
            "/api/context",
            json={"ticket_id": "linear-123"},
            headers=mock_auth_header
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "generating"
```

### Testing Pydantic Models

```python
from pydantic import ValidationError
import pytest

from src.models import ContextPageData

def test_context_page_validation():
    """Valid context page should pass validation."""
    data = {
        "title": "Bug fix",
        "content": "Fix login bug",
        "status": "ready"
    }
    page = ContextPageData(**data)
    assert page.title == "Bug fix"

def test_context_page_invalid_status():
    """Invalid status should raise validation error."""
    data = {
        "title": "Bug fix",
        "content": "...",
        "status": "invalid"
    }
    with pytest.raises(ValidationError):
        ContextPageData(**data)
```

### Testing Error Cases

```python
import pytest

def test_synthesis_with_empty_context(self):
    """Synthesis should handle empty source data gracefully."""
    result = synthesize_context(
        sources=[],
        ticket_title="Test"
    )
    # Should return minimal valid output, not crash
    assert result is not None
    assert result.content is not None

def test_api_timeout_handling(self, client, mock_linear_timeout):
    """Should handle Linear API timeout gracefully."""
    response = client.post("/api/sync/linear")
    assert response.status_code == 504  # Gateway Timeout
    assert "timeout" in response.json()["error"].lower()
```

## Test Execution

### Run All Tests

**Backend:**
```bash
cd backend && . .venv/bin/activate && pytest
```

**Frontend (when configured):**
```bash
cd apps/web && pnpm test
```

### Run Specific Tests

**By file:**
```bash
pytest backend/src/api/test_routes.py
```

**By test name:**
```bash
pytest -k test_create_context
```

**By marker:**
```bash
pytest -m asyncio          # Only async tests
pytest -m slow -v          # Only slow tests (if marked)
```

### Watch Mode (Development)

**Backend:**
```bash
cd backend && . .venv/bin/activate
pytest-watch -- -x --tb=short
```

**Frontend (when configured):**
```bash
cd apps/web && pnpm test --watch
```

## CI/CD Integration

**Not yet configured** - Will be added when CI pipeline is set up.

Recommended:
- Run tests on PR and main branch
- Fail if coverage drops
- Test matrix: Python 3.12, Node.js 22+
- Separate fast (unit) and slow (integration) test runs

---

*Testing analysis: 2026-02-24*
