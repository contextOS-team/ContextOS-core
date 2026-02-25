# Phase 7: GitHub Integration - Context

**Gathered:** 2026-02-25
**Status:** Ready for planning

<domain>
## Phase Boundary

GitHub PR data (reviews, comments, branch links) flows into the system, connecting code execution to Linear tickets so context pages include implementation details. This phase covers: GitHub App OAuth, repo selection, PR/review ingestion, PR-to-Linear linking, and webhook processing. It does NOT cover context generation changes to use GitHub data (Phase 4 handles synthesis).

</domain>

<decisions>
## Implementation Decisions

### PR-to-Linear Linking
- Match PRs to Linear tickets via **branch name pattern parsing** (e.g., `feat/ENG-123-add-auth` → ENG-123)
- Auto-detect Linear team keys from the connected Linear workspace API — no hardcoded prefixes
- When a PR **can't be auto-linked** (no issue ID in branch name), store it as unlinked — context generation can try fuzzy matching later
- **Multiple PRs per ticket are supported** — all linked PRs are stored, showing the full implementation story

### Data Scope
- Store: PR title, description, state (open/merged/closed), author, branch, reviewers, review verdicts (approved/changes requested)
- Store review comments with **file path + line range + comment body** — enough to reference "review on src/auth.ts:42"
- Ingest **all PRs including drafts** — drafts often contain early implementation notes; context generation can filter by state
- Store **current state only** — no state transition history (opened → merged timeline lives in GitHub)

### Repo Selection UX
- Use **GitHub App installation** (org-level) — one install covers all users, fine-grained permissions, built-in webhooks
- Present repos as a **searchable checkbox list** — same UX pattern as Slack channel picker
- New repos added to the org are **not auto-monitored** — user must manually add them via the repo picker
- On first connection, **backfill open PRs + PRs merged in the last 60 days** (wider than 30 to catch long-lived PRs)

### Webhook Handling
- Subscribe to: `pull_request` (opened/closed/merged/edited), `pull_request_review` (submitted), `pull_request_review_comment` (created)
- **Filter known bot accounts** (dependabot, renovate, etc.) — they add noise and rarely relate to feature tickets
- **Idempotent processing** with delivery ID tracking — same pattern as Linear webhooks in Phase 2
- **github.com only** for v1.0 — no GitHub Enterprise Server support

### Initial Sync Behavior
- Show **per-repo sync status**: syncing/synced/error with progress count (e.g., "12/45 PRs synced") on the repo card
- **Sequential sync with rate limit awareness** — one repo at a time, monitor remaining GitHub API rate limit, throttle if needed
- On sync failure: **mark repo as failed, keep partial data, allow manual retry** from integration page — resume from where it left off
- Backfill window: **60 days** — chosen because team members sometimes have PRs open for 1.5+ months

### Claude's Discretion
- Integration card UI design on the setup page
- GitHub App setup/install redirect flow details
- Exact bot account filtering list
- Error message copy and UX states
- Database schema design for PR/review models

</decisions>

<specifics>
## Specific Ideas

- Backfill window is 60 days because "Dulat had a PR open for 1.5 months" — real team workflow drives this number
- Follow existing patterns: repo picker mirrors Slack channel picker, webhook handling mirrors Linear webhook pattern, OAuth follows GitHub App install flow
- PR linking uses branch name only (not title/commits) to minimize false positives

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-github-integration*
*Context gathered: 2026-02-25*
