# Phase 28: GitLab Project Selection & Code Indexing

## Goal

Add full project selection UI and code indexing for GitLab, mirroring the GitHub integration experience. After OAuth connect, users should be able to browse their GitLab projects, select which ones to monitor, and have code automatically indexed (cloned, parsed, embedded) using the existing provider-agnostic pipeline.

## What Exists (Phase 24 Output)

Phase 24 built the GitLab foundation:
- **Database:** `gitlab_merge_requests`, `gitlab_reviews` tables, provider enum includes `gitlab`
- **OAuth:** Full OAuth2 flow working (connect/disconnect/callback)
- **Backend services:** `gitlab_common.py`, `gitlab_oauth.py`, `gitlab_repos.py`, `gitlab_sync.py`, `gitlab_webhook.py`, `gitlab_linking.py`
- **Router:** `backend/src/routers/gitlab.py` with 10 endpoints
- **Frontend:** GitLab logo, API client functions, onboarding source card, settings integration card
- **Status:** GitLab appears in `/api/integrations/status`

### What `gitlab_repos.py` Already Has

The service already implements project listing and selection:
- `list_projects()` — calls GitLab API `/projects?membership=true`, paginates, caches in `workspace_integrations.config.available_repos`
- `get_cached_projects()` — reads from cache
- `save_selected_projects()` — validates and stores selection in `config.selected_repos`
- `is_project_monitored()` — checks if a project is in selected list

### What's Missing

1. **Frontend project selection component** — no UI to browse/select GitLab projects
2. **Code indexing integration** — no clone-via-GitLab-token, no `/api/gitlab/index` endpoint
3. **Index status tracking** — no `selected_repos_count` in integrations status for GitLab

## GitHub Reference Architecture (Mirror This)

### Frontend: `apps/web/src/app/dashboard/integrations/github-repos.tsx`
- Loads available repos via `GET /api/github/repos`
- Auto-refreshes from GitHub if cache empty
- Manual refresh button (`POST /api/github/repos/refresh`)
- Checkbox selection with "select all"
- Save selection (`POST /api/github/repos/select`) → auto-triggers indexing
- Polls index status (`GET /api/github/index/status` every 3s)
- Displays: "X code symbols indexed across Y repos"

### Backend Endpoints (in `backend/src/routers/github.py`)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/github/repos` | GET | Returns cached repos + selected_repos |
| `/api/github/repos/refresh` | POST | Fetches fresh list from GitHub API |
| `/api/github/repos/select` | POST | Saves user's repo selection |
| `/api/github/index` | POST | Triggers workspace-wide code indexing |
| `/api/github/index/status` | GET | Returns indexing status + per-repo chunk counts |

### Code Indexing Pipeline (Provider-Agnostic)
The indexing pipeline is already provider-agnostic and reusable:

1. **Code Index Worker** (`backend/src/services/code_index_worker.py`) — reads from Redis Stream `code_index:jobs`
2. **Code Indexer** (`backend/src/services/code_indexer.py`) — clones repo (shallow `--depth 1`), walks files, parses with tree-sitter
3. **Code Parser** (`backend/src/services/code_parser.py`) — tree-sitter extraction of functions, classes, methods, types
4. **Embedding Worker** (`backend/src/services/embedding_worker.py`) — reads from Redis Stream `embedding:jobs`
5. **Embedding Service** (`backend/src/services/embedding.py`) — OpenAI `text-embedding-3-small` (768 dims), batch size 25

**Clone URL pattern:** `https://x-access-token:{token}@github.com/{owner}/{repo}.git`
**GitLab equivalent:** `https://oauth2:{access_token}@gitlab.com/{namespace}/{project}.git`

**Key difference:** GitHub uses App installation tokens (long-lived). GitLab uses OAuth access tokens (2-hour expiry, need refresh before clone).

### Status Tracking (in `workspace_integrations.config` JSONB)
```json
{
  "available_repos": [...],
  "selected_repos": ["owner/repo", ...],
  "code_index_status": "idle|indexing",
  "code_index_last_at": "2026-03-10T..."
}
```

### Integrations Status Endpoint
`backend/src/routers/integrations.py` — `_build_provider_status()` includes `selected_repos_count` for GitHub. Need same for GitLab.

## Implementation Notes

### Clone Authentication
- `code_indexer.py` currently hardcodes GitHub App token retrieval
- Need to abstract clone auth: given a `(provider, workspace_id)`, return `(clone_url_prefix, token)`
- GitLab clone: `https://oauth2:{access_token}@gitlab.com/{path}.git`
- Must refresh OAuth token if expired before cloning (GitLab tokens expire in 2 hours)

### Project vs Repo Naming
- GitHub calls them "repos" (`repo_full_name` = `owner/repo`)
- GitLab calls them "projects" (`path_with_namespace` = `namespace/project`)
- The `CodeChunk` table uses `repo_full_name` — can store GitLab project paths here too
- Frontend should say "Projects" for GitLab, "Repos" for GitHub

### Files to Create/Modify
| File | Action |
|------|--------|
| `apps/web/src/app/dashboard/integrations/gitlab-repos.tsx` | **Create** — mirror `github-repos.tsx` |
| `apps/web/src/app/dashboard/settings/page.tsx` | **Modify** — render `GitlabRepos` under GitLab card |
| `apps/web/src/lib/api.ts` | **Modify** — add `getGitlabRepos`, `refreshGitlabRepos`, `selectGitlabRepos`, `triggerGitlabIndex`, `getGitlabIndexStatus` |
| `backend/src/routers/gitlab.py` | **Modify** — add `/repos`, `/repos/refresh`, `/repos/select`, `/index`, `/index/status` endpoints |
| `backend/src/services/code_indexer.py` | **Modify** — abstract clone auth to support both GitHub and GitLab tokens |
| `backend/src/routers/integrations.py` | **Modify** — add `selected_repos_count` for GitLab in `_build_provider_status` |

### Bugs Found During Phase 24 Testing
1. ~~OAuth scope mismatch~~ — fixed (was `read_api`, changed to `api+read_user`)
2. ~~Migration not applied~~ — fixed (ran `supabase db push`)
3. ~~`PROVIDERS` list missing GitLab~~ — fixed
4. ~~`external_name` showing numeric ID~~ — fixed (now uses username)
