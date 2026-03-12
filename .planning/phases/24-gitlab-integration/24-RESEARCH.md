# Phase 24: GitLab Integration - Research

**Researched:** 2026-03-09
**Domain:** GitLab REST API v4, OAuth2, Webhooks, Merge Request ingestion
**Confidence:** HIGH

## Summary

GitLab integration mirrors the existing GitHub integration architecture almost exactly. The project already has a well-established pattern: OAuth connect/callback/disconnect/status endpoints, provider-specific models (PR/review tables), sync services with backfill, webhook event processors, and frontend IntegrationCard + onboarding SourceCard components. GitLab's REST API v4 maps cleanly to these patterns -- merge requests replace pull requests, notes/discussions replace reviews, and GitLab's standard OAuth2 authorization code flow replaces GitHub App installation flow.

The key structural difference is that GitLab uses standard OAuth2 (authorization code + refresh token) rather than GitHub's App installation model with JWT-signed tokens. This is actually simpler -- it matches the Linear/Slack/Notion OAuth pattern already in the codebase rather than GitHub's unique App JWT flow. GitLab tokens expire after 2 hours (7200 seconds) and include a refresh_token, fitting perfectly into the existing `oauth_common.py` infrastructure.

The implementation should follow the GitHub integration file-for-file: `models/gitlab.py`, `services/gitlab_oauth.py`, `services/gitlab_sync.py`, `services/gitlab_webhook.py`, `services/gitlab_common.py`, `services/gitlab_repos.py`, `services/gitlab_linking.py`, `routers/gitlab.py`. The database migration creates parallel tables (`gitlab_merge_requests`, `gitlab_reviews`) and adds `'gitlab'` to the provider check constraints.

**Primary recommendation:** Clone the GitHub integration architecture pattern-for-pattern, substituting GitLab API endpoints and OAuth2 flow. No new libraries needed -- httpx handles all API calls.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GL-01 | GitLab OAuth2 connect/callback/disconnect/status | Standard OAuth2 authorization code flow with refresh tokens; follows Linear/Slack pattern in oauth_common.py |
| GL-02 | GitLab MR ingestion (sync + backfill) | REST API v4 GET /projects/:id/merge_requests with pagination; maps to existing sync_adapter pattern |
| GL-03 | GitLab review/note ingestion | Notes API + Discussions API for diff-level comments; stored in gitlab_reviews table |
| GL-04 | MR-to-Linear ticket linking | Reuse existing branch name pattern parsing from github_linking.py; same extract_linear_issue_id logic |
| GL-05 | GitLab webhook sync (MR events) | Webhook events with object_kind="merge_request" and note events; secret token verification |
| GL-06 | GitLab project/repo selection | REST API v4 GET /projects with membership=true; cache in workspace_integrations.config JSONB |
| GL-07 | GitLab source in onboarding wizard sources grid | Add GitLabLogo SVG + SourceCard in step-sources.tsx; add IntegrationCard in settings integrations tab |
| GL-08 | Database migration for GitLab tables | gitlab_merge_requests + gitlab_reviews tables with RLS, indexes, triggers; add 'gitlab' to provider constraints |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | (existing) | GitLab REST API v4 calls | Already used for GitHub/Notion API calls; HTTP/2 support, async |
| pyjwt | (existing) | NOT needed for GitLab | GitLab uses standard OAuth2, not JWT-signed App tokens |
| sqlmodel | (existing) | ORM models for gitlab_merge_requests/gitlab_reviews | Project-wide ORM choice |
| pydantic | (existing) | Request/response validation in router | Existing pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| oauth_common.py | (existing) | sign_oauth_state, verify_state_or_raise, upsert_oauth_token, upsert_workspace_integration | All OAuth lifecycle operations |
| vault.py | (existing) | Encrypted token storage | Store GitLab access_token and refresh_token in Supabase Vault |
| sync_adapter.py | (existing) | SyncAdapter protocol, SyncRunLogger, update_cursor_status | Sync service conforms to this protocol |
| embedding_worker.py | (existing) | enqueue_embedding_job | Queue MR description embeddings |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx direct | python-gitlab SDK | Adds dependency; httpx is project standard; SDK is overkill for targeted API calls |
| Standard OAuth2 | GitLab App (like GitHub App) | GitLab doesn't have an equivalent App model; standard OAuth2 is correct |

**Installation:**
```bash
# No new packages needed -- all dependencies already in project
```

## Architecture Patterns

### Recommended Project Structure
```
backend/src/
  models/
    gitlab.py              # GitlabMergeRequest, GitlabReview SQLModel classes
  services/
    gitlab_oauth.py        # OAuth2 connect/callback/disconnect/status/token refresh
    gitlab_sync.py         # MR + review sync with 60-day backfill
    gitlab_webhook.py      # Webhook event processor (MR, note events)
    gitlab_common.py       # Shared helpers: headers, rate limit, timestamp parsing, bot filter
    gitlab_repos.py        # Project listing, selection, caching
    gitlab_linking.py      # MR-to-Linear ticket linking via branch name
  routers/
    gitlab.py              # FastAPI router: /api/gitlab/*
apps/web/src/
  components/icons/brand-logos.tsx  # Add GitLabLogo SVG
  components/onboarding/step-sources.tsx  # Add GitLab SourceCard
  app/dashboard/settings/page.tsx  # Add GitLab IntegrationCard
  app/dashboard/integrations/gitlab-repos.tsx  # GitLab project selection component
  lib/api.ts               # Add GitLab API client functions
supabase/migrations/
  00019_gitlab_tables.sql   # DB migration
backend/src/
  config.py                # Add GITLAB_* settings
  main.py                  # Register gitlab_router
  models/integration.py    # Add GITLAB to Provider enum
```

### Pattern 1: OAuth2 Authorization Code Flow (matches Linear/Slack)
**What:** Standard OAuth2 with authorization code exchange and refresh tokens
**When to use:** GitLab uses standard OAuth2 (not an App model like GitHub)
**Example:**
```python
# GitLab OAuth2 URLs
GITLAB_AUTH_URL = "https://gitlab.com/oauth/authorize"
GITLAB_TOKEN_URL = "https://gitlab.com/oauth/token"
GITLAB_API_BASE = "https://gitlab.com/api/v4"

# Authorization URL construction
def build_auth_url(state: str, settings: Settings) -> str:
    params = {
        "client_id": settings.GITLAB_CLIENT_ID,
        "redirect_uri": settings.gitlab_redirect_uri,
        "response_type": "code",
        "state": state,
        "scope": "read_api",  # Minimal scope for MR/project read access
    }
    return f"{GITLAB_AUTH_URL}?{urlencode(params)}"

# Token exchange (callback handler)
async def exchange_code(code: str, settings: Settings) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(GITLAB_TOKEN_URL, data={
            "client_id": settings.GITLAB_CLIENT_ID,
            "client_secret": settings.GITLAB_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.gitlab_redirect_uri,
        })
    return resp.json()  # {"access_token": "...", "refresh_token": "...", "expires_in": 7200}
```

### Pattern 2: MR Sync with Pagination (mirrors github_sync.py)
**What:** Fetch merge requests from GitLab API v4 with keyset/offset pagination
**When to use:** Initial backfill and periodic sync
**Example:**
```python
# GitLab uses offset pagination (page + per_page)
url = f"{GITLAB_API_BASE}/projects/{project_id}/merge_requests"
params = {"state": "all", "order_by": "updated_at", "sort": "desc", "per_page": 100}

async with httpx.AsyncClient() as client:
    while url:
        resp = await client.get(url, headers=gitlab_headers(token), params=params)
        mrs = resp.json()
        for mr_data in mrs:
            # Process MR...
            pass
        # GitLab returns next page URL in Link header (same RFC 5988 as GitHub)
        url = parse_link_next(resp.headers.get("link"))
        params = {}  # params already in the Link URL
```

### Pattern 3: Webhook Event Processing (mirrors github_webhook.py)
**What:** Process GitLab webhook POST events for real-time MR updates
**When to use:** GitLab sends webhooks on MR create/update/merge/close and note events
**Example:**
```python
# GitLab webhook payload structure
# object_kind: "merge_request" or "note"
# object_attributes.action: "open", "close", "reopen", "update", "merge", "approval"

async def process_gitlab_event(event_type: str, payload: dict) -> None:
    object_kind = payload.get("object_kind")
    if object_kind == "merge_request":
        await handle_merge_request_event(payload)
    elif object_kind == "note":
        noteable_type = payload.get("object_attributes", {}).get("noteable_type")
        if noteable_type == "MergeRequest":
            await handle_mr_note_event(payload)
```

### Anti-Patterns to Avoid
- **Do NOT use python-gitlab SDK:** Project uses httpx for all API calls. Adding a provider-specific SDK creates inconsistency.
- **Do NOT create a shared "code hosting" abstraction layer:** GitHub and GitLab are similar but differ enough (App JWT vs OAuth2, PR vs MR terminology, different webhook payloads) that a premature abstraction adds complexity without value. Keep them as parallel implementations.
- **Do NOT auto-monitor all projects:** Follow GitHub pattern -- user explicitly selects projects to monitor.
- **Do NOT store tokens in plaintext:** All tokens go through Supabase Vault (store_token/read_token/delete_token).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth state CSRF | Custom state signing | `oauth_common.sign_oauth_state` / `verify_state_or_raise` | Already battle-tested with HMAC-SHA256 |
| Token storage | DB columns with plaintext | `vault.store_token` / `vault.read_token` | Supabase Vault encryption at rest |
| Integration lifecycle | Custom connect/disconnect | `oauth_common.upsert_oauth_token` / `upsert_workspace_integration` / `disconnect_provider` | Handles soft-delete reuse, re-connection |
| Sync state tracking | Custom status fields | `sync_adapter.update_cursor_status` / `SyncRunLogger` | Structured sync_cursors table |
| Linear ticket linking | New regex logic | `github_linking.extract_linear_issue_id` / `get_linear_team_keys` | Branch name parsing is provider-agnostic -- works for GitLab MR source branches too |
| Webhook idempotency | Custom dedup | `WebhookDelivery` model | Already exists with unique delivery_id |
| Embedding generation | Custom pipeline | `embedding_worker.enqueue_embedding_job` | Async embedding via Redis |

**Key insight:** The existing GitHub integration built all the reusable infrastructure. GitLab integration primarily creates new models/routes and calls into existing shared services.

## Common Pitfalls

### Pitfall 1: GitLab OAuth2 Token Expiry (2 hours)
**What goes wrong:** GitLab access tokens expire after 7200 seconds (2 hours), shorter than some providers
**Why it happens:** GitLab's default token TTL is aggressive
**How to avoid:** Store both access_token and refresh_token in Vault. Check expiry before API calls (like GitHub's `get_installation_token`). Use `TOKEN_REFRESH_BUFFER` (5 min) from oauth_common.
**Warning signs:** 401 responses from GitLab API during sync

### Pitfall 2: GitLab Project IDs vs Path
**What goes wrong:** GitLab API accepts both numeric project IDs and URL-encoded paths (e.g., `group%2Fproject`). Inconsistent usage causes 404s.
**Why it happens:** Some endpoints work with paths, others need numeric IDs
**How to avoid:** Always store and use numeric project `id` from the projects API response. Store `path_with_namespace` for display only.
**Warning signs:** 404 errors on some API calls but not others

### Pitfall 3: GitLab Notes vs Discussions for Reviews
**What goes wrong:** GitLab doesn't have a formal "review" concept like GitHub. Reviews are represented as notes and discussion threads.
**Why it happens:** GitLab's review model differs from GitHub's -- no single "review" entity with approve/request changes
**How to avoid:** Use the Notes API (`/merge_requests/:iid/notes`) for general comments. Use Discussions API (`/merge_requests/:iid/discussions`) for threaded diff comments. Map both to `gitlab_reviews` table with appropriate type field.
**Warning signs:** Missing review data, incomplete comment ingestion

### Pitfall 4: GitLab Webhook Secret Verification
**What goes wrong:** Webhook payloads aren't verified, allowing spoofed events
**Why it happens:** GitLab sends the secret token in `X-Gitlab-Token` header (not HMAC signature like GitHub)
**How to avoid:** Compare `X-Gitlab-Token` header directly against stored secret (constant-time comparison). Simpler than GitHub's HMAC-SHA256 body signing.
**Warning signs:** Processing forged webhook events

### Pitfall 5: MR State Mapping
**What goes wrong:** GitLab MR states don't map 1:1 to GitHub PR states
**Why it happens:** GitLab has `opened`, `closed`, `merged`, `locked` states. GitHub has `open`, `closed` + merged_at
**How to avoid:** Map explicitly: `opened` -> `open`, `closed` -> `closed`, `merged` -> `merged`, `locked` -> `closed`
**Warning signs:** Invalid state values in database

### Pitfall 6: Provider Check Constraints
**What goes wrong:** Inserting 'gitlab' into oauth_tokens or workspace_integrations fails with check constraint violation
**Why it happens:** Existing CHECK constraints only allow known provider values
**How to avoid:** Migration MUST update both `oauth_tokens_provider_check` and `workspace_integrations_provider_check` to include 'gitlab' (see GitHub migration pattern in 00004)
**Warning signs:** DB constraint violation errors on first connection attempt

## Code Examples

### GitLab OAuth2 Callback Handler
```python
# Source: matches Linear/Slack pattern in oauth_common.py
async def handle_callback(
    code: str, state: str, session: AsyncSession, settings: Settings
) -> dict:
    workspace_id = verify_state_or_raise(
        state, settings.GITLAB_CLIENT_SECRET, GitLabOAuthError
    )

    # Exchange code for tokens
    token_data = await _exchange_code(code, settings)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in", 7200)

    token_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)

    # Get user info for workspace member lookup
    user_info = await _get_current_user(access_token)

    # Store tokens in Vault
    access_name = token_name(Provider.GITLAB, workspace_id, "access_token")
    refresh_name = token_name(Provider.GITLAB, workspace_id, "refresh_token")
    await store_token(session, access_name, access_token)
    if refresh_token:
        await store_token(session, refresh_name, refresh_token)

    # ... upsert_oauth_token, upsert_workspace_integration, commit
```

### GitLab MR Model (parallel to GithubPullRequest)
```python
class GitlabMergeRequest(BaseModel, table=True):
    __tablename__ = "gitlab_merge_requests"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    linear_ticket_id: uuid.UUID | None = Field(default=None, foreign_key="linear_tickets.id")
    gitlab_id: int = Field(nullable=False)         # GitLab's internal MR ID
    project_id: int = Field(nullable=False)         # GitLab project numeric ID
    project_path: str = Field(nullable=False)       # e.g. "group/project"
    iid: int = Field(nullable=False)                # Project-scoped MR number
    title: str = Field(nullable=False)
    description: str | None = Field(default=None)
    state: str = Field(nullable=False)              # open, closed, merged
    author: str = Field(nullable=False)
    source_branch: str = Field(nullable=False)      # GitLab uses source_branch (not branch_name)
    target_branch: str = Field(nullable=False)      # GitLab uses target_branch (not base_branch)
    reviewers: list[str] | None = Field(default=None, sa_column=Column(ARRAY(String)))
    is_draft: bool = Field(default=False)
    gitlab_created_at: datetime | None = Field(default=None)
    gitlab_updated_at: datetime | None = Field(default=None)
    gitlab_merged_at: datetime | None = Field(default=None)
    raw_data: dict = Field(default_factory=dict, sa_column=Column(JSONB, ...))
```

### Settings Configuration
```python
# Add to config.py Settings class:
GITLAB_CLIENT_ID: str = ""
GITLAB_CLIENT_SECRET: str = ""
GITLAB_REDIRECT_URI: str = ""
GITLAB_WEBHOOK_SECRET: str = ""

@property
def gitlab_redirect_uri(self) -> str:
    if self.GITLAB_REDIRECT_URI:
        return self.GITLAB_REDIRECT_URI
    return f"{self._public_base_url}/api/gitlab/callback"
```

### Frontend API Client Functions
```typescript
// Add to lib/api.ts (matches GitHub pattern)
export function connectGitlab(): Promise<{ authorization_url: string }> {
  return apiFetch<{ authorization_url: string }>('/api/gitlab/connect')
}

export function disconnectGitlab(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>('/api/gitlab/disconnect', { method: 'POST' })
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GitLab personal access tokens | OAuth2 with PKCE | Always available but PKCE added for security | Use standard OAuth2 authorization code flow; PKCE optional for server apps |
| v3 API | v4 API | GitLab 9.0 (2017) | All endpoints under /api/v4 |
| No refresh tokens | Refresh tokens standard | Long-standing | Must store and use refresh_token for token renewal |

**Deprecated/outdated:**
- GitLab API v3: Removed years ago, only v4 exists
- `repository` field in webhook payloads: Deprecated, use `project` instead

## Key Differences: GitLab vs GitHub

| Aspect | GitHub | GitLab | Implementation Impact |
|--------|--------|--------|----------------------|
| Auth model | GitHub App (JWT + installation tokens) | Standard OAuth2 (auth code + refresh) | Simpler -- matches Linear/Slack pattern |
| Token expiry | 1 hour (installation tokens) | 2 hours (access tokens) | Same refresh pattern, different TTL |
| PR/MR terminology | Pull Request, PR number | Merge Request, IID (project-scoped) | Different field names in models/API |
| Reviews | Formal review objects | Notes + Discussions (no review entity) | Map notes/discussions to review table |
| Webhook auth | HMAC-SHA256 body signature | X-Gitlab-Token header comparison | Simpler verification |
| Repo/Project selection | Installation repositories | User's accessible projects | Different API endpoint |
| Bot filtering | `[bot]` suffix convention | Bot users have `bot` user type | Check user.bot field instead of name suffix |
| Rate limiting | X-RateLimit-* headers | RateLimit-* headers (no X- prefix) | Different header names |
| Pagination | Link header (RFC 5988) | Link header (RFC 5988) + X-Total, X-Page | Same Link header parsing works |

## Open Questions

1. **Self-hosted GitLab support**
   - What we know: GitLab can be self-hosted with custom base URLs
   - What's unclear: Should Phase 24 support custom GitLab instances or only gitlab.com?
   - Recommendation: Start with gitlab.com only. Store `gitlab_base_url` in settings for future self-hosted support, but hardcode to `https://gitlab.com` initially.

2. **GitLab project selection granularity**
   - What we know: Users can access many projects across groups
   - What's unclear: Should we list all accessible projects or filter by group?
   - Recommendation: List all projects where user is a member (`membership=true`). Let user select which to monitor (matches GitHub repo selection UX).

3. **Approval data ingestion**
   - What we know: GitLab has approval rules and approval events in webhooks
   - What's unclear: Should we ingest approval data as review records?
   - Recommendation: Map approval webhook events to gitlab_reviews records with state `approved`. This matches how GitHub `APPROVED` reviews are stored.

## Sources

### Primary (HIGH confidence)
- [GitLab OAuth2 API Docs](https://docs.gitlab.com/api/oauth2/) - Authorization code flow, token exchange, refresh tokens, scopes
- [GitLab Merge Requests API](https://docs.gitlab.com/api/merge_requests/) - MR listing, filtering, pagination, response fields
- [GitLab Notes API](https://docs.gitlab.com/api/notes/) - MR notes endpoints, response structure
- [GitLab Discussions API](https://docs.gitlab.com/api/discussions/) - Diff-level comments, discussion threads
- [GitLab Project Webhooks API](https://docs.gitlab.com/api/project_webhooks/) - Webhook creation, event types, secret tokens
- [GitLab Webhook Events](https://docs.gitlab.com/user/project/integrations/webhook_events/) - MR event payload structure, action values

### Secondary (MEDIUM confidence)
- [GitLab OAuth Provider Config](https://docs.gitlab.com/integration/oauth_provider/) - Application registration, scope details

### Tertiary (LOW confidence)
- None -- all findings verified against official GitLab documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies; all patterns exist in codebase
- Architecture: HIGH - Direct mirror of GitHub integration with well-understood differences
- Pitfalls: HIGH - GitLab API differences verified against official docs
- OAuth flow: HIGH - Standard OAuth2 authorization code flow, well-documented

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (stable -- GitLab API v4 is mature)
