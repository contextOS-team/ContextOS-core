# ContextOS — Technical Plan, August 2026 → January 2027

*Companion to `docs/execution-plan-winter-2027.md` (strategy/sequencing). This document is the engineering side: schemas, service contracts, API shapes, file-level changes, and definition-of-done per phase. Grounded in the 2026-08-11 six-subsystem code survey at commit `639862d`. House style for all new tables: `workspace_id NOT NULL` FK, RLS `workspace_access` policy via `workspace_members`, `moddatetime` trigger, soft delete via `deleted_at`, partial unique indexes `WHERE deleted_at IS NULL` — same as the existing 47 migrations.*

**Gate rule from the execution plan applies here: Phases 4–5 build only if the Phase 2–3 metrics say customers trust and act on Drift.**

---

## Architecture: current → target

```
CURRENT                                   TARGET (Winter)
8 connectors → per-provider tables        8 connectors → per-provider tables (unchanged)
     ↓                                         ↓
3 uncoordinated extractors                N detectors (instrumented by producer tag)
     ↓                                         ↓
graph_nodes JSONB "decisions"             missed_decision_candidates  (existing, extended)
(no status, no history, no dedup          ↓
 beyond exact fingerprints)               relation classifier (SAME/SUPPORTS/SUPersedes/…)
                                               ↓
                                          decision_writer  ←— THE ONLY WRITE PATH
                                          (consequentiality gate + duplicate collapse)
                                               ↓
                                          decisions + decision_versions + decision_evidence
                                          + decision_edges          (typed, temporal)
                                               ↓
                                          impact inference → expected_consequences
                                               ↓
                                          artifact checkers → artifact_observations
                                               ↓
                                          skeptical verifier → drifts (lifecycle + outcome)
                                               ↓                    ↓
                                          dashboard UI        /api/v1 Decision Context API
                                          + feedback                ↓
                                               ↓               MCP server → coding agents
                                          decision_feedback         ↓
                                          → eval gold sets     check_action (Guard, advisory)
```

---

## Phase 0 — CI and safety rails (2 days, before anything else)

**New `.github/workflows/test.yml`**
- Job `test`: checkout → uv/pip install backend deps → `make test` (pytest already executes both golden-dataset threshold gates deterministically — no live LLM calls, CI-safe by design). Add a Postgres service container only if the suite requires it (first task: verify `make test` runs headless; fix fixtures if not).
- Job `web`: `npm ci && npm test --workspace apps/web` (vitest suite exists, e.g. `needs-review-suggestions.test.tsx`).

**Change `.github/workflows/deploy.yml`**
- Convert to `workflow_run`-gated or same-workflow `needs: [test, web]`. Today it deploys to prod on every push to main with zero checks — this is the single highest-leverage change in the whole plan.

**Retention conflict**
- Delete `backend/src/services/data_retention.py` (zero callers today; if ever wired it scrubs `text`/`raw_data` 24h after embedding, destroying the evidence base). Git history preserves it; add a note in the privacy section of README pointing at `decision_evidence.captured_at` as the evidence-preservation mechanism.

**DoD:** a PR with a failing eval threshold cannot reach production.

---

## Phase 1 — Decision State v1 (August, P0)

### 1.1 Schema (one migration set, ~00046+)

```sql
create table decisions (
  id                        uuid primary key default gen_random_uuid(),
  workspace_id              uuid not null references workspaces(id),
  statement                 text not null,
  rationale                 text,
  status                    text not null default 'active'
    check (status in ('active','superseded','tentative','reversed','unknown')),
  valid_from                timestamptz not null default now(),
  valid_until               timestamptz,          -- set when superseded/reversed
  owner_node_id             uuid references graph_nodes(id),   -- canonical Person node
  confidence                real,
  consequentiality_score    real,                 -- persisted numeric, not just tier
  producer                  text not null
    check (producer in ('missed_decision','llm_extractor','digest','manual','import')),
  created_from_candidate_id uuid references missed_decision_candidates(id),
  graph_node_id             uuid,                 -- mirror node in graph layer
  created_at, updated_at, deleted_at              -- house style + trigger + RLS
);

create table decision_versions (        -- append-only; INSERT-only service discipline
  id            uuid primary key default gen_random_uuid(),
  decision_id   uuid not null references decisions(id),
  workspace_id  uuid not null,
  version       int  not null,
  snapshot      jsonb not null,         -- full decision row at time of change
  change_type   text not null
    check (change_type in ('created','status_changed','evidence_added',
                           'statement_edited','superseded','imported')),
  change_reason text,
  actor         text not null,          -- user id or 'system:<service>'
  created_at    timestamptz not null default now(),
  unique (decision_id, version)
);

create table decision_evidence (
  id           uuid primary key default gen_random_uuid(),
  decision_id  uuid not null references decisions(id),
  workspace_id uuid not null,
  source_type  text not null,           -- reuse SOURCE_TYPE_MAP vocabulary
  source_id    uuid not null,
  quote        text not null,           -- FROZEN at capture; never re-read from source
  source_link  text,
  captured_at  timestamptz not null default now(),
  added_by     text not null
);

create table decision_edges (
  id            uuid primary key default gen_random_uuid(),
  workspace_id  uuid not null,
  from_decision uuid not null references decisions(id),
  to_decision   uuid not null references decisions(id),
  edge_type     text not null
    check (edge_type in ('supersedes','contradicts','refines','relates_to')),
  rationale     text,
  actor         text not null,
  created_at    timestamptz not null default now(),
  unique (workspace_id, from_decision, to_decision, edge_type)
);

create table decision_feedback (        -- append-only
  id           uuid primary key default gen_random_uuid(),
  workspace_id uuid not null,
  decision_id  uuid not null references decisions(id),
  user_id      uuid not null,
  verdict      text not null
    check (verdict in ('correct','wrong','superseded','minor',
                       'missing_evidence','duplicate','not_important')),
  note         text,
  created_at   timestamptz not null default now()
);
```

Notes:
- `graph_nodes`/`graph_edges` stay as the **linking layer** (people, tickets, PRs, communities). `decisions.graph_node_id` mirrors each decision into the graph so traverse/communities/GraphRAG keep working. Graph mirror is written by the writer service only.
- Temporal query the product must answer: *"current decision on date D"* = `status='active' AND valid_from <= D AND (valid_until IS NULL OR valid_until > D)` — plus `decision_versions` for the audit trail.

### 1.2 Canonical write service — `backend/src/services/decision_writer.py`

The **only** module allowed to touch `decisions`. Contract:

```python
@dataclass
class DecisionDraft:
    statement: str; rationale: str | None
    evidence: list[EvidenceRef]          # source_type, source_id, quote, link
    producer: str                        # which detector
    candidate_id: UUID | None
    people: list[str]; confidence: float | None

class WriteOutcome(Enum):
    CREATED, MERGED_AS_EVIDENCE, REJECTED_NOT_CONSEQUENTIAL

async def create_decision(session, ws_id, draft) -> tuple[WriteOutcome, UUID | None]
async def change_status(session, ws_id, decision_id, new_status, reason, actor,
                        superseded_by: UUID | None = None) -> None
async def add_evidence(session, ws_id, decision_id, refs, actor) -> None
```

`create_decision` internally, in order:

1. **Consequentiality gate** (fixes observed junk-decision problem): one `LLMClient.generate_json` call (traced via existing Langfuse/Laminar wiring) → `{is_decision: bool, consequential: bool, score: float, category: str, reason: str}`. Score below threshold (config, start 0.6) ⇒ `REJECTED_NOT_CONSEQUENTIAL`, reason persisted on the candidate. This gate applies to **all** producers — closing the hole where `llm_extractor.py` and `digest.py` write ungated.
2. **Duplicate collapse** (fixes observed repeated-Slack-decision problem): embed statement → `hybrid_search()` restricted to decision embeddings, top-k (k=5) → if best score ≥ τ, one LLM confirm call ("same decision?") → yes ⇒ `add_evidence` on the existing decision + version row `evidence_added`, return `MERGED_AS_EVIDENCE`. Replaces exact-fingerprint + Jaccard-over-50-rows matching for the decision store (candidate-level fingerprints stay for scan idempotency).
3. Insert `decisions` row + `decision_versions` v1 + `decision_evidence` rows + graph mirror node (via `graph_ops`, one place).

`change_status` snapshots the current row into `decision_versions` **before** mutating; supersession sets `valid_until` and inserts a `supersedes` edge.

**Call-site changes (writers stop writing graph nodes directly):**
- `llm_extractor.py` `persist_decision` (≈ lines 251–335) → `decision_writer.create_decision(producer='llm_extractor')`
- `missed_decision_actions.py` `promote_candidate_to_decision` (≈ 263–363) → same, `producer='missed_decision'`
- `digest.py` decision output → same, `producer='digest'`
- Producer instrumentation is free from here: `SELECT producer, count(*), avg(consequentiality_score) … GROUP BY producer` joined with `decision_feedback` answers "which extractor earns its keep" — consolidation happens on that data, later.

### 1.3 Backfill migration (script, `backend/scripts/migrate_decisions.py`)

Modeled on `reclassify_missed_decisions.py` (dry-run/apply flags):
- Import existing Decision graph nodes + `confirmed` candidates through the writer with `producer='import'`, **duplicate collapse ON** (this deduplicates the current polluted list as a side effect), consequentiality gate in **report mode** (score stored, nothing auto-deleted; low scorers listed for one manual review pass in the new UI).

### 1.4 Historical scan windows (Coverage Audit engine)

- `workspace_integrations.config` gains `backfill_days: 30|60|90` (per provider).
- `slack_messages.py:72-73`: remove `14 days` + `100 msgs/conversation` cap → cursor-paginated history fetch honoring `backfill_days`, run inside a background job (rate-limit sleeps must not block the request path).
- `github_sync.py:60`, `gitlab_sync.py:53`: `BACKFILL_DAYS` constant → config read.
- Linear/Jira full syncs accept the same window param (they currently pull unbounded history — bound it).
- Defer: Jira webhook registration cleanup, Telegram lookback (impossible by design — bot API has no history).

### 1.5 API + frontend

Backend (`routers/decisions.py`, new — human-facing, Supabase-JWT auth):
- `GET /api/decisions?status=` — typed list (no more untyped `graph_nodes.properties`)
- `GET /api/decisions/{id}` — row + versions + evidence + edges
- `POST /api/decisions/{id}/feedback` — enum-validated verdict
- `POST /api/decisions/{id}/status` — manual status change (Review screen actions)

Frontend (`apps/web`):
- Nav entry for Decisions in `chrome-nav.tsx` (currently orphaned).
- `decisions/` list: status-grouped, evidence-count chip ("discussed 4× in 3 channels" — the duplicate fix made visible), consequentiality-sorted.
- Detail: evidence rows with `captured_at` + provider deep links (reuse `source-reference` route); feedback buttons reusing the `needs-review-suggestions.tsx` row pattern → `decision_feedback`.
- Defer the polished Evidence panel extraction from `context/[id]/source-explanations.tsx` to September.

**DoD Phase 1:** 2 pilot workspaces scanned 30–90 days back; decisions list deduplicated and gated; every decision shows status + evidence; ≥5 customer-confirmed decisions recorded as `decision_feedback(verdict='correct')`; producer instrumentation live.

---

## Phase 2 — Impact → Drift (September)

### 2.1 Relation classifier (full version)

New `backend/src/services/decision_relations.py`. Input: candidate (or new decision draft) + top-k related active decisions (hybrid retrieval). One structured LLM call →

```json
{ "relation": "SAME|SUPPORTS|SUPERSEDES|CONTRADICTS|REFINES|UNRELATED",
  "target_decision_id": "...", "confidence": 0.87, "rationale": "..." }
```

Action mapping: SAME→merge evidence · SUPPORTS→evidence + version note · SUPERSEDES→`proposed_supersession` surfaced for human confirm (then `change_status` + edge) · CONTRADICTS→`contradicts` edge + surfaced · REFINES→`refines` edge, candidate may become exception (Dec) · UNRELATED→normal create. Persist onto the candidate's existing `match_status`/`matched_entity_type/id` columns (extend the CHECK) — no new table needed.

### 2.2 Impact inference + checkers + verifier (schema)

```sql
create table expected_consequences (
  id uuid pk, workspace_id uuid not null, decision_id uuid not null references decisions(id),
  target_type text not null check (target_type in ('linear','jira','github','docs','release','other')),
  target_query text not null,         -- natural-language + optional entity ref
  expected_state text not null,
  rationale text, importance text check (importance in ('high','medium','low')),
  confidence real,
  status text not null default 'pending' check (status in ('pending','checked','invalidated')),
  created_at …
);

create table artifact_observations (
  id uuid pk, workspace_id uuid not null,
  expected_consequence_id uuid not null references expected_consequences(id),
  checker text not null,              -- 'linear','jira','github','docs'
  observed_state text not null,
  consistent boolean,
  evidence jsonb not null,            -- [{source_type, source_id, quote, link}]
  checked_at timestamptz not null default now()
);

create table drifts (
  id uuid pk, workspace_id uuid not null,
  decision_id uuid not null references decisions(id),
  expected_consequence_id uuid references expected_consequences(id),
  summary text not null, severity text check (severity in ('high','medium','low')),
  verifier_verdict jsonb not null,    -- full skeptical-verifier output, incl. kill checklist
  -- lifecycle (Amendment C: outcome is first-class from day one)
  detected_at timestamptz not null default now(),
  confirmed_at timestamptz, owner_user_id uuid, owner_assigned_at timestamptz,
  resolved_at timestamptz, verified_at timestamptz,
  resolution_type text check (resolution_type in
    ('jira_updated','linear_updated','doc_updated','implementation_changed',
     'work_cancelled','timeline_changed','intentional_exception','other')),
  feedback_verdict text check (feedback_verdict in
    ('confirmed','false_positive','intentional_exception','decision_superseded',
     'wrong_artifact','not_important')),
  suggestion_id uuid references suggestions(id)   -- surfaced via existing contract
);
```

The investor metric is now one query: `count(*) filter (where resolved_at is not null) / count(*) filter (where confirmed_at is not null)`.

### 2.3 Pipeline services

- `impact_inference.py`: on decision confirm → LLM → N `expected_consequences` rows.
- `checkers/{linear,jira,github,docs}.py` implementing `async def check(consequence) -> ArtifactObservation` — generalized from `missed_decision_actionability.py`'s provider search, but retrieval via `hybrid_search()` + provider-table queries instead of Jaccard `.limit(50)` scans, and **re-run on schedule** (not just at candidate creation).
- `skeptical_verifier.py`: separate LLM pass per inconsistent observation, instruction = *prove this is NOT meaningful drift* (checklist: consequential? decision still active? artifact really affected? intentional? explained by another artifact? semantic-only difference? would a CTO care?). Verdict persisted whole in `drifts.verifier_verdict` — including kills, which never surface but feed evals.

### 2.4 Orchestration off the request path

New `backend/src/workers/decision_pipeline_worker.py` on the **existing Redis Streams consumer-group pattern** (`gitlab_sync_worker.py` is the template, with stale-job reclaim). Streams: `decision.scan`, `impact.infer`, `artifact.check`, `drift.verify`. `sync_scheduler.py` only *enqueues*; the 15-minute in-process loop stops doing LLM work (it already starves on Slack rate-limit sleeps).

### 2.5 Evals become real

- `backend/scripts/export_gold_cases.py`: harvest `decision_feedback` + candidate lifecycle outcomes into golden JSONL (existing format), with provenance fields (workspace, labeler=user, date). Target 50–100 real cases across the 8-category taxonomy.
- New runners on the existing `EvalThresholds` pattern: `evals/decision_state.py` (state-resolution accuracy), `evals/impact.py` (impact precision), `evals/drift.py` (drift precision), plus a usefulness report from `drifts.feedback_verdict`.
- Fix vacuous-pass semantics (precision=1.0 on zero positives) while consolidating the two existing runner styles.
- All wired into `make test` ⇒ CI gate from Phase 0 now guards the whole pipeline.

**DoD Phase 2:** ≥10 customer-confirmed drifts; verifier kill-rate and drift precision measured; scans run in workers with the API process idle-safe; gold set ≥50 real cases.

---

## Phase 3 — Coverage Audit productization (October)

- `audit_runs` table (id, workspace, window_days, scope jsonb, status, counts jsonb, started/finished) — thin generalization of `missed_decision_scan_runs`; one audit = scan + extract + classify + impact + check + verify for a scoped window.
- Audit result screen: "N decisions reconstructed / aligned / uncertain / drifts" + drill-down. Report = same aggregates over 30 days at `GET /api/reports/monthly`; render as printable HTML (no PDF pipeline).
- Drift lifecycle endpoints: `POST /api/drifts/{id}/confirm | assign | resolve | verify` (resolve requires `resolution_type`), feedback verdicts enum-validated server-side.
- Realtime on `drifts`/`decisions` via the proven Supabase-channel hook pattern (`use-context-pages-realtime.ts`).
- Ops hardening this month: nightly `pg_dump` of Supabase to the Hetzner box (cron + 14-day rotation) — free tier has no backups; resolve the Supabase 500 MB decision (Pro $25/mo, or move `embeddings`+`code_chunks` to pgvector on the box **after verifying no SQL joins to workspace tables**).
- Billing: invoices. No Stripe integration.

**DoD Phase 3:** a stranger-operable audit flow (connect → scope → scan → report), 1–2 paying design partners, ≥10 drift-driven `resolution_type` rows.

---

## Phase 4 — Decision Context API (November, **conditional on Drift metrics**)

### 4.1 Machine auth (the missing half of `api_keys`)

- Migration: `alter table api_keys add column scopes text[] not null default '{decisions:read}', add column expires_at timestamptz, add column last_used_at timestamptz; create index on api_keys (key_prefix);` — prefix lookup is mandatory because per-key salts (00022) make hash lookup impossible; the survey confirmed the intended path was never implemented.
- New dependency `get_api_principal` in `dependencies.py`: parse `Bearer cos_…` → lookup by `key_prefix` → `verify_api_key` (exists, currently uncalled) → `MachinePrincipal(workspace_id, key_id, scopes)` — deliberately *not* `UserContext` (which requires email and one-human-workspace). Touch points: Sentry middleware and audit logging get a principal union type.
- Per-key rate limiting: existing Redis middleware, key derivation on `key_id`; stamp `last_used_at`.

### 4.2 `/api/v1` (versioned, agent-facing, read-only)

Envelope: `{ "schema_version": "1", "data": … }`. Endpoints:

```
GET /api/v1/decisions?query=&repository=&service=&team=&status=active
GET /api/v1/decisions/{id}          → row + versions + evidence + supersession chain
GET /api/v1/constraints?action=&repository=&project=
```

Response items always carry provenance: `verification: reviewed|auto_saved`, `confidence`, `consequentiality_score`, evidence links. Two deliberate semantic differences from the human endpoints: **no disconnected-provider filtering** (decisions must not vanish when an integration disconnects — `_node_passes_source_filter` is not inherited), and auto-saved unreviewed decisions are visibly lower-trust rather than hidden.

### 4.3 MCP server (`packages/mcp-server`)

Fix auth (send the key to endpoints that now accept it), repoint the three existing tools, add `get_current_decisions` / `get_decision` / `get_constraints` tools. MCP *is* the agent-neutral interface — Claude Code, Cursor, Codex all consume it; no per-agent builds. Demo script: agent asked to "continue self-hosted implementation" → queries ContextOS → surfaces the deferral decision with evidence → asks the human. Read-only.

**DoD Phase 4:** an API key can query current decisions from a clean machine; MCP demo runs against production data of a consenting pilot; p95 < 1s on `get_current_decisions`.

---

## Phase 5 — Decision Guard advisory (December, **conditional on agents consuming Phase 4**)

```
POST /api/v1/check_action  { proposed_action, actor, scope{repository?, project?} }
  → retrieval: hybrid_search + graph traverse over ACTIVE decisions (+ exceptions)
  → one LLM conflict assessment
  → { status: "no_known_conflict" | "potential_conflict" | "requires_review",
      decisions: […], evidence: […], rationale, confidence }
```

- Never `ALLOW` — the vocabulary is epistemically bounded by design.
- Every verdict persisted (`guard_verdicts`: input, retrieved set, verdict, latency) — the Guard eval set accumulates from day one of usage.
- `decision_exceptions` table (decision_id, scope, approved_by, reason, valid_from, expires_at, evidence) — consulted by checkers *and* guard so sanctioned exceptions stop reading as drift.
- Offline eval dataset: JSONL `{action, active_decisions, expected_verdict}` with hard negatives ("optimize Postgres query" vs "Postgres-only architecture" ⇒ `no_known_conflict`), runner on the standard pattern, thresholded in CI. A guard that cries wolf dies in the demo.

**DoD Phase 5:** advisory verdicts on real org state; false-warning rate measured; zero blocking behavior.

---

## Cross-cutting engineering rules

| Area | Rule |
|---|---|
| LLM calls | All through `LLMClient.generate_json` — structured output + Langfuse/Laminar tracing for free. Prompt changes ship with an eval-case delta. |
| Migrations | Idempotent, through `scripts/deploy-migrations.sh`'s version ledger. Backfills as dry-run/apply scripts (`reclassify_missed_decisions.py` pattern). |
| Writes | `decisions` only via `decision_writer`; `decision_versions`/`decision_feedback` append-only (enforced by service discipline + no UPDATE grants if practical). |
| Tenancy | Every new table: `workspace_id NOT NULL` + RLS; new pipeline code must pass the workspace filter explicitly (backend bypasses RLS via direct asyncpg — app-level filters are the real boundary; the `code_chunks` cross-tenant bug (fixed in 00011) is the cautionary tale). |
| Evidence | Quotes frozen at `captured_at`. Raw-event immutable history is a named **post-YC** item, not silently dropped. |
| Capacity | Supabase 500 MB decision lands in September (embeddings-dominated; pilots' 90-day scans will hit it). Hetzner box: watch RAM when workers land; CX32 (8 GB, ~€8/mo) is the pressure valve. Nightly `pg_dump` from October at latest. |
| Observability | Pipeline stage counters (candidates in → gated out → merged → created; consequences → observations → kills → drifts) exposed on the internal metrics dashboard — these are also the investor numbers. |

## Deliberately not building (technical form)

No Neo4j / GraphRAG rewrite (Postgres `graph_edges` stays) · no new connectors (Jira gets *fixed*, not multiplied) · no billing system · no blocking Guard · no unified immutable SourceEvent store before Winter (post-YC roadmap) · no mobile · no meeting bot (Fathom exists) · no enterprise permission system unless a deal forces it.
