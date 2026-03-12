# Phase 28: GitLab Project Selection & Code Indexing - Research

**Researched:** 2026-03-12
**Domain:** GitLab API integration, code indexing pipeline, React UI
**Confidence:** HIGH

## Summary

Phase 28 extends the existing GitHub code indexing experience to GitLab. The work is highly constrained and well-defined: the backend project listing/selection service (`gitlab_repos.py`) already exists from Phase 24, the code indexing pipeline (`code_indexer.py`, `code_index_worker.py`, `code_parser.py`) is provider-agnostic, and the GitHub UI component (`github-repos.tsx`) serves as a direct template. The primary work involves three areas: (1) creating a GitLab project selection frontend component mirroring `github-repos.tsx`, (2) adding `/index` and `/index/status` endpoints to the GitLab router that use the existing pipeline with GitLab OAuth token authentication, and (3) abstracting the clone authentication in `code_indexer.py` to support both GitHub App tokens and GitLab OAuth tokens.

The critical technical challenge is GitLab's 2-hour OAuth token expiry. The existing `ensure_valid_token()` in `gitlab_common.py` handles token refresh, but `code_indexer.py` currently hardcodes GitHub App token retrieval via `get_installation_token()`. This must be abstracted to a provider-aware pattern.

**Primary recommendation:** Mirror the GitHub implementation exactly, abstracting only the clone authentication layer. Do not redesign the pipeline.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GL-09 | Frontend project selection UI for GitLab | Mirror `github-repos.tsx` pattern; backend endpoints (`/repos`, `/repos/refresh`, `/repos/select`) already exist from Phase 24 |
| GL-10 | Code indexing integration for GitLab projects | Abstract `code_indexer.py` clone auth; add `/index` and `/index/status` endpoints to GitLab router; use existing Redis Stream worker |
| GL-11 | Index status tracking in integrations status | Add `selected_repos_count` for GitLab in `_build_provider_status()` in `integrations.py` |
</phase_requirements>

## Standard Stack

### Core (Already in Project)
| Library | Purpose | Why Standard |
|---------|---------|--------------|
| FastAPI | Backend router endpoints | Project standard |
| httpx | GitLab API calls | Already used in `gitlab_common.py` |
| React/Next.js | Frontend components | Project standard |
| Redis Streams | Async job processing | Used by `code_index_worker.py` |
| tree-sitter | Code parsing | Used by `code_parser.py` |

### No New Dependencies Required
This phase uses only existing libraries. No new installations needed.

## Architecture Patterns

### Pattern 1: Mirror GitHub Endpoint Structure
**What:** GitLab router gets the same `/index` and `/index/status` endpoint structure as GitHub.
**When to use:** Always -- consistency is the goal.

GitHub endpoints to mirror:
```
POST /api/github/index         -> POST /api/gitlab/index
GET  /api/github/index/status  -> GET  /api/gitlab/index/status
```

The existing GitLab router already has `/repos`, `/repos/refresh`, `/repos/select` from Phase 24.

### Pattern 2: Provider-Aware Clone Authentication
**What:** Abstract clone URL + token retrieval in `code_indexer.py` so it works for both GitHub and GitLab.
**When to use:** In `index_repo()` function.

Current hardcoded GitHub pattern:
```python
# code_indexer.py line 135-137
token = await get_installation_token(workspace_id, session, settings)
clone_url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
```

GitLab equivalent:
```python
token = await ensure_valid_token(session, workspace_id, settings)
clone_url = f"https://oauth2:{token}@gitlab.com/{repo_full_name}.git"
```

**Recommended approach:** Add a `provider` parameter to `index_repo()` and `index_workspace_repos()`. Use a helper function like:
```python
async def _get_clone_credentials(
    provider: str, workspace_id: UUID, session: AsyncSession, settings: Settings
) -> tuple[str, str]:
    """Return (clone_url_prefix, token) for the given provider."""
    if provider == "gitlab":
        token = await ensure_valid_token(session, workspace_id, settings)
        return f"https://oauth2:{token}@gitlab.com/", token
    else:  # github
        token = await get_installation_token(workspace_id, session, settings)
        return f"https://x-access-token:{token}@github.com/", token
```

### Pattern 3: GitLab Index Status Tracking
**What:** Store `code_index_status` and `code_index_last_at` in GitLab's `workspace_integrations.config` JSONB.
**When to use:** In `_update_index_status()` -- currently hardcoded to `provider == "github"`.

The existing `_update_index_status()` function filters by `provider == "github"`. It needs a `provider` parameter.

### Pattern 4: Frontend Component Mirroring
**What:** `gitlab-repos.tsx` mirrors `github-repos.tsx` with GitLab-specific adaptations.
**Key differences from GitHub:**
- Selection uses numeric project IDs (not string repo names)
- Display uses `path_with_namespace` (not `full_name`)
- Visibility uses `visibility` field (private/internal/public, not boolean `private`)
- API functions call `/api/gitlab/*` endpoints
- Label says "projects" not "repos"

### Pattern 5: API Client Functions
**What:** Add GitLab-specific API functions to `api.ts`.
**Functions needed:**
```typescript
// Already exists (Phase 24):
// connectGitlab(), disconnectGitlab()

// New functions needed:
getGitlabRepos()          // GET /api/gitlab/repos
refreshGitlabRepos()      // POST /api/gitlab/repos/refresh
selectGitlabRepos()       // POST /api/gitlab/repos/select
triggerGitlabIndex()       // POST /api/gitlab/index
getGitlabIndexStatus()     // GET /api/gitlab/index/status
```

Note: `getGitlabRepos` and `refreshGitlabRepos` can likely reuse the existing Phase 24 router endpoints directly. The `/repos`, `/repos/refresh`, and `/repos/select` endpoints already exist in the GitLab router.

### Recommended File Changes
```
Modified:
├── apps/web/src/lib/api.ts                           # Add 5 GitLab API functions
├── apps/web/src/app/dashboard/settings/tabs/
│   └── integration-cards.tsx                          # Render GitlabRepos under GitLab card
├── backend/src/routers/gitlab.py                      # Add /index and /index/status endpoints
├── backend/src/routers/integrations.py                # Add selected_repos_count for GitLab
├── backend/src/services/code_indexer.py               # Abstract clone auth (provider param)

Created:
├── apps/web/src/app/dashboard/integrations/
│   └── gitlab-repos.tsx                               # New component mirroring github-repos.tsx
```

### Anti-Patterns to Avoid
- **Separate code indexer for GitLab:** Do NOT create a `gitlab_code_indexer.py`. The pipeline is provider-agnostic -- only clone auth differs.
- **Duplicating `_update_index_status`:** Do NOT copy the function. Add a `provider` parameter instead.
- **Using `path_with_namespace` as selection key:** GitLab projects use numeric IDs for selection (per Phase 24 decision). The frontend sends `project_ids: number[]`, not strings.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Code parsing | Custom parser | Existing `code_parser.py` with tree-sitter | Already supports Python, TypeScript, JavaScript, Go, Rust, Java, etc. |
| Job queuing | New queue system | Existing Redis Stream `code_index:jobs` | `code_index_worker.py` already processes these jobs |
| Token refresh | Manual refresh logic | Existing `ensure_valid_token()` in `gitlab_common.py` | Handles 2-hour expiry, refresh token exchange, Vault storage |
| Embedding generation | Custom embedding | Existing `embedding_worker.py` pipeline | Automatically processes chunks via Redis Stream |

## Common Pitfalls

### Pitfall 1: GitLab Token Expiry During Clone
**What goes wrong:** GitLab OAuth tokens expire after 2 hours. If indexing multiple large projects, the token may expire mid-operation.
**Why it happens:** Unlike GitHub App installation tokens (1 hour, requested per-use), GitLab tokens are cached and may be close to expiry.
**How to avoid:** Call `ensure_valid_token()` before EACH repo clone, not once at the start of workspace indexing. The function handles refresh internally.
**Warning signs:** Clone failures with 401 errors after the first repo succeeds.

### Pitfall 2: Numeric ID vs Path Mismatch
**What goes wrong:** GitLab projects are selected by numeric ID but `code_chunks.repo_full_name` stores string paths.
**Why it happens:** Phase 24 decided on numeric IDs for selection (avoids URL encoding), but the code chunk table uses string identifiers.
**How to avoid:** When iterating selected projects for indexing, look up the `path_with_namespace` from the cached `available_projects` list using the numeric ID. Store `path_with_namespace` in `repo_full_name`.
**Warning signs:** Empty index results despite projects being selected.

### Pitfall 3: `_update_index_status` Hardcoded to GitHub
**What goes wrong:** The existing `_update_index_status()` function in `code_indexer.py` filters by `provider == "github"`. Calling it for GitLab indexing silently fails.
**Why it happens:** Function was written for GitHub only in Phase 7/12.
**How to avoid:** Add a `provider` parameter (default "github" for backward compatibility).

### Pitfall 4: `index_workspace_repos` Uses GitHub-Specific Imports
**What goes wrong:** The function imports from `github_repos` (`get_cached_repos`, `is_repo_monitored`) directly.
**Why it happens:** Function was written for GitHub only.
**How to avoid:** Create a parallel `index_gitlab_workspace_repos()` function or parameterize the existing one. The GitLab equivalent uses `gitlab_repos.get_cached_repos()` and `gitlab_repos.is_project_monitored()`.

### Pitfall 5: Frontend Selection State Type Mismatch
**What goes wrong:** GitHub uses `Set<string>` for selected repo names. GitLab uses numeric project IDs.
**Why it happens:** Different selection models between providers.
**How to avoid:** GitLab component should use `Set<number>` for `selectedIds` state, matching the `project_ids: list[int]` backend contract.

## Code Examples

### GitLab Index Endpoint (Backend)
```python
# In backend/src/routers/gitlab.py
@router.post("/index", status_code=status.HTTP_202_ACCEPTED)
async def trigger_index(
    user: UserContext = Depends(get_current_user),
) -> dict:
    """Trigger code indexing for all selected GitLab projects."""
    await enqueue_workspace_index_job(user.workspace_id, provider="gitlab")
    return {
        "status": "accepted",
        "message": "Code indexing started for selected GitLab projects",
    }
```

### GitLab Index Status Endpoint (Backend)
```python
# Mirror the GitHub /index/status pattern exactly
@router.get("/index/status")
async def get_index_status(
    user: UserContext = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get code indexing status for GitLab projects."""
    # Read status from GitLab workspace_integrations config
    # Query code_chunks where repo_full_name matches GitLab project paths
    ...
```

### Frontend API Functions
```typescript
// In apps/web/src/lib/api.ts
export interface GitlabProject {
  id: number
  path_with_namespace: string
  name: string
  visibility: 'private' | 'internal' | 'public'
  web_url: string
}

export interface GitlabReposResponse {
  repos: GitlabProject[]
  selected_projects: number[]
}

export function getGitlabRepos(): Promise<GitlabReposResponse> {
  return apiFetch<GitlabReposResponse>('/api/gitlab/repos')
}

export function refreshGitlabRepos(): Promise<GitlabReposResponse> {
  return apiFetch<GitlabReposResponse>('/api/gitlab/repos/refresh', {
    method: 'POST',
  })
}

export function selectGitlabRepos(
  projectIds: number[]
): Promise<{ selected_projects: number[] }> {
  return apiFetch<{ selected_projects: number[] }>(
    '/api/gitlab/repos/select',
    {
      method: 'POST',
      body: JSON.stringify({ project_ids: projectIds }),
    }
  )
}

export function triggerGitlabIndex(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/gitlab/index', {
    method: 'POST',
  })
}

export interface GitlabIndexStatus {
  status: string
  last_indexed_at: string | null
  repos: { repo: string; chunks: number }[]
}

export function getGitlabIndexStatus(): Promise<GitlabIndexStatus> {
  return apiFetch<GitlabIndexStatus>('/api/gitlab/index/status')
}
```

### Integrations Status Addition
```python
# In backend/src/routers/integrations.py, add to _build_provider_status():
if integration.provider == Provider.GITLAB:
    config = integration.config or {}
    selected = config.get("selected_projects", [])
    result["selected_repos_count"] = len(selected) if isinstance(selected, list) else 0
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GitHub-only code indexing | Provider-agnostic pipeline | Phase 12 (v1.0) | Pipeline is reusable, only auth differs |
| Hardcoded clone auth | Needs provider abstraction | Phase 28 (this phase) | Enables GitLab + future providers |

## Open Questions

1. **Redis Stream Job Provider Routing**
   - What we know: `enqueue_workspace_index_job()` currently takes only `workspace_id`. The worker calls `index_workspace_repos()` which is GitHub-specific.
   - What's unclear: Whether to add a `provider` field to the Redis job payload or create a separate function.
   - Recommendation: Add `provider` field to the job payload. The worker dispatches to the correct indexer based on provider. This is backward-compatible (default to "github" if missing).

2. **Code Chunks Table -- Distinguishing GitLab from GitHub**
   - What we know: `code_chunks.repo_full_name` stores `owner/repo` for GitHub. GitLab would store `namespace/project` (same format).
   - What's unclear: Whether the `/index/status` endpoint needs to filter by provider.
   - Recommendation: Add provider awareness to the status query. GitLab projects are stored in `workspace_integrations.config.available_projects` -- cross-reference to filter chunks.

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `backend/src/services/code_indexer.py` -- current GitHub-only clone auth
- Codebase inspection: `backend/src/services/gitlab_repos.py` -- existing project listing/selection
- Codebase inspection: `backend/src/services/gitlab_common.py` -- `ensure_valid_token()` with refresh
- Codebase inspection: `backend/src/routers/gitlab.py` -- existing endpoints (repos, sync, webhook)
- Codebase inspection: `backend/src/routers/github.py` -- reference `/index` and `/index/status` endpoints
- Codebase inspection: `apps/web/src/app/dashboard/integrations/github-repos.tsx` -- reference UI component
- Codebase inspection: `apps/web/src/lib/api.ts` -- existing GitHub API client functions
- Codebase inspection: `backend/src/services/code_index_worker.py` -- Redis Stream job processing
- Codebase inspection: `backend/src/routers/integrations.py` -- status endpoint with provider-specific fields

### Secondary (MEDIUM confidence)
- Phase 24 CONTEXT.md -- detailed implementation notes and architecture decisions
- Phase 24 decisions in STATE.md -- numeric project IDs, OAuth2 flow, webhook verification

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in project, no new dependencies
- Architecture: HIGH -- direct mirror of existing GitHub implementation, all reference code inspected
- Pitfalls: HIGH -- identified from actual code inspection (hardcoded GitHub refs, type mismatches)

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable -- no external API changes expected)
