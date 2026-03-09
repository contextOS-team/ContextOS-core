# Phase 25: Jira Integration - Research

**Researched:** 2026-03-09
**Domain:** Jira Cloud REST API v3, OAuth 2.0 (3LO), Webhook Integration
**Confidence:** HIGH

## Summary

Jira Cloud integration follows the identical architectural pattern already established by the Linear integration in ContextOS. The project has a well-defined integration template: OAuth service, sync service, webhook handler, router, SQLModel models, Supabase migration, Vault token storage, Provider enum, SyncAdapter protocol, and frontend integration card + onboarding source card.

Jira Cloud uses OAuth 2.0 (3LO) via `auth.atlassian.com`, with a critical difference from Linear: Jira requires a `cloudId` (obtained via the `/oauth/token/accessible-resources` endpoint after token exchange) to construct API URLs. All Jira REST API calls go through `https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/...`. The search endpoint has recently migrated from `/rest/api/3/search` to `/rest/api/3/search/jql` with token-based pagination (no more `startAt`/`total`).

**Primary recommendation:** Mirror the Linear integration pattern file-for-file (oauth, sync, webhook, router, model, migration), using `httpx` for all Jira REST API calls. Store `cloudId` in `workspace_integrations.config`. Use the new `/search/jql` endpoint with `nextPageToken` pagination.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| JIRA-01 | Jira OAuth 2.0 (3LO) connect/disconnect flow | OAuth 2.0 3LO flow via auth.atlassian.com, rotating refresh tokens, cloudId resolution |
| JIRA-02 | Jira issue sync with JQL-based filtering | REST API v3 `/search/jql` endpoint, token-based pagination, project/board filtering |
| JIRA-03 | Jira-to-context page linking | New `jira_issues` table parallel to `linear_tickets`, context_pages FK update |
| JIRA-04 | Jira webhook for real-time issue updates | Webhook registration via REST API, HMAC-SHA256 verification, 30-day expiry refresh |
| JIRA-05 | Jira source in onboarding wizard sources grid | SourceCard component pattern, connectJira API function, JiraLogo SVG icon |
| JIRA-06 | Jira integration card in settings/integrations | IntegrationCard pattern, project selector as expandable settings |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | (existing) | Jira REST API calls | Already used for Linear/GitHub/Notion -- raw HTTP, no SDK needed |
| SQLModel | (existing) | JiraIssue + JiraComment models | Project standard for all DB models |
| Supabase Vault | (existing) | Encrypted token storage | All OAuth tokens stored in Vault, never plaintext |
| FastAPI | (existing) | Jira router + webhook endpoint | Project standard backend framework |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | (existing) | JIRA_* env vars in Settings | Config pattern matches Linear/GitHub/Slack |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| httpx (raw REST) | `jira` Python SDK | SDK adds dependency + abstraction mismatch; project uses raw httpx for all integrations |
| Custom webhook handler | Atlassian Connect | Connect is for Atlassian Marketplace apps, not custom integrations |

## Architecture Patterns

### Recommended Project Structure (new files)
```
backend/src/
  models/
    jira.py                  # JiraIssue, JiraComment SQLModel classes
  services/
    jira_oauth.py            # OAuth 2.0 3LO: build_auth_url, exchange_code, refresh, disconnect
    jira_sync.py             # Issue sync via REST API, JQL filtering, SyncAdapter impl
    jira_webhook.py          # Webhook event processor (issue/comment CRUD)
  routers/
    jira.py                  # /api/jira/* endpoints (connect, callback, disconnect, status, sync, search)

supabase/migrations/
  00019_jira_tables.sql      # jira_issues, jira_comments tables + provider constraint updates

apps/web/src/
  components/icons/
    jira-logo.tsx             # JiraLogo SVG component
  lib/
    api.ts                    # connectJira, disconnectJira, searchJiraIssues functions
```

### Pattern 1: OAuth 2.0 (3LO) Flow
**What:** Jira uses Atlassian's centralized OAuth at `auth.atlassian.com`, not Jira-specific endpoints
**When to use:** All OAuth operations
**Key difference from Linear:** After token exchange, must call `/oauth/token/accessible-resources` to get `cloudId`
**Example:**
```python
# Authorization URL
JIRA_AUTHORIZE_URL = "https://auth.atlassian.com/authorize"
JIRA_TOKEN_URL = "https://auth.atlassian.com/oauth/token"
JIRA_ACCESSIBLE_RESOURCES_URL = "https://api.atlassian.com/oauth/token/accessible-resources"

def build_auth_url(state: str, settings: Settings) -> str:
    params = {
        "audience": "api.atlassian.com",
        "client_id": settings.JIRA_CLIENT_ID,
        "scope": "read:jira-work write:jira-work read:jira-user manage:jira-webhook offline_access",
        "redirect_uri": settings.jira_redirect_uri,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    return f"{JIRA_AUTHORIZE_URL}?{urlencode(params)}"

async def exchange_code(code, session, workspace_id, user_id, settings):
    # 1. Exchange code for tokens (JSON body, not form data!)
    async with httpx.AsyncClient() as client:
        response = await client.post(JIRA_TOKEN_URL, json={
            "grant_type": "authorization_code",
            "client_id": settings.JIRA_CLIENT_ID,
            "client_secret": settings.JIRA_CLIENT_SECRET,
            "code": code,
            "redirect_uri": settings.jira_redirect_uri,
        })
    # 2. Get accessible resources to find cloudId
    async with httpx.AsyncClient() as client:
        resources = await client.get(
            JIRA_ACCESSIBLE_RESOURCES_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    # cloudId = resources.json()[0]["id"]
    # Store cloudId in workspace_integrations.config
```

### Pattern 2: Jira REST API URL Construction
**What:** All API calls require cloudId in the URL path
**When to use:** Every Jira API call after OAuth
```python
def _api_url(cloud_id: str, path: str) -> str:
    return f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/{path}"

# Example: Search issues
url = _api_url(cloud_id, "search/jql")
```

### Pattern 3: JQL Search with Token-Based Pagination
**What:** New `/search/jql` endpoint replaces deprecated `/search`
**When to use:** Issue sync and search
**Key difference:** Uses `nextPageToken` instead of `startAt`/`total`
```python
async def fetch_issues_jql(client, cloud_id, access_token, jql, max_results=50):
    """Fetch issues with token-based pagination."""
    all_issues = []
    next_page_token = None

    while True:
        body = {
            "jql": jql,
            "maxResults": max_results,
            "fields": ["summary", "description", "status", "priority",
                       "assignee", "reporter", "project", "labels",
                       "comment", "created", "updated", "issuetype"],
        }
        if next_page_token:
            body["nextPageToken"] = next_page_token

        response = await client.post(
            _api_url(cloud_id, "search/jql"),
            headers={"Authorization": f"Bearer {access_token}"},
            json=body,
        )
        data = response.json()
        all_issues.extend(data.get("issues", []))

        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return all_issues
```

### Pattern 4: Webhook Registration via REST API
**What:** OAuth 2.0 apps register webhooks via REST API (not Connect)
**When to use:** After OAuth connection, register for issue/comment events
**Important:** Webhooks expire after 30 days -- must implement refresh
```python
async def register_webhooks(client, cloud_id, access_token, callback_url):
    response = await client.post(
        _api_url(cloud_id, "webhook"),
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "webhooks": [{
                "events": [
                    "jira:issue_created",
                    "jira:issue_updated",
                    "jira:issue_deleted",
                    "comment_created",
                    "comment_updated",
                    "comment_deleted",
                ],
                "jqlFilter": "project = KEY",  # Filtered by selected projects
            }],
            "url": callback_url,
        },
    )
```

### Anti-Patterns to Avoid
- **Using `/rest/api/3/search` (deprecated):** Fully removed from Jira Cloud. Must use `/rest/api/3/search/jql`
- **Using `startAt` pagination:** Removed. Must use `nextPageToken`
- **Sending token exchange as form data:** Jira expects JSON body (`Content-Type: application/json`), unlike Linear which uses form data
- **Hardcoding Jira domain:** All API calls go through `api.atlassian.com/ex/jira/{cloudId}`, never directly to `*.atlassian.net`
- **Forgetting `offline_access` scope:** Without it, no refresh token is returned
- **Ignoring webhook expiry:** Jira webhooks expire after 30 days. Must implement periodic refresh via `PUT /rest/api/3/webhook/refresh`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OAuth state signing | Custom state format | `oauth_common.sign_oauth_state` / `verify_state_or_raise` | Already handles HMAC-SHA256 signing/verification |
| Token storage | Plaintext DB columns | Supabase Vault via `vault.store_token` / `vault.read_token` | All existing integrations use Vault |
| Integration upsert | Custom upsert logic | `oauth_common.upsert_oauth_token` / `upsert_workspace_integration` | Handles soft-delete reuse, reconnect logic |
| Disconnect flow | Custom cleanup | `oauth_common.disconnect_provider` | Handles Vault cleanup, soft-delete, status update |
| Sync state tracking | Custom tracking | `sync_adapter.update_cursor_status` / `SyncRunLogger` | Structured sync state + log correlation |
| Webhook idempotency | Custom dedup | `WebhookDelivery` model + existing pattern | Already solved for Linear/GitHub/Notion |

**Key insight:** The codebase has extracted nearly all OAuth/sync/webhook infrastructure into reusable modules (`oauth_common.py`, `sync_adapter.py`, `vault.py`, webhook pattern in `webhooks.py`). The Jira integration should be ~90% wiring these together with Jira-specific API calls.

## Common Pitfalls

### Pitfall 1: CloudId Resolution
**What goes wrong:** Forgetting to fetch cloudId after token exchange, or assuming there's only one accessible resource
**Why it happens:** Linear/GitHub don't have this concept -- Jira requires it for multi-tenant API routing
**How to avoid:** Always call `/oauth/token/accessible-resources` after exchange, store cloudId in `workspace_integrations.config.cloud_id`. Handle case where user has access to multiple Jira sites (present selector or use first).
**Warning signs:** 404 errors on all API calls after OAuth

### Pitfall 2: Rotating Refresh Tokens
**What goes wrong:** Reusing old refresh token after rotation
**Why it happens:** Jira uses rotating refresh tokens -- each use issues a NEW token and invalidates the old one
**How to avoid:** Always store the new refresh token from each refresh response. Use advisory lock (existing pattern) to prevent concurrent refreshes.
**Warning signs:** `invalid_grant` errors on token refresh

### Pitfall 3: Token Exchange Body Format
**What goes wrong:** Sending form-encoded data for token exchange
**Why it happens:** Linear uses `data={}` (form-encoded), Jira requires `json={}` (JSON body)
**How to avoid:** Use `json=` parameter in httpx, not `data=`
**Warning signs:** 400 errors on token exchange

### Pitfall 4: Search Endpoint Migration
**What goes wrong:** Using deprecated `/search` endpoint or `startAt` pagination
**Why it happens:** Many online examples and tutorials still reference the old endpoint
**How to avoid:** Use `/search/jql` with POST and `nextPageToken` pagination exclusively
**Warning signs:** Empty results or deprecation warnings from Jira API

### Pitfall 5: Webhook 30-Day Expiry
**What goes wrong:** Webhooks stop delivering after 30 days
**Why it happens:** Jira Cloud webhooks auto-expire after 30 days for OAuth 2.0 apps
**How to avoid:** Implement periodic webhook refresh via `PUT /rest/api/3/webhook/refresh`. Could piggyback on existing sync scheduler or add pg_cron job.
**Warning signs:** Webhook events suddenly stop arriving

### Pitfall 6: Provider Check Constraints
**What goes wrong:** INSERT fails on oauth_tokens or workspace_integrations because 'jira' is not in the CHECK constraint
**Why it happens:** The provider CHECK constraint on these tables must be updated in the migration
**How to avoid:** Migration must ALTER CONSTRAINT to add 'jira' to both oauth_tokens and workspace_integrations tables (same pattern as 00004_github_tables.sql)
**Warning signs:** Postgres CHECK constraint violation errors

### Pitfall 7: Context Pages FK to linear_tickets
**What goes wrong:** context_pages.ticket_id has a hard FK to linear_tickets, can't reference Jira issues
**Why it happens:** Original schema assumed Linear-only
**How to avoid:** Either add a separate `jira_issue_id` FK column to context_pages, or refactor to a generic `ticket_source`/`ticket_source_id` pattern. Recommend adding `jira_issue_id` FK (simpler, no migration risk on existing data).
**Warning signs:** Cannot link Jira issues to context pages

## Code Examples

### Settings Configuration
```python
# In config.py Settings class
JIRA_CLIENT_ID: str = ""
JIRA_CLIENT_SECRET: str = ""
JIRA_REDIRECT_URI: str = ""
JIRA_WEBHOOK_SECRET: str = ""

@property
def jira_redirect_uri(self) -> str:
    if self.JIRA_REDIRECT_URI:
        return self.JIRA_REDIRECT_URI
    return f"{self._public_base_url}/api/jira/callback"
```

### Provider Enum Extension
```python
# In models/integration.py
class Provider(str, Enum):
    LINEAR = "linear"
    GITHUB = "github"
    SLACK = "slack"
    FATHOM = "fathom"
    NOTION = "notion"
    JIRA = "jira"  # Add this
```

### JiraIssue Model (mirrors LinearTicket structure)
```python
class JiraIssue(BaseModel, table=True):
    __tablename__ = "jira_issues"

    workspace_id: uuid.UUID = Field(foreign_key="workspaces.id", nullable=False)
    jira_id: str = Field(nullable=False)        # Jira issue ID (numeric string)
    jira_key: str = Field(nullable=False)        # e.g. "PROJ-123"
    summary: str = Field(nullable=False)         # Jira calls title "summary"
    description: str | None = Field(default=None)
    status: str | None = Field(default=None)
    priority: str | None = Field(default=None)   # Jira priority is string, not int
    issue_type: str | None = Field(default=None) # Bug, Story, Task, Epic
    assignee_name: str | None = Field(default=None)
    reporter_name: str | None = Field(default=None)
    project_key: str | None = Field(default=None)
    project_name: str | None = Field(default=None)
    labels: list[str] | None = Field(default=None, sa_column=Column(ARRAY(String)))
    jira_created_at: datetime | None = Field(default=None)
    jira_updated_at: datetime | None = Field(default=None)
    raw_data: dict = Field(default_factory=dict, sa_column=Column(JSONB, ...))
```

### Integration Status Extension
```python
# In routers/integrations.py
PROVIDERS = [Provider.LINEAR, Provider.SLACK, Provider.FATHOM,
             Provider.GITHUB, Provider.NOTION, Provider.JIRA]

# In _build_provider_status:
if integration.provider == Provider.JIRA:
    config = integration.config or {}
    result["projects_synced"] = len(config.get("synced_projects", []))
    result["last_sync_at"] = config.get("last_sync_at")
```

### Frontend IntegrationStatusResponse Extension
```typescript
// In lib/api.ts
export interface IntegrationStatusResponse {
  linear: ProviderStatus
  slack: ProviderStatus
  fathom: ProviderStatus
  github: ProviderStatus
  notion: ProviderStatus
  jira: ProviderStatus  // Add this
}
```

### Webhook Signature Verification
```python
# Jira uses X-Hub-Signature header with sha256=<hex> format (same as GitHub)
signature_header = request.headers.get("X-Hub-Signature")
if signature_header and signature_header.startswith("sha256="):
    expected = "sha256=" + hmac.new(
        settings.JIRA_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature_header, expected):
        raise HTTPException(status_code=400, detail="Invalid signature")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `/rest/api/3/search` | `/rest/api/3/search/jql` | 2025 | Must use new endpoint; old one fully removed |
| `startAt` offset pagination | `nextPageToken` token pagination | 2025 | No `total` field available; use approximate-count API if needed |
| OAuth 1.0a | OAuth 2.0 (3LO) | Deprecated years ago | Must use 3LO via auth.atlassian.com |
| Static refresh tokens | Rotating refresh tokens | Current | Each refresh invalidates old token; 90-day inactivity expiry |
| Manual webhook setup | REST API webhook registration | Current | 5 webhooks per app per user limit; 30-day expiry |

**Deprecated/outdated:**
- `/rest/api/3/search` endpoint -- fully removed, use `/rest/api/3/search/jql`
- `startAt`/`total` pagination -- replaced by `nextPageToken`
- OAuth 1.0a -- deprecated, use OAuth 2.0 (3LO)

## Open Questions

1. **Multiple Jira Sites**
   - What we know: A user may have access to multiple Jira Cloud sites (accessible-resources returns array)
   - What's unclear: Should the UI present a site selector, or auto-select the first one?
   - Recommendation: Use first accessible resource for v1. Add site selector if requested later.

2. **Webhook Refresh Scheduling**
   - What we know: Webhooks expire after 30 days and must be refreshed via REST API
   - What's unclear: Whether to use pg_cron (existing pattern) or piggyback on sync scheduler
   - Recommendation: Add a pg_cron job that calls webhook refresh endpoint every 25 days

3. **Context Pages Dual-FK vs Generic**
   - What we know: context_pages currently has `ticket_id FK -> linear_tickets`. Need to also link to Jira.
   - What's unclear: Whether to add `jira_issue_id` FK or refactor to generic source linkage
   - Recommendation: Add `jira_issue_id` column (nullable FK to jira_issues). Simpler, no risk to existing data. Generic refactor can be deferred.

4. **Embedding source_type for Jira**
   - What we know: embeddings.source_type has a CHECK constraint listing allowed types
   - What's unclear: Exact naming convention
   - Recommendation: Add `jira_issue` and `jira_comment` to the CHECK constraint. Matches `linear_ticket`/`linear_comment` pattern.

## Sources

### Primary (HIGH confidence)
- [Atlassian OAuth 2.0 (3LO) docs](https://developer.atlassian.com/cloud/jira/platform/oauth-2-3lo-apps/) - Full OAuth flow, endpoints, rotating tokens
- [Jira Scopes documentation](https://developer.atlassian.com/cloud/jira/platform/scopes-for-oauth-2-3LO-and-forge-apps/) - Classic and granular scopes
- [Jira Webhooks documentation](https://developer.atlassian.com/cloud/jira/platform/webhooks/) - Registration, events, HMAC, expiry
- [Jira REST API v3 Issue Search](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/) - Search/JQL endpoint
- Existing codebase: Linear OAuth/sync/webhook implementation (direct code analysis)

### Secondary (MEDIUM confidence)
- [Atlassian Community - search/jql migration](https://community.atlassian.com/forums/Jira-questions/REST-The-new-rest-api-3-search-jql-endpoint-is-a-complete/qaq-p/3101716) - Pagination issues, workarounds
- [Jira Webhooks Guide (Inventive HQ)](https://inventivehq.com/blog/jira-webhooks-guide) - Payload examples, setup guide

### Tertiary (LOW confidence)
- None -- all findings verified against official Atlassian documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - mirrors existing integration pattern exactly, no new dependencies
- Architecture: HIGH - file-for-file mirror of Linear integration with well-documented Jira API differences
- Pitfalls: HIGH - cloudId, rotating tokens, JSON body, and search migration are well-documented in official docs
- Webhook expiry: MEDIUM - 30-day expiry documented but refresh scheduling approach needs validation

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (Jira Cloud API is stable; 30-day validity)
