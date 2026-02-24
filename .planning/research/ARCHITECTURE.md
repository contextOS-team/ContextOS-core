# Architecture Research

**Domain:** AI-powered developer context synthesis platform
**Researched:** 2026-02-24
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │
│  │  Next.js 15  │  │  MCP Server  │  │  External Webhooks       │   │
│  │  (Dashboard) │  │  (stdio→HTTP)│  │  (Linear, Slack)         │   │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘   │
│         │ reads            │ HTTP                 │ HTTP POST         │
├─────────┼──────────────────┼─────────────────────┼───────────────────┤
│         │                  │       API LAYER      │                   │
│         │           ┌──────┴──────────────────────┴──────────┐       │
│         │           │          FastAPI Backend                │       │
│         │           │  ┌─────────┐ ┌──────────┐ ┌─────────┐ │       │
│         │           │  │ Context │ │ Webhook  │ │  OAuth   │ │       │
│         │           │  │  API    │ │ Handlers │ │  Flows   │ │       │
│         │           │  └────┬────┘ └────┬─────┘ └────┬────-┘ │       │
│         │           └───────┼───────────┼────────────┼───────┘       │
├─────────┼───────────────────┼───────────┼────────────┼───────────────┤
│         │         PROCESSING LAYER      │            │               │
│         │           ┌───────┴───────────┴────┐  ┌────┴────┐         │
│         │           │  BackgroundTasks        │  │ Ingest  │         │
│         │           │  ┌──────────────────┐   │  │ Layer   │         │
│         │           │  │   LangGraph       │   │  └────┬────┘         │
│         │           │  │   (Data Gather)   │   │       │             │
│         │           │  └────────┬─────────┘   │       │             │
│         │           │  ┌────────┴─────────┐   │       │             │
│         │           │  │  Gemini Flash     │   │       │             │
│         │           │  │  (Synthesis)      │   │       │             │
│         │           │  └──────────────────┘   │       │             │
│         │           └─────────────────────────┘       │             │
├─────────┼─────────────────────────────────────────────┼─────────────┤
│         │              DATA LAYER                     │             │
│         ▼                                             ▼             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  Supabase (PostgreSQL + pgvector)             │   │
│  │  ┌───────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────┐  │   │
│  │  │ Workspaces│ │  Tickets │ │  Messages │ │  Embeddings  │  │   │
│  │  │  + RLS    │ │  + Pages │ │  + Threads│ │  (vector)    │  │   │
│  │  └───────────┘ └──────────┘ └───────────┘ └──────────────┘  │   │
│  │  ┌──────────────┐ ┌─────────────┐ ┌──────────────────────┐  │   │
│  │  │ Context Pages│ │ OAuth Tokens│ │  Supabase Auth       │  │   │
│  │  │  (output)    │ │ (Vault)     │ │  (JWT + sessions)    │  │   │
│  │  └──────────────┘ └─────────────┘ └──────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Next.js Dashboard** | UI rendering, auth redirects, direct data reads, real-time subscriptions | Supabase (reads), FastAPI (actions) |
| **FastAPI Backend** | Business logic, webhook handling, OAuth flows, context generation orchestration | Supabase (writes), LLM APIs, External services |
| **LangGraph Pipeline** | Multi-step data gathering: fetch ticket, find related Slack threads, retrieve docs | FastAPI (invoked by), Supabase (queries), Embedding store |
| **Gemini Flash** | Single synthesis call: generates 5-section context page from gathered data | LangGraph (invoked by) |
| **Ingestion Layer** | Normalize and store incoming data from Linear/Slack webhooks, generate embeddings | Webhook handlers (invoked by), Supabase (writes), Embedding model |
| **MCP Server** | Expose context tools to IDE coding assistants over stdio | FastAPI backend (HTTP calls to Railway) |
| **Supabase** | Data storage, auth, RLS multi-tenancy, real-time subscriptions, vector search | All components |
| **Webhook Handlers** | Receive, verify signatures, normalize, and dispatch Linear/Slack events | External services (receives from), Ingestion layer (dispatches to) |
| **OAuth Manager** | Handle OAuth2 flows for Linear/Slack, store tokens in Vault, refresh on expiry | External OAuth providers, Supabase Vault |

## Recommended Project Structure

```
backend/
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory, middleware, lifespan
│   ├── config.py                  # Pydantic Settings (already exists)
│   ├── dependencies.py            # FastAPI dependency injection (DB clients, auth)
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── context.py         # POST /context/{ticket_id}/generate, GET status
│   │       ├── webhooks.py        # POST /webhooks/linear, /webhooks/slack
│   │       ├── oauth.py           # GET /oauth/{provider}/callback, /oauth/{provider}/start
│   │       ├── mcp.py             # Endpoints consumed by MCP server
│   │       └── health.py          # GET /health
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── linear.py              # Linear API client, data normalization
│   │   ├── slack.py               # Slack API client, data normalization
│   │   └── base.py                # Common ingestion interface
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── gather.py              # LangGraph graph: data gathering pipeline
│   │   ├── nodes.py               # Individual graph nodes (fetch_ticket, find_slack, etc.)
│   │   └── state.py               # TypedDict state schema for the graph
│   ├── synthesis/
│   │   ├── __init__.py
│   │   ├── generator.py           # Gemini Flash API call, prompt construction
│   │   ├── prompts.py             # Synthesis prompt templates
│   │   └── formatter.py           # Markdown output formatting, section structure
│   ├── embeddings/
│   │   ├── __init__.py
│   │   ├── service.py             # Generate embeddings, upsert to pgvector
│   │   └── search.py              # Vector similarity search via match_embeddings()
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── oauth.py               # OAuth2 flow handlers (Linear, Slack)
│   │   ├── tokens.py              # Token storage/refresh via Supabase Vault
│   │   └── middleware.py          # Service-role auth for backend operations
│   └── workers/
│       ├── __init__.py
│       └── tasks.py               # Background task definitions (wrappers)
│
apps/web/
├── src/
│   ├── app/
│   │   ├── layout.tsx             # Root layout with Supabase provider
│   │   ├── page.tsx               # Landing / redirect to dashboard
│   │   ├── (auth)/
│   │   │   ├── login/page.tsx
│   │   │   └── callback/route.ts  # Supabase auth callback
│   │   ├── (dashboard)/
│   │   │   ├── layout.tsx         # Auth-gated dashboard layout
│   │   │   ├── page.tsx           # Context pages feed
│   │   │   ├── context/[id]/page.tsx  # Context page detail view
│   │   │   ├── settings/page.tsx  # API keys, team settings
│   │   │   └── integrations/page.tsx  # OAuth connect/disconnect
│   │   └── api/                   # Next.js API routes (minimal, mostly proxy)
│   ├── components/
│   │   ├── context/               # Context page components
│   │   ├── integrations/          # OAuth connection components
│   │   └── ui/                    # shadcn/ui primitives
│   └── lib/
│       ├── supabase/
│       │   ├── client.ts          # Browser Supabase client
│       │   ├── server.ts          # Server-side Supabase client
│       │   └── middleware.ts      # Auth middleware
│       ├── api.ts                 # FastAPI backend client
│       └── hooks/
│           └── use-realtime.ts    # Supabase realtime subscription hooks
│
packages/mcp-server/
├── src/
│   ├── index.ts                   # Entry point, MCP server setup
│   ├── tools/
│   │   ├── get-feature-context.ts # Fetch context page for a ticket
│   │   ├── search-context.ts      # Semantic search across context
│   │   └── get-related-work.ts    # Find related tickets/discussions
│   ├── resources/                 # MCP resources (optional, v2)
│   └── client.ts                  # HTTP client to Railway backend
```

### Structure Rationale

- **backend/src/api/routes/**: Flat route files, not nested. Each file owns one domain (webhooks, oauth, context). FastAPI router composition keeps things modular without over-abstraction.
- **backend/src/agents/**: Isolated LangGraph concern. The `state.py` defines the TypedDict, `nodes.py` contains pure functions for each graph node, and `gather.py` wires the graph. This separation lets you test nodes independently.
- **backend/src/auth/**: Extracted from api/routes because OAuth token management is a cross-cutting concern used by ingestion, webhooks, and API routes. Tokens need refresh logic that lives outside the request cycle.
- **apps/web/src/app/(dashboard)/**: Route group for auth-gated pages. Everything under `(dashboard)` shares a layout that checks authentication.
- **packages/mcp-server/src/tools/**: One file per MCP tool. Each tool is a self-contained function that calls the remote backend API. Simple, testable, easy to add new tools.

## Architectural Patterns

### Pattern 1: Split Read/Write Data Access

**What:** Frontend reads directly from Supabase (instant, real-time capable). Writes and complex operations go through FastAPI backend.

**When to use:** Always in this architecture. The frontend never calls external APIs directly and never performs business logic writes.

**Trade-offs:**
- Pro: Instant reads without backend round-trip, Supabase real-time subscriptions work natively
- Pro: RLS enforces access control at the database level regardless of caller
- Con: Two data access paths means two places to understand
- Con: Must ensure backend writes are visible to frontend via Supabase (not a separate DB)

**Example:**
```typescript
// Frontend: direct read with real-time updates
const supabase = createClient();

// Initial read (instant, RLS-filtered)
const { data: contextPages } = await supabase
  .from('context_pages')
  .select('*')
  .eq('workspace_id', workspaceId)
  .order('updated_at', { ascending: false });

// Real-time subscription for status changes
supabase
  .channel('context-updates')
  .on('postgres_changes', {
    event: 'UPDATE',
    schema: 'public',
    table: 'context_pages',
    filter: `workspace_id=eq.${workspaceId}`,
  }, (payload) => {
    // Update UI when backend finishes generating
    updateContextPage(payload.new);
  })
  .subscribe();
```

```python
# Backend: write operation (triggered by user action)
@router.post("/context/{ticket_id}/generate")
async def generate_context(
    ticket_id: str,
    background_tasks: BackgroundTasks,
    workspace_id: str = Depends(get_workspace_id),
):
    # Mark as generating (frontend sees this via real-time)
    await supabase.table("context_pages").upsert({
        "ticket_id": ticket_id,
        "workspace_id": workspace_id,
        "status": "generating",
    }).execute()

    # Offload actual work
    background_tasks.add_task(run_synthesis_pipeline, ticket_id, workspace_id)
    return {"status": "generating"}
```

### Pattern 2: Verify-Enqueue-ACK Webhook Processing

**What:** Webhook handlers immediately verify the signature, extract minimal data, enqueue background work, and return 200. Never do heavy processing in the webhook handler itself.

**When to use:** All webhook endpoints (Linear, Slack). Both services have tight response time expectations.

**Trade-offs:**
- Pro: Fast acknowledgment prevents webhook retries and timeouts
- Pro: Background processing can retry independently on failure
- Con: Need idempotency handling since webhooks may deliver duplicates
- Con: Debugging is split between handler (receive) and task (process)

**Example:**
```python
@router.post("/webhooks/linear")
async def handle_linear_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    # 1. VERIFY: Check HMAC-SHA256 signature
    body = await request.body()
    signature = request.headers.get("Linear-Signature", "")
    if not verify_linear_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 2. PARSE: Extract event type and minimal data
    payload = json.loads(body)
    action = payload.get("action")
    event_type = payload.get("type")

    # 3. IDEMPOTENCY: Check if already processed
    delivery_id = request.headers.get("Linear-Delivery")
    if delivery_id and await is_already_processed(delivery_id):
        return {"status": "already_processed"}

    # 4. ENQUEUE: Background task for actual processing
    background_tasks.add_task(
        process_linear_event,
        payload=payload,
        delivery_id=delivery_id,
    )

    # 5. ACK: Return immediately
    return {"status": "accepted"}
```

### Pattern 3: LangGraph Gather-Then-Synthesize Pipeline

**What:** LangGraph orchestrates parallel data gathering (fetch ticket details, find related Slack threads, search embeddings). Once all data is gathered, a single Gemini Flash call synthesizes the context page.

**When to use:** Every context page generation. The graph manages the complexity of "what data do we need and in what order" while keeping synthesis as a single, predictable LLM call.

**Trade-offs:**
- Pro: Each gathering node is independently testable and replaceable
- Pro: LangGraph handles conditional logic (e.g., skip Slack if not connected)
- Pro: Single synthesis call is cheaper and more predictable than multi-turn agent
- Con: LangGraph adds a dependency and learning curve
- Con: Sequential gathering nodes add latency (mitigate with parallel execution)

**Example:**
```python
# agents/state.py
from typing import TypedDict, Annotated
from operator import add

class GatherState(TypedDict):
    ticket_id: str
    workspace_id: str
    ticket_data: dict | None
    slack_threads: Annotated[list, add]
    related_tickets: Annotated[list, add]
    embedding_results: Annotated[list, add]
    synthesis_input: str | None
    context_page: str | None
    errors: Annotated[list, add]

# agents/nodes.py
async def fetch_ticket(state: GatherState) -> dict:
    """Fetch full ticket details from Linear via stored data."""
    ticket = await get_linear_ticket(state["ticket_id"], state["workspace_id"])
    return {"ticket_data": ticket}

async def find_slack_context(state: GatherState) -> dict:
    """Find Slack threads related to this ticket."""
    threads = await search_slack_for_ticket(
        state["ticket_data"]["identifier"],
        state["workspace_id"],
    )
    return {"slack_threads": threads}

async def search_embeddings(state: GatherState) -> dict:
    """Vector search for semantically related content."""
    query = f"{state['ticket_data']['title']} {state['ticket_data']['description']}"
    results = await match_embeddings(query, state["workspace_id"])
    return {"embedding_results": results}

async def synthesize(state: GatherState) -> dict:
    """Single Gemini Flash call to generate the context page."""
    prompt = build_synthesis_prompt(
        ticket=state["ticket_data"],
        slack_threads=state["slack_threads"],
        related=state["related_tickets"],
        embeddings=state["embedding_results"],
    )
    content = await call_gemini_flash(prompt)
    return {"context_page": content}

# agents/gather.py
from langgraph.graph import StateGraph, END

graph = StateGraph(GatherState)
graph.add_node("fetch_ticket", fetch_ticket)
graph.add_node("find_slack", find_slack_context)
graph.add_node("search_embeddings", search_embeddings)
graph.add_node("synthesize", synthesize)

graph.set_entry_point("fetch_ticket")
# After fetching ticket, gather Slack and embeddings in parallel
graph.add_edge("fetch_ticket", "find_slack")
graph.add_edge("fetch_ticket", "search_embeddings")
# After both complete, synthesize
graph.add_edge("find_slack", "synthesize")
graph.add_edge("search_embeddings", "synthesize")
graph.add_edge("synthesize", END)

pipeline = graph.compile()
```

### Pattern 4: MCP-as-Thin-Client

**What:** The MCP server runs locally via stdio but acts as a thin HTTP client. All business logic lives on the Railway-hosted FastAPI backend. The MCP server only handles protocol translation (MCP tool calls to HTTP requests) and API key authentication.

**When to use:** Always. The MCP server should never contain business logic or direct database access.

**Trade-offs:**
- Pro: Single source of truth for logic (backend), MCP server is trivially simple
- Pro: No database credentials on developer machines
- Pro: Updates to logic deploy to Railway, no MCP server update needed
- Con: Requires network access (no offline mode)
- Con: Adds latency from local to Railway round-trip

**Example:**
```typescript
// packages/mcp-server/src/tools/get-feature-context.ts
import { z } from "zod";
import { backendClient } from "../client.js";

export const getFeatureContextTool = {
  name: "get_feature_context",
  description: "Get the full context page for a Linear ticket identifier (e.g., ENG-123)",
  inputSchema: z.object({
    ticket_identifier: z.string().describe("Linear ticket ID like ENG-123"),
  }),
  async handler({ ticket_identifier }: { ticket_identifier: string }) {
    const response = await backendClient.get(
      `/api/mcp/context/${ticket_identifier}`
    );
    return {
      content: [{ type: "text", text: response.data.content }],
    };
  },
};

// packages/mcp-server/src/client.ts
import axios from "axios";

export const backendClient = axios.create({
  baseURL: process.env.CONTEXTOS_API_URL || "https://api.contextos.dev",
  headers: {
    Authorization: `Bearer ${process.env.CONTEXTOS_API_KEY}`,
  },
  timeout: 30000,
});
```

### Pattern 5: Workspace-Scoped RLS Multi-Tenancy

**What:** Every data table has a `workspace_id` column. Row Level Security policies ensure queries only return data for workspaces the authenticated user belongs to. The backend uses a service-role key for operations that cross workspace boundaries (webhook processing from external sources).

**When to use:** All database access, no exceptions. Even backend code should be workspace-aware.

**Trade-offs:**
- Pro: Security enforcement at database level -- impossible to accidentally leak cross-tenant data
- Pro: No application-level permission checks needed for reads
- Con: Service-role key bypasses RLS (needed for webhooks), so those code paths need extra care
- Con: RLS policies add query overhead (minimal for simple workspace_id checks)

## Data Flow

### Context Generation Flow (Primary)

```
User clicks "Generate"
    │
    ▼
Next.js ──POST──► FastAPI /context/{ticket_id}/generate
                      │
                      ├── Upsert context_pages (status: "generating")
                      │       └──► Supabase Realtime ──► Frontend updates UI
                      │
                      └── BackgroundTask ──► LangGraph Pipeline
                                                │
                                    ┌───────────┼───────────┐
                                    ▼           ▼           ▼
                              fetch_ticket  find_slack  search_embeddings
                                    │           │           │
                                    └───────────┼───────────┘
                                                ▼
                                          synthesize (Gemini Flash)
                                                │
                                                ▼
                                    Write context_pages (status: "ready")
                                          │
                                          └──► Supabase Realtime ──► Frontend shows result
                                          └──► Post to Linear as comment
```

### Webhook Ingestion Flow

```
Linear/Slack event
    │
    ▼
FastAPI webhook handler
    │
    ├── Verify signature (HMAC-SHA256 / Slack signing)
    ├── Check idempotency (delivery ID)
    ├── Return 200 immediately
    │
    └── BackgroundTask
            │
            ├── Normalize payload → Upsert to source table
            ├── Generate embedding → Upsert to embeddings table
            │
            └── If ticket assignment detected:
                    └── Trigger context generation pipeline
```

### OAuth Flow

```
User clicks "Connect Linear"
    │
    ▼
Frontend ──► FastAPI /oauth/linear/start
                │
                └── Return redirect URL (with state param)
                        │
                        ▼
                  User authorizes on Linear
                        │
                        ▼
              Linear callback ──► FastAPI /oauth/linear/callback
                                      │
                                      ├── Exchange code for tokens
                                      ├── Store in Supabase Vault
                                      ├── Trigger initial data sync (BackgroundTask)
                                      │
                                      └── Redirect user back to integrations page
```

### MCP Tool Call Flow

```
Developer in Cursor/Claude Code
    │
    ├── "get_feature_context ENG-123"
    │
    ▼
MCP Client (IDE) ──stdio──► MCP Server (local process)
                                │
                                └──HTTP──► FastAPI /api/mcp/context/ENG-123
                                              │
                                              ├── Validate API key
                                              ├── Look up workspace from API key
                                              ├── Fetch context page from DB
                                              │
                                              └──► Return markdown content
                                                      │
                                ┌───────────────────────┘
                                ▼
                          MCP Server ──stdio──► IDE renders context
```

### State Management

| State | Where | How Updated | How Read |
|-------|-------|-------------|----------|
| User session | Supabase Auth (JWT) | Login/signup flows | `@supabase/ssr` middleware in Next.js |
| Context page status | `context_pages.status` column | Backend writes (draft/generating/ready/stale) | Frontend via Supabase Realtime subscription |
| OAuth tokens | `oauth_tokens` table (Vault-encrypted) | OAuth callback, refresh logic | Backend only (service-role key) |
| Workspace membership | `workspace_members` table | Admin actions | RLS policies reference this for all queries |
| Webhook delivery tracking | Idempotency store (Redis or DB table) | On webhook receipt | Before processing to skip duplicates |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 users (dogfooding) | Current architecture: FastAPI BackgroundTasks, no queue. Supabase free/pro tier. Single Railway instance. This is where ContextOS starts. |
| 10-100 users | Add Redis-backed task queue (switch BackgroundTasks to Celery/ARQ). Rate limit external API calls. Add connection pooling (pgBouncer on Supabase). Monitor embedding storage growth. |
| 100-1000 users | Dedicated worker processes for synthesis (separate from API). Batch embedding generation. Consider IVFFlat index if HNSW memory grows. Add CDN for frontend. |
| 1000+ users | Horizontal API scaling. Event-driven architecture (message bus). Dedicated vector DB if pgvector hits limits. Per-workspace queue isolation. |

### Scaling Priorities

1. **First bottleneck -- LLM API rate limits:** Gemini Flash has generous rate limits but synthesis takes seconds. At 100+ concurrent users generating context, you need queue-based throttling with configurable concurrency. Mitigation: switch BackgroundTasks to a proper queue with max_workers.

2. **Second bottleneck -- Webhook processing volume:** Active Slack workspaces generate hundreds of messages per hour. Embedding generation for each message adds up. Mitigation: batch embedding calls, skip messages below relevance threshold (e.g., under 20 characters, bot messages).

3. **Third bottleneck -- pgvector index memory:** HNSW indexes are memory-resident. With 100K+ embeddings, memory usage grows. Mitigation: monitor `pg_total_relation_size` for the embeddings table, consider switching to IVFFlat or partitioning by workspace.

## Anti-Patterns

### Anti-Pattern 1: Processing Webhooks Synchronously

**What people do:** Perform database writes, embedding generation, and context regeneration inside the webhook handler before returning a response.
**Why it is wrong:** Linear expects a response within seconds. Slack has a 3-second acknowledgment window. Timeout means Slack retries, causing duplicate processing and potential webhook disabling.
**Do this instead:** Verify signature, extract delivery ID, return 200, then process in a BackgroundTask. Use delivery ID for idempotency.

### Anti-Pattern 2: Frontend Calling External APIs Directly

**What people do:** Have Next.js call Linear API or Slack API directly from the browser or server-side routes.
**Why it is wrong:** Exposes API tokens to the client. Creates two codepaths for the same integration. Bypasses the webhook/ingestion pipeline. Makes token refresh logic distributed.
**Do this instead:** All external API calls go through FastAPI. Frontend reads cached/synced data from Supabase. Frontend triggers backend actions via FastAPI endpoints.

### Anti-Pattern 3: Storing Tokens in Application Config

**What people do:** Put OAuth access/refresh tokens in environment variables or config files.
**Why it is wrong:** Tokens are per-workspace, per-user, per-provider. They expire and need refresh. Environment variables are static and shared across requests.
**Do this instead:** Store in Supabase `oauth_tokens` table. Use Supabase Vault for encryption at rest. Backend service refreshes tokens proactively before expiry.

### Anti-Pattern 4: Using LangGraph as a Multi-Turn Agent

**What people do:** Let LangGraph make multiple LLM calls with tool use to iteratively search and gather data, like a ReAct agent.
**Why it is wrong:** Unpredictable cost and latency. A single context page generation could make 5-15 LLM calls. At scale, this is expensive and slow. The data sources are known and finite -- no need for agent autonomy.
**Do this instead:** Use LangGraph as a deterministic pipeline with defined nodes. Each node does one thing (fetch ticket, search Slack, query embeddings). The only LLM call is the final synthesis step.

### Anti-Pattern 5: Polling for Context Page Status

**What people do:** Set up a `setInterval` in the frontend to poll the backend for context page generation status.
**Why it is wrong:** Wasteful network traffic. Delayed updates (depends on polling interval). Does not scale with many concurrent users.
**Do this instead:** Use Supabase Realtime subscriptions. Subscribe to `postgres_changes` on the `context_pages` table filtered by workspace. Updates arrive instantly when the backend writes to the database.

## Integration Points

### External Services

| Service | Integration Pattern | Key Considerations |
|---------|--------------------|--------------------|
| **Linear** | OAuth2 + REST API + Webhooks | HMAC-SHA256 signature verification. Webhook payload includes `action` (create/update/remove) and `type` (Issue, Comment, etc.). Initial sync pulls active issues. |
| **Slack** | OAuth2 V2 + Events API + Web API | Signing secret verification (v0=sha256 HMAC). URL verification challenge on setup. Bot token for reading, user token optional. Event subscriptions for message.channels and message.groups. |
| **Gemini Flash** | REST API (google-generativeai SDK) | Model: gemini-2.0-flash. Structured output via response_schema. Token limits per request. Rate limits per minute. |
| **Supabase Auth** | JWT + @supabase/ssr | Magic links + email/password. JWT claims include user ID. RLS policies reference `auth.uid()`. |
| **Supabase Vault** | SQL functions via service-role | `vault.create_secret()` and `vault.get_secret()`. Only accessible via service-role key (not anon key). |
| **Embedding Model** | TBD (Dulat decides) | Must produce 1536-dimension vectors (matches schema). Options: OpenAI text-embedding-3-small, Gemini text-embedding-004, Voyage AI. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Frontend to Backend | HTTP REST (fetch/axios) | Backend URL from env var. Auth via Supabase JWT forwarded as Bearer token. |
| Frontend to Supabase | Direct client SDK | Read-only for data. Auth flows. Real-time subscriptions. RLS enforces access. |
| Backend to Supabase | Service-role client (supabase-py) | Full access, bypasses RLS. Used for webhook processing and background tasks where user context is not available. |
| MCP Server to Backend | HTTP REST (axios) | API key in Authorization header. Backend maps API key to workspace. No Supabase direct access. |
| LangGraph to Synthesis | Function call within same process | No network boundary. Synthesis module is imported and called by the final graph node. |
| Backend to External APIs | HTTP REST via official SDKs | Linear SDK (linearb/sdk), Slack SDK (slack_sdk). OAuth tokens fetched from DB per request. |

## Build Order (Dependency Chain)

The components have clear dependencies that dictate implementation order:

```
Phase 1: Foundation (no external dependencies)
├── Database schema (already done: 00001_initial_schema.sql)
├── Supabase Auth setup
├── FastAPI app skeleton with health endpoint
└── Next.js shell with auth flow

Phase 2: Data Pipeline (depends on Phase 1)
├── OAuth flows for Linear (needs FastAPI + token storage)
├── Linear initial sync (needs OAuth + ingestion layer)
├── Linear webhook handler (needs FastAPI + ingestion)
├── Embedding generation service (needs DB + embedding model choice)
└── Vector search (needs embeddings in DB)

Phase 3: Core Feature (depends on Phase 2)
├── LangGraph gather pipeline (needs ingestion data + embeddings)
├── Gemini Flash synthesis (needs gathered data)
├── Context page generation endpoint (needs pipeline + synthesis)
└── Auto-trigger on ticket assignment (needs webhook + pipeline)

Phase 4: User Interface (depends on Phase 3)
├── Context pages feed (needs context_pages in DB)
├── Context page detail view (needs generated content)
├── Realtime status updates (needs Supabase Realtime)
└── Integration setup page (needs OAuth flows working)

Phase 5: IDE Integration (depends on Phase 3)
├── MCP server tools (needs backend API endpoints)
├── API key generation (needs auth + settings)
└── MCP authentication (needs API key validation)

Phase 6: Slack + Polish (can partially parallel with Phase 4-5)
├── Slack OAuth + Events API (needs OAuth framework from Phase 2)
├── Slack message ingestion + embedding (needs ingestion + embedding services)
├── Slack-to-ticket linking (needs both Linear and Slack data)
└── Linear comment posting (needs context pages + Linear API)
```

**Rationale:** Linear before Slack because Linear is the primary data source (tickets are the unit of work). Context generation before UI because you need real data to build meaningful UI. MCP after context generation because the MCP tools surface generated content.

## Sources

- [LangGraph Architecture Patterns](https://latenode.com/blog/ai-frameworks-technical-infrastructure/langgraph-multi-agent-orchestration/langgraph-ai-framework-2025-complete-architecture-guide-multi-agent-orchestration-analysis) - MEDIUM confidence (blog, but consistent with official docs)
- [FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/) - HIGH confidence (official docs)
- [FastAPI BackgroundTasks vs Celery](https://medium.com/@komalbaparmar007/fastapi-background-tasks-vs-celery-vs-arq-picking-the-right-asynchronous-workhorse-b6e0478ecf4a) - MEDIUM confidence (verified against official docs)
- [pgvector Supabase Docs](https://supabase.com/docs/guides/database/extensions/pgvector) - HIGH confidence (official)
- [Supabase AI & Vectors](https://supabase.com/docs/guides/ai) - HIGH confidence (official)
- [MCP Specification 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25) - HIGH confidence (official spec)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) - HIGH confidence (official repo)
- [MCP Transport Deprecation (SSE to Streamable HTTP)](https://auth0.com/blog/mcp-streamable-http/) - MEDIUM confidence (Auth0 blog, verified against spec)
- [Linear Webhooks Developer Docs](https://linear.app/developers/webhooks) - HIGH confidence (official)
- [Slack Events API](https://api.slack.com/events-api) - HIGH confidence (official)
- [Supabase Realtime with Next.js](https://supabase.com/docs/guides/realtime/realtime-with-nextjs) - HIGH confidence (official)
- [Webhook Idempotency Patterns](https://www.integrate.io/blog/apply-webhook-best-practices/) - MEDIUM confidence (multiple sources agree)
- [MCP Authentication Stack Overflow](https://stackoverflow.blog/2026/01/21/is-that-allowed-authentication-and-authorization-in-model-context-protocol) - MEDIUM confidence
- [Linear MCP Server](https://linear.app/docs/mcp) - HIGH confidence (official, reference for MCP patterns)

---
*Architecture research for: AI-powered developer context synthesis platform*
*Researched: 2026-02-24*
