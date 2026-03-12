---
phase: 28-gitlab-code-indexing
verified: 2026-03-12T00:00:00Z
status: passed
score: 5/5 must-haves verified
gaps: []
human_verification:
  - test: "Connect a real GitLab account and browse projects"
    expected: "GitlabRepos component renders project list with checkboxes, visibility icons (Lock/Globe), and path_with_namespace labels"
    why_human: "Visual rendering and OAuth flow cannot be verified programmatically"
  - test: "Select projects and click Save selection"
    expected: "POST /api/gitlab/repos/select fires, then POST /api/gitlab/index fires automatically, indexing status bar switches to 'Indexing projects...' spinner"
    why_human: "Real-time state transition and auto-trigger chain requires browser execution"
  - test: "Wait for indexing to complete and check status bar"
    expected: "Status bar shows 'N code symbols indexed across M projects' with last indexed date"
    why_human: "Requires running Redis worker and actual GitLab repo clone pipeline"
---

# Phase 28: GitLab Project Selection & Code Indexing Verification Report

**Phase Goal:** Add project selection UI and code indexing for GitLab, mirroring the GitHub experience — browse projects, select which to monitor, clone and index code using the existing provider-agnostic pipeline (tree-sitter parsing, embeddings).
**Verified:** 2026-03-12T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                    | Status     | Evidence                                                                                                                        |
|----|------------------------------------------------------------------------------------------|------------|---------------------------------------------------------------------------------------------------------------------------------|
| 1  | Code indexing pipeline supports both GitHub and GitLab with provider-aware clone auth    | VERIFIED   | `_get_clone_credentials()` in `code_indexer.py` dispatches on `provider` param; GitHub uses installation token, GitLab uses `ensure_valid_token()` with `oauth2:` prefix |
| 2  | POST /api/gitlab/index triggers indexing for selected GitLab projects via Redis Stream   | VERIFIED   | `trigger_index()` at line 335 of `gitlab.py` calls `enqueue_workspace_index_job(user.workspace_id, provider="gitlab")`; worker reads `provider` from job payload and dispatches to `index_gitlab_workspace_repos()` |
| 3  | GET /api/gitlab/index/status returns indexing state and per-project chunk counts         | VERIFIED   | `get_index_status()` at line 349 of `gitlab.py` reads `code_index_status`/`code_index_last_at` from config, queries `code_chunks` filtered by `available_projects` paths |
| 4  | Users can browse, select, and save GitLab projects from the settings page                | VERIFIED   | `GitlabRepos` component (343 lines) renders project list with numeric Set<number> selection; `integration-cards.tsx` renders `<GitlabRepos onSaved={fetchStatuses} />` inside the GitLab `IntegrationCard` |
| 5  | Saving project selection auto-triggers code indexing with status polling                 | VERIFIED   | `handleSave()` in `gitlab-repos.tsx` calls `selectGitlabRepos()`, then immediately calls `triggerGitlabIndex()` and starts `pollIndexStatus()` on 3s interval |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact                                                                 | Expected                                        | Status     | Details                                                                                |
|--------------------------------------------------------------------------|-------------------------------------------------|------------|----------------------------------------------------------------------------------------|
| `backend/src/services/code_indexer.py`                                   | Provider-aware clone auth and indexing          | VERIFIED   | Contains `_get_clone_credentials`, `index_repo(provider=)`, `_update_index_status(provider=)`, `index_gitlab_workspace_repos()` |
| `backend/src/routers/gitlab.py`                                          | /index and /index/status endpoints              | VERIFIED   | `trigger_index` at line 335, `get_index_status` at line 349; both wired and substantive |
| `backend/src/routers/integrations.py`                                    | GitLab selected_repos_count in status           | VERIFIED   | Lines 55-57 add `selected_repos_count` for `Provider.GITLAB` from `selected_projects` key |
| `apps/web/src/app/dashboard/integrations/gitlab-repos.tsx`               | GitLab project selection UI (min 200 lines)     | VERIFIED   | 343 lines; full implementation with search, select-all, visibility icons, save, index status bar |
| `apps/web/src/lib/api.ts`                                                | GitLab API client functions including getGitlabRepos | VERIFIED | Lines 270-319 contain `GitlabProject`, `GitlabReposResponse`, `GitlabIndexStatus` interfaces and 5 API functions |
| `apps/web/src/app/dashboard/settings/tabs/integration-cards.tsx`         | GitlabRepos rendered under GitLab card          | VERIFIED   | Line 37 imports `GitlabRepos`, line 248 renders `<GitlabRepos onSaved={fetchStatuses} />` |
| `backend/src/services/code_index_worker.py`                              | Provider field in job payload, GitLab dispatch  | VERIFIED   | `enqueue_workspace_index_job` accepts `provider` param and includes it in payload; `_process_index_message` reads `provider` and dispatches to `index_gitlab_workspace_repos` |

### Key Link Verification

| From                                        | To                                          | Via                                                   | Status  | Details                                                                                    |
|---------------------------------------------|---------------------------------------------|-------------------------------------------------------|---------|--------------------------------------------------------------------------------------------|
| `gitlab.py` (trigger_index)                 | `code_index_worker.py`                      | `enqueue_workspace_index_job(provider="gitlab")`      | WIRED   | Line 345: `await enqueue_workspace_index_job(user.workspace_id, provider="gitlab")`       |
| `code_index_worker.py` (_process_index_message) | `code_indexer.py`                       | `provider == "gitlab"` dispatch to `index_gitlab_workspace_repos` | WIRED   | Lines 136-139: `if provider == "gitlab": results = await index_gitlab_workspace_repos(...)` |
| `code_indexer.py` (_get_clone_credentials)  | `gitlab_common.py`                          | `ensure_valid_token` for OAuth token retrieval        | WIRED   | Line 27 imports `ensure_valid_token`; line 118 calls it inside `_get_clone_credentials`   |
| `gitlab-repos.tsx`                          | `api.ts`                                    | imports `getGitlabRepos`, `refreshGitlabRepos`, etc.  | WIRED   | Lines 8-15 import all 5 functions and both interfaces; all are called in component body   |
| `integration-cards.tsx`                     | `gitlab-repos.tsx`                          | renders `<GitlabRepos>` as child of GitLab IntegrationCard | WIRED   | Line 37 import + line 248 JSX usage inside GitLab `IntegrationCard`                      |
| `index_gitlab_workspace_repos()`            | `ensure_valid_token`                        | called before each repo clone for token refresh       | WIRED   | Line 525: `await ensure_valid_token(session, workspace_id, settings)` inside the repo loop |

### Requirements Coverage

| Requirement | Source Plan | Description                                        | Status    | Evidence                                                                          |
|-------------|-------------|-----------------------------------------------------|-----------|-----------------------------------------------------------------------------------|
| GL-09       | 28-02-PLAN  | Frontend project selection UI for GitLab            | SATISFIED | `gitlab-repos.tsx` (343 lines) with full select/save/index-trigger UX; wired into settings |
| GL-10       | 28-01-PLAN  | Code indexing integration for GitLab projects       | SATISFIED | `_get_clone_credentials`, `index_gitlab_workspace_repos`, `/index` endpoint all implemented and connected |
| GL-11       | 28-01-PLAN  | Index status tracking in integrations status        | SATISFIED | `_build_provider_status()` in `integrations.py` lines 55-57 add `selected_repos_count` for `Provider.GITLAB` |

**Note on REQUIREMENTS.md:** GL-09, GL-10, GL-11 are GitLab-specific requirement IDs defined in `28-RESEARCH.md` and referenced in `ROADMAP.md` Phase 28. They do not appear in `.planning/REQUIREMENTS.md` because that file covers the v1.1 dashboard milestone (DS/ONB/FEED/etc. IDs only). The GL series are phase-local requirements — this is consistent with how they are used across all GitLab phases (24-27 pattern). No orphaned requirements exist.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/src/routers/gitlab.py` | 269 | `TODO(Phase 28): Replace BackgroundTasks with Redis queue for durability` | Info | Applies to MR sync endpoint (`/sync`), not to the code indexing endpoints delivered by this phase. The code indexing endpoints correctly use Redis Stream. Not a blocker. |
| `backend/src/routers/gitlab.py` | 156 | `return []` in `_get_selected_projects` | Info | Legitimate null-guard for missing integration config — not a stub. Returns empty list when no integration exists. |
| `gitlab-repos.tsx` | 245 | `placeholder="Filter projects..."` | Info | HTML input `placeholder` attribute — not code stubbing. |

No blocker or warning anti-patterns found.

### Human Verification Required

#### 1. GitLab Project Browse UI

**Test:** Connect a GitLab account via OAuth, navigate to Settings > Integrations, expand the GitLab card.
**Expected:** GitlabRepos component renders with project list, visibility icons (Lock for private, dimmed Lock for internal, Globe for public), `path_with_namespace` labels, and "N of M projects selected" counter.
**Why human:** Visual rendering and OAuth callback flow cannot be verified programmatically.

#### 2. Save Selection Auto-Triggers Indexing

**Test:** Select 1-2 projects via checkboxes and click "Save selection".
**Expected:** Request fires to POST /api/gitlab/repos/select, then immediately POST /api/gitlab/index fires. The index status bar changes from static to "Indexing projects..." spinner within 3 seconds.
**Why human:** State transition sequence and auto-trigger chain require live browser execution.

#### 3. Index Status Bar After Completion

**Test:** Wait for the background Redis worker to complete indexing of a small GitLab repo.
**Expected:** Status bar updates from "Indexing projects..." to "N code symbols indexed across M projects" with last indexed date. Polling stops after status returns to "idle".
**Why human:** Requires running Redis worker, actual GitLab OAuth token, and real repo clone pipeline end-to-end.

### Gaps Summary

No gaps found. All 5 observable truths are verified, all 7 required artifacts exist and are substantive and wired, all 6 key links are confirmed, and all 3 GL requirements are satisfied.

---

_Verified: 2026-03-12T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
