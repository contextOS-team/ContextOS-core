# ContextOS MCP Server

Agent-neutral **Decision Context** over the Model Context Protocol. Any
MCP-speaking coding agent (Claude Code, Cursor, Codex, …) can ask what your
engineering organization has already decided before it acts.

Thin stdio client over the read-only Decision Context API (`/api/v1`),
authenticated by a workspace-scoped API key.

## Tools

| Tool | Purpose |
|---|---|
| `get_current_decisions` | Active decisions, optionally ranked by a query |
| `get_decision` | One decision with evidence quotes + supersession chain |
| `get_constraints` | Decisions most relevant to a proposed action |
| `check_action` | Advisory Guard verdict for a proposed action (no_known_conflict / potential_conflict / requires_review) |

## Setup

1. Create a workspace API key in ContextOS (Settings → API keys). It starts with `cos_`.
2. Build:
   ```bash
   cd packages/mcp-server && pnpm install && pnpm build
   ```
3. Register with your agent. Example (Claude Code `mcp` config):
   ```json
   {
     "mcpServers": {
       "contextos": {
         "command": "node",
         "args": ["/absolute/path/to/packages/mcp-server/dist/index.js"],
         "env": {
           "CONTEXTOS_API_URL": "https://api.contextos.pro",
           "CONTEXTOS_API_KEY": "cos_your_key_here"
         }
       }
     }
   }
   ```

## Example agent flow

> Engineer: "Continue the self-hosted implementation."
> Agent calls `get_constraints("self-hosted implementation")` →
> ContextOS returns: *"Self-hosted launch deferred until Q1 (active, reviewed)."*
> Agent surfaces the conflict and asks the human before proceeding.

Read-only and advisory: the agent decides what to do with the context; ContextOS
never blocks.
