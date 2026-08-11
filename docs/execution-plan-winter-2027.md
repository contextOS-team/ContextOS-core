# ContextOS — Winter 2027 Execution Plan (code-grounded, v2)

> ## CUSTOMER EVIDENCE OVERRIDES ROADMAP.
> Every milestone below past August P0 is **conditional on customer validation, not the calendar**. If three pilots say the important problem is different, the architecture changes, not the pilots.

*v1 written 2026-08-11 against commit `639862d` after a six-subsystem code survey; v2 same day, incorporating review: reduced August scope, relation classifier instead of dedupe inversion, instrument-before-consolidating extraction, conditional November/December gates, DriftOutcome in schema from day one.*

## Verdict in one paragraph

The plan's pipeline is `SourceEvents → DecisionCandidates → Consequentiality → DecisionState → Impact → Checkers → Verifier → Drift → Context API → Guard`. Today the codebase has a **real, working front half** — 8 connectors, a mature candidate pipeline (`missed_decision_*`), consequentiality-ish gating, evidence links, a knowledge graph, an eval harness, multi-tenant scoping, API-key schema — and **nothing of the back half**: no DecisionState (decisions are untyped JSONB on `graph_nodes`, history overwritten in place), no supersedes/contradicts, no versioning, no impact inference, no drift, no LLM verifier, no working agent auth. The work is not a rewrite; it is **hardening one object (Decision), classifying decision relationships properly, and building Impact → Drift → Context API on infrastructure that already exists** — while getting customer evidence at every step before building the next.

The company, as a sequence:

```
existing ContextOS → make Decision reliable → make Decision temporal
→ understand consequences → compare with reality → Decision Drift
→ humans trust it → agents consume it → Decision Guard
```

---

## What already exists and maps onto the plan

| Plan concept | Existing code | Status |
|---|---|---|
| Connectors | 8 providers: Slack, Linear, Jira, GitHub, GitLab, Notion, Telegram, Fathom (webhooks + OAuth via Supabase Vault, per-workspace channel/repo/project scoping UI) | ✅ solid, gaps in lookback (below) |
| DecisionCandidate | `missed_decision_candidates` (00042): fingerprint dedup, confidence tiers, 7-state lifecycle, anti-hallucination quote validation, scan runs/state | ✅ strongest asset in the repo |
| Consequentiality filter | `impact_level` medium/high + business-category allow/block lists in `missed_decision_extractor.py` | 🟡 exists but LLM self-report; no persisted score |
| Evidence | `evidenced_by`/`has_evidence` graph edges carrying source_quote/link; `graph_nodes.source_type/source_id` back-pointers | 🟡 exists; payloads are unvalidated JSONB |
| Decision Graph | `graph_nodes`/`graph_edges` in Postgres + traverse_graph + communities + identity_mappings | ✅ plan says Postgres, not Neo4j — already right |
| Retrieval | pgvector HNSW + hybrid FTS (`hybrid_search()`), code_chunks via tree-sitter | ✅ |
| Review UI | candidate review with confirm/add-evidence/defer/reject-with-reason (`needs-review-suggestions.tsx`) | 🟡 pre-acceptance only |
| Evidence UI | rich per-source panel with freshness/verification labels — but only on ticket context pages | 🟡 lift later, don't polish in August |
| Evals | 2 golden JSONL datasets + threshold CLI runners + pytest gates (`backend/src/evals/`) | 🟡 synthetic fixtures, no CI |
| Tenant isolation | workspace_id + RLS on ~39 tables, append-only `audit_log`, Vault-encrypted tokens | ✅ most of the "security basics" |
| Agent auth | `api_keys` table + management service + settings UI (00016, 00022) | 🔴 **auth dependency never wired — keys can't authenticate anything** |
| MCP | `packages/mcp-server` scaffold (stdio, zod) | 🔴 sends an API key the backend rejects |

## The seven structural gaps

1. **Decisions are not an entity.** `graph_nodes` rows with free-form `properties.status` — `'active'` from one writer (`llm_extractor.py:294`), `'confirmed'` from another (`missed_decision_actions.py:319`), absent from a third (`digest.py`). `upsert_node` overwrites in place: **no history survives an update.** ContextOS must answer "what was the current decision on August 3?" — impossible today.
2. **Three parallel extraction paths** with different prompts, models, status conventions. Invariant to establish: **one Decision write path** (extraction mechanisms may stay plural — see Amendments).
3. **Decision-to-decision relationships don't exist.** Today a strong match against an existing artifact *suppresses* a candidate. Matching needs to become a **relation classification**, not a binary suppress/create.
4. **Evidence is mutable.** Source tables upsert raw_data in place; Slack/Telegram edits overwrite text by design. `data_retention.py` (currently uncalled) would scrub text/raw_data 24h after embedding — if ever wired up, it destroys the evidence base. Decide, don't discover.
5. **Lookback can't back the sales product.** Coverage Audit promises 30–90 days; Slack backfill is hardcoded **14 days / 100 messages per channel**, GitHub/GitLab 60 days, Telegram zero, Jira webhook registration is dead code. Historical lookback is **core GTM infrastructure**, not plumbing.
6. **No CI.** `deploy.yml` ships to prod on every push with zero tests, while a working eval+pytest gate sits unused locally. Gold sets are synthetic (15+21 cases) with no tooling to harvest customer corrections into labels.
7. **No machine principal.** `get_current_user` hardcodes one-workspace-per-human-JWT (`dependencies.py:167`); `GET /api/graph/decisions` silently hides decisions when a provider disconnects — unacceptable for an agent-facing source of truth.

---

## Amendments adopted in v2 (review corrections)

**A. Relation classifier replaces "inverted dedupe."** A strong semantic match means one of several things. Pipeline stage after candidate extraction:

```
candidate → retrieve related decisions (hybrid_search) → classify relation:
  SAME          → duplicate / attach as supporting evidence
  SUPPORTS      → reinforce existing decision (evidence++)
  SUPERSEDES    → propose supersession (human confirms)
  CONTRADICTS   → propose contradiction flag
  REFINES       → scope refinement / exception candidate
  UNRELATED     → new decision candidate
```

The candidate schema already carries `match_status`/`matched_entity_type/id` — extend those, don't greenfield. This classifier becomes core Decision State infrastructure.

**B. Instrument extraction paths before consolidating.** Tag every candidate with its producer (`missed_decision` / `llm_extractor` / `digest`), track customer confirmation + importance per producer for a few weeks, then consolidate deliberately. One **write** path from day one; plural detectors allowed to feed it.

**C. Drift outcomes are first-class from the first migration.** `drifts` carries the business metric directly:

```
detected_at / confirmed_at / owner_assigned_at / resolved_at / verified_at
resolution_type: jira_updated | linear_updated | doc_updated |
  implementation_changed | work_cancelled | timeline_changed |
  intentional_exception | other
```

The investor line is "31 confirmed drifts, 18 caused an actual engineering change" — the DB must answer it with one query, no interpretation.

**D. November/December are conditional, not calendar:**

```
IF Decision State trustworthy AND Drift useful AND customers acting
  THEN build Decision Context API
IF agents actually consume it
  THEN build Decision Guard (advisory)
ELSE keep improving Drift precision — that is the better application story.
```

**E. Immutable SourceEvent history: explicitly post-YC roadmap.** Frozen evidence quotes (`decision_evidence.captured_at`) suffice through Winter. But temporal drift reconstruction ("what did execution look like *at the time*?") will eventually need raw-event history. Parked deliberately, not forgotten.

---

## Month-by-month

### August — P0 only

**Business goal: 2 real companies connected. Technical goal: reliable Decision State v1.**

P0 (in order):
1. **CI gate** (~1 day): GitHub Actions workflow running `make test` (already executes both eval gates); `deploy.yml` depends on it. Also: park or delete `data_retention.py` with an explicit "never before evidence redesign" marker.
2. **Typed decision schema**: `decisions` (status CHECK: active | superseded | tentative | reversed | unknown; valid_from/valid_until; owner; confidence; consequentiality_score), `decision_versions` (append-only), `decision_evidence` (quote frozen at capture, `captured_at`), `decision_edges` (supersedes | contradicts | refines | relates_to).
3. **One canonical decision write service** — snapshots a version on every change; all three extractors route decision *writes* through it (extraction consolidation itself deferred, see Amendment B). Graph nodes remain as mirror/linking layer. The write service enforces two quality gates from day one, pulled forward from September because founder testing already hit both failure modes: **(a) consequentiality check** — an LLM skeptical pass ("is this actually a consequential decision?") applied uniformly, fixing the ungated `llm_extractor`/`digest` paths that currently pollute the list with non-decisions; **(b) write-time duplicate collapse** — hybrid-search existing decisions before insert; a strong SAME match attaches the mention as supporting evidence on the existing decision instead of creating a new row, fixing repeated-Slack-mention duplicates (fingerprint dedup can't catch rewordings). The full six-way relation classifier still lands in September.
4. **Migrate** confirmed missed-decision candidates + existing Decision graph nodes into the new tables.
5. **Decision State UI**: status-grouped list + basic detail (extend `decision-node.ts`, add nav entry). Basic decision feedback actions (correct / wrong / superseded) → `decision_feedback` table. *Not* the polished Evidence screen.
6. **Historical scan, configurable 30/60/90 days, for Slack + one tracker (Linear or Jira, whichever the pilot uses) + GitHub.** Slack = remove the 14-day/100-msg cap with paginated backfill. This is the Coverage Audit's engine and a sales feature.
7. **Run it on 2 pilot companies' real data.**

Deferred from August (do when scans run on real data): full Jira webhook cleanup, extraction-path deletion, polished Evidence screen, sophisticated supersession UX, remaining-provider lookback completeness.

**Exit gate: 2 orgs + ≥5 customer-confirmed decisions with status, versions, evidence rows underneath.**

### September — find real Decision Drift

**Primary focus: precision. Target: 10+ customer-confirmed meaningful drifts.**

- Relation classifier (Amendment A) in the candidate pipeline — supersession detection now runs through it.
- `expected_consequences` + impact-inference step on decision confirmation (`LLMClient.generate_json`, traced).
- **Per-artifact checkers**: generalize `verify_candidate_actionability` into scheduled re-checks persisting `artifact_observations`; retrieval via `hybrid_search()`, not Jaccard-over-50-rows.
- **Skeptical verifier**: separate LLM pass whose instruction is *prove this is NOT meaningful drift* (consequential? still active? artifact really affected? intentional? explained elsewhere? semantic-only? would a CTO care?). Only survivors reach the customer. This is the direct fix for Needs-Review noise.
- `drifts` table with lifecycle + resolution_type (Amendment C); surfaced through the existing `suggestions` contract.
- Scans move to the Redis Streams worker pattern (`gitlab_sync_worker.py` template) — verifier latency won't fit the 15-min in-process loop.
- **Evals**: gold-set exporter harvesting confirmed/rejected candidates + `decision_feedback` into labeled cases (plan taxonomy: true-important / true-minor / not-a-decision / superseded / already-covered / wrong-artifact / intentional-exception / ambiguous); target 50–100 real cases; add state-resolution, impact-precision, drift-precision, usefulness metric families on the existing runner pattern.

### October — get somebody to pay

- Productize **Decision Coverage Audit**: scope pickers exist; add scan-run + audit result screen ("27 decisions, 21 aligned, 4 uncertain, 2 drifts") + auto-generated 30-day report (SELECTs once drifts are tables).
- Continuous monitoring + drift lifecycle UI with structured feedback codes (confirmed / false_positive / intentional_exception / decision_superseded / wrong_artifact / not_important) — backend-validated enum. Every click is future eval data and future moat.
- Design-partner pricing by invoice. **No billing system.**
- Target: 3–5 companies, 1–2 paying, 10+ drift-driven actions.

### November — prove a stranger wants it

- **First cold-acquired customer** is the month's actual goal. Product work is subordinate.
- *Conditional on the Amendment-D gate:* wire API-key auth (`get_api_principal` dependency; `key_prefix` index — salted hashes can't be looked up by hash; scopes/expiry/last_used_at; per-key rate limits), then **Decision Context API v1** (`/api/v1/`): `get_current_decisions`, `get_decision` (versions + evidence + supersession chain), `get_constraints`. Read-only. Expose verification/provenance states (auto-saved unreviewed decisions must look lower-trust to agents). No disconnected-provider hiding.
- Fix `packages/mcp-server` against it — MCP *is* the agent-neutral interface (Claude Code, Cursor, Codex). One killer demo: agent asks for relevant active decisions before working. Read-only, no enforcement.

### December — application-grade evidence

Priority order: customers, confirmed drifts, actions, precision, case studies, cold funnel. Applications (YC current + a16z submitted by mid-November per the GTM plan) get updated with every metric improvement.

*Conditional on the Amendment-D gate:* advisory `check_action` returning `no_known_conflict | potential_conflict | requires_review` (never "ALLOW"); every verdict persisted — the Guard eval set accumulates for free; `decision_exceptions` (scope, approved_by, expires_at) so legitimate exceptions stop reading as drift; offline Guard eval dataset with positive *and* negative cases.

If Drift precision or adoption is weak: skip Guard, keep making Drift better. "27 real drifts, 19 caused changes" beats "we built Guard but nobody uses it."

### January — no new categories. Sell. Fix. Improve.

---

## Explicit "change" list

| # | Change | From → To |
|---|---|---|
| 1 | Decision storage | graph-node JSONB → typed `decisions` + versions + evidence (graph keeps linking role) |
| 2 | Match handling | match ⇒ suppress → **relation classifier** (SAME/SUPPORTS/SUPERSEDES/CONTRADICTS/REFINES/UNRELATED) |
| 3 | Decision writes | 3 uncoordinated writers → 1 canonical write service (detectors stay plural until instrumented data says otherwise) |
| 4 | Deploy | push-to-prod → CI-gated (tests + eval thresholds) |
| 5 | Slack backfill | 14 days / 100 msgs → configurable 30/60/90 days |
| 6 | Feedback | JSONB append inside `evidence` → first-class `decision_feedback` table with enum reasons |
| 7 | Matching retrieval | Jaccard over 50-row scans → `hybrid_search()` |
| 8 | Scan orchestration | in-process 15-min loop → Redis Streams workers |
| 9 | API identity | human-JWT-only, one workspace → machine principal + scoped API keys (when gate passes) |
| 10 | Decision visibility | hidden when provider disconnects → always visible with provenance state |

## Do-NOT-build list (confirmed against code)

- No Neo4j/GraphRAG rewrite — `graph_edges` in Postgres already is the semantic graph.
- No new connectors — 8 exist; Jira needs *fixing*, not company adding a ninth.
- No graph-viz investment; the React-Flow explorer exists.
- No billing system, no enforcement/blocking Guard, no mobile, no meeting bot.
- No unified immutable SourceEvent store before Winter — frozen evidence quotes now; raw-event history is a **named post-YC roadmap item** (Amendment E).

## Infrastructure realities

- **Supabase free tier (500 MB) is 56% full, embeddings-dominated.** 5–8 orgs with 90-day backfills blow through it in September. Decide then: $25/mo Pro (zero work) or embeddings/code_chunks → pgvector on the Hetzner box (verify no SQL joins to workspace tables first). Budget it; don't discover it.
- **Prod is one 4 GB / 2-CPU Hetzner box shared with scraper containers.** Fine for pilots; watch memory when workers land in September. Nightly `pg_dump` of Supabase to the box is still unset and should exist (free tier has no backups).
- **The investor metrics sheet falls out of the schema for free** once decisions/drifts/feedback are tables with outcome fields — the strongest reason August P0 comes first: every later month's evidence compounds on it.
