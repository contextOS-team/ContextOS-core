# Coding Conventions

**Analysis Date:** 2026-02-24

## Overview

ContextOS is a multi-language monorepo with three main codebases:
- **Frontend**: TypeScript/React (Next.js 15)
- **Backend**: Python (FastAPI)
- **MCP Server**: TypeScript (Node.js)

Each follows its language's established best practices with unified principles around naming, structure, and error handling.

## Naming Patterns

### TypeScript/JavaScript (Frontend & MCP Server)

**Files:**
- Components: PascalCase (e.g., `UserProfile.tsx`, `ContextCard.tsx`)
- Utils/Helpers: camelCase (e.g., `formatDate.ts`, `parseMarkdown.ts`)
- Hooks: camelCase with `use` prefix (e.g., `useWorkspace.ts`, `useAuth.ts`)
- Pages: Match Next.js conventions (e.g., `app/page.tsx`, `app/settings/page.tsx`)

**Functions/Variables:**
- camelCase for functions and variables
- UPPER_SNAKE_CASE for constants
- Descriptive names that reflect intent

**Types/Interfaces:**
- PascalCase (e.g., `interface UserProfile`, `type ContextPageData`)
- Suffix with `Type` or `Props` for clarity when needed (e.g., `UserProfileProps`)

**Path Aliases:**
- Frontend: `@/*` resolves to `apps/web/src/*` (defined in `tsconfig.json`)
- Enables clean imports: `import Button from '@/components/Button'`

### Python (Backend)

**Files:**
- Modules: snake_case (e.g., `config.py`, `api_handler.py`)
- Classes: PascalCase (e.g., `Settings`, `LinearClient`)
- Private modules: Leading underscore (e.g., `_internal.py`)

**Functions/Variables:**
- snake_case for functions and variables
- UPPER_SNAKE_CASE for constants
- Descriptive, explicit names

**Classes:**
- PascalCase following Python conventions
- Inherit from appropriate base classes (e.g., `BaseSettings` from pydantic)

**Pydantic Models:**
- PascalCase class names
- Field validation with validators if needed

### SQL (Database Schema)

**Tables:**
- snake_case, plural form (e.g., `workspaces`, `linear_tickets`, `slack_messages`)
- Schema-prefixed: `public.table_name`

**Columns:**
- snake_case
- Meaningful names that indicate content type
- Use suffixes for clarity:
  - `_at` for timestamps (e.g., `created_at`, `updated_at`, `slack_created_at`)
  - `_id` for foreign/external IDs (e.g., `slack_ts`, `linear_id`, `notion_id`)
  - `_url` for URIs (e.g., `avatar_url`, `url`)

**Constraints:**
- Primary keys: `id` (UUID with `default gen_random_uuid()`)
- Foreign keys: `{table}_id`
- Check constraints: `check (column in ('value1', 'value2'))`

**Indexes:**
- Implicit naming via Supabase (platform-generated)
- Create indexes on:
  - Vector similarity searches (HNSW algorithm for pgvector)
  - Text search columns (GIN indexes with `gin_trgm_ops`)
  - Foreign key lookups
  - Frequently filtered columns

## Code Style

### TypeScript/JavaScript

**Formatting:**
- Tool: ESLint (via Next.js config)
- Extends: `next/core-web-vitals`, `next/typescript`
- Config: `apps/web/eslint.config.mjs`
- Strict TypeScript mode enabled (`strict: true` in `tsconfig.json`)

**Key Settings:**
- Target: ES2017 for frontend, ES2022 for MCP server
- Module resolution: bundler (Next.js), Node16 (MCP)
- No implicit any
- Isolated modules for better build performance

**Import Organization:**
1. External dependencies (React, Next.js, libraries)
2. Type imports from external packages
3. Absolute path aliases (`@/`)
4. Relative imports
5. Side effects (styles, polyfills)

Example:
```typescript
import type { NextConfig } from "next";
import React from "react";

import { Button } from "@/components/ui/Button";
import { parseMetadata } from "@/lib/parsers";

import styles from "./page.module.css";
```

**Error Handling:**
- Use try-catch for async operations
- Return error objects or union types instead of throwing from utilities
- Pass errors through with context

### Python

**Formatting:**
- Tool: Ruff (linter and formatter)
- Config: `backend/ruff.toml`
- Settings:
  - Line length: 88 characters
  - Target version: Python 3.12
  - Rules: E (errors), F (pyflakes), I (imports), UP (upgrades)

**Key Settings:**
- Strict type checking with mypy
- Pydantic v2 for data validation
- UPPER_SNAKE_CASE for env variables in Settings class
- snake_case for function and variable names

**Import Organization:**
1. Standard library imports
2. Third-party imports (FastAPI, Pydantic, etc.)
3. Local imports (relative with `.`)
4. Blank line between groups

Example:
```python
from typing import Optional
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from .config import get_settings
```

**Error Handling:**
- Use Pydantic validators for input validation
- Raise appropriate HTTP exceptions in FastAPI routes
- Log errors with context (use logging module)
- Return meaningful error messages to clients

### SQL

**Style:**
- UPPERCASE keywords (CREATE TABLE, SELECT, INSERT, etc.)
- Lowercase identifiers (table names, column names)
- Spaces around operators
- Consistent indentation (2 spaces)
- Comments above logical sections (`-- ============================================================`)
- Functions: `plpgsql` language for Postgres functions

**Migrations:**
- File format: `NNNNN_description.sql` (e.g., `00001_initial_schema.sql`)
- Idempotent: Use `create table if not exists`, `drop if exists`
- Include comments explaining the schema
- Apply auto-update triggers for `updated_at` columns

## Comments

### When to Comment

**TypeScript/JavaScript:**
- Complex algorithms or non-obvious logic
- TSDoc/JSDoc for public APIs and components
- Avoid obvious comments (e.g., `// increment counter`)
- Explain the "why" not the "what"

Example:
```typescript
/**
 * Synthesizes context for a Linear ticket by querying embeddings
 * and generating a summary via Claude.
 *
 * @param ticketId - Linear ticket UUID
 * @param workspaceId - Workspace context
 * @returns Generated context page with sources
 */
async function synthesizeContext(ticketId: string, workspaceId: string) {
  // ...
}
```

**Python:**
- Docstrings for modules, classes, and functions
- Use triple-quoted strings (""" """)
- Follow NumPy or Google docstring style
- Comment non-obvious logic

Example:
```python
def handle_updated_at():
    """
    Trigger function that automatically updates the updated_at timestamp
    when a row is modified.
    """
    pass
```

**SQL:**
- Section headers for logical groupings
- Explain complex constraints or indexes
- Document custom functions

## Function Design

### TypeScript/JavaScript

**Size:**
- Prefer functions under 50 lines
- Extract complex logic into separate functions
- One responsibility per function

**Parameters:**
- Maximum 3-4 parameters
- Use object destructuring for multiple related params
- Use optional chaining and nullish coalescing

**Return Values:**
- Type-annotate return values
- Use union types or discriminated unions for multiple outcomes
- Prefer returning data over void

### Python

**Size:**
- Prefer functions under 40 lines
- Use comprehensions for simple iterations
- Extract helper functions for complex logic

**Parameters:**
- Type hints required (PEP 484)
- Use `Optional[T]` for nullable values
- Default values for optional parameters

**Return Values:**
- Always include return type hints
- Use `Optional[T]` for nullable returns
- Use tuples for multiple return values (sparingly)

## Module Design

### TypeScript/JavaScript

**Exports:**
- Export interfaces/types for public APIs
- Use named exports for functions and components
- Default exports for pages (Next.js convention)
- Re-export common utilities in barrel files (`index.ts`)

Example barrel file (`src/components/ui/index.ts`):
```typescript
export { Button } from './Button';
export { Card } from './Card';
export { Dialog } from './Dialog';
export type { ButtonProps } from './Button';
```

**Directory Structure:**
- Components co-located with styles
- Utils grouped by domain
- Types in separate `types.ts` or inline
- Tests co-located with source (`Component.test.ts`)

### Python

**Exports:**
- Use `__all__` to define public API
- Import from submodules explicitly
- Avoid wildcard imports in production code

Example:
```python
# src/api/__init__.py
from .routes import router

__all__ = ["router"]
```

**Directory Structure:**
- `src/api/routes/` for endpoint handlers
- `src/agents/` for LangGraph agent definitions
- `src/synthesis/` for context synthesis logic
- `src/ingestion/` for data collection
- `src/embeddings/` for vector operations
- `src/workers/` for Celery background jobs
- `src/config.py` for settings singleton

## Environment Configuration

**Frontend (.env):**
- `NEXT_PUBLIC_*` prefix for browser-exposed variables
- Typically: Supabase URLs/keys, app URLs, PostHog tokens
- Example: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_APP_URL`

**Backend (.env):**
- All keys secret (no prefix)
- Settings loaded via Pydantic BaseSettings
- Located at `backend/../.env` (project root)
- Example: `ANTHROPIC_API_KEY`, `SUPABASE_KEY`, `REDIS_URL`

**Shared:**
- `ENVIRONMENT` for environment selection (dev/staging/prod)
- `BACKEND_URL` for frontend-to-backend communication

## Build & Development

### TypeScript/JavaScript

**Scripts (package.json):**
- `dev`: Start development server (Next.js with Turbopack)
- `build`: Production build
- `start`: Run production build
- `lint`: Run ESLint (Next.js)
- `typecheck`: Run tsc without emitting

**Run Commands:**
```bash
cd apps/web && pnpm dev        # Frontend dev
cd apps/web && pnpm lint       # Lint and type check
cd apps/web && pnpm build      # Build for production
```

### Python

**Scripts (Makefile):**
- `setup`: Initialize venv, install deps, start Docker services
- `dev-backend`: Run uvicorn with reload
- `lint`: Run ruff check
- `typecheck`: Run mypy
- `test`: Run pytest

**Run Commands:**
```bash
cd backend && . .venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Format & Lint:**
```bash
ruff check .        # Check for issues
ruff format .       # Auto-format code
mypy src/           # Type checking
```

---

*Convention analysis: 2026-02-24*
