#!/usr/bin/env node
/**
 * ContextOS MCP Server — Decision Context for AI coding agents.
 *
 * An agent-neutral surface (Claude Code, Cursor, Codex, …): before acting, an
 * agent can ask what the organization has actually decided. Thin stdio client
 * over the read-only Decision Context API (/api/v1), authenticated by a
 * workspace-scoped API key (cos_…).
 *
 * Tools:
 * - get_current_decisions: active decisions, optionally ranked by relevance
 * - get_decision:          one decision with evidence + supersession chain
 * - get_constraints:       decisions most relevant to a proposed action
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const API_BASE_URL = process.env.CONTEXTOS_API_URL || "http://localhost:8000";
const API_KEY = process.env.CONTEXTOS_API_KEY || "";

interface DecisionData {
  id: string;
  statement: string;
  rationale: string | null;
  status: string;
  valid_from: string | null;
  valid_until: string | null;
  confidence: number | null;
  consequentiality_score: number | null;
  verification: string;
  evidence_count?: number;
  evidence?: Array<{
    source_type: string;
    source_id: string;
    quote: string;
    source_link: string | null;
    captured_at: string | null;
  }>;
  relations?: Array<{
    from_decision: string;
    to_decision: string;
    edge_type: string;
  }>;
}

interface Envelope<T> {
  schema_version: string;
  data: T;
}

async function apiRequest<T>(
  path: string,
  params?: Record<string, string>
): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    }
  }
  return httpJson<T>(url.toString(), { method: "GET" });
}

async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return httpJson<T>(new URL(path, API_BASE_URL).toString(), {
    method: "POST",
    body: JSON.stringify(body),
  });
}

async function httpJson<T>(url: string, init: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
  });
  if (!response.ok) {
    const bodyText = await response.text();
    if (response.status === 401) {
      throw new Error(
        "Unauthorized — set CONTEXTOS_API_KEY to a valid workspace API key (cos_…)."
      );
    }
    throw new Error(`API request failed (${response.status}): ${bodyText}`);
  }
  return (await response.json()) as T;
}

function formatDecision(d: DecisionData): string {
  const lines = [
    `### ${d.statement}`,
    `- status: **${d.status}** · verification: ${d.verification}`,
  ];
  if (d.rationale) lines.push(`- rationale: ${d.rationale}`);
  if (d.consequentiality_score != null) {
    lines.push(`- consequentiality: ${d.consequentiality_score.toFixed(2)}`);
  }
  if (d.valid_from) lines.push(`- decided: ${d.valid_from}`);
  if (d.evidence_count != null) lines.push(`- evidence: ${d.evidence_count} source(s)`);
  lines.push(`- id: ${d.id}`);
  return lines.join("\n");
}

const server = new McpServer({ name: "contextos", version: "0.1.0" });

server.tool(
  "get_current_decisions",
  "List the engineering organization's currently active decisions. Optionally pass a query to rank by relevance. Use this before starting work to understand what has already been decided.",
  {
    query: z
      .string()
      .optional()
      .describe("Optional topic to rank decisions by relevance"),
    limit: z.number().optional().default(25).describe("Max decisions (1-200)"),
  },
  async ({ query, limit }) => {
    try {
      const params: Record<string, string> = { limit: String(limit || 25) };
      if (query) params.query = query;
      const { data } = await apiRequest<
        Envelope<{ decisions: DecisionData[]; count: number }>
      >("/api/v1/decisions", params);
      if (data.count === 0) {
        return {
          content: [{ type: "text" as const, text: "No active decisions found." }],
        };
      }
      const text = [
        `## ${data.count} active decision(s)`,
        "",
        ...data.decisions.map(formatDecision),
      ].join("\n\n");
      return { content: [{ type: "text" as const, text }] };
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to fetch decisions: ${
              error instanceof Error ? error.message : "unknown error"
            }`,
          },
        ],
        isError: true,
      };
    }
  }
);

server.tool(
  "get_decision",
  "Get one decision in full: its evidence (exact source quotes) and any supersession/contradiction relationships to other decisions.",
  {
    decision_id: z.string().describe("The decision id (uuid)"),
  },
  async ({ decision_id }) => {
    try {
      const { data } = await apiRequest<Envelope<DecisionData>>(
        `/api/v1/decisions/${encodeURIComponent(decision_id)}`
      );
      const lines = [formatDecision(data)];
      if (data.evidence?.length) {
        lines.push("", "**Evidence:**");
        for (const e of data.evidence) {
          lines.push(
            `- [${e.source_type}] “${e.quote}”${
              e.source_link ? ` (${e.source_link})` : ""
            }`
          );
        }
      }
      if (data.relations?.length) {
        lines.push("", "**Relationships:**");
        for (const r of data.relations) {
          lines.push(`- ${r.edge_type}: ${r.from_decision} → ${r.to_decision}`);
        }
      }
      return { content: [{ type: "text" as const, text: lines.join("\n") }] };
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to fetch decision: ${
              error instanceof Error ? error.message : "unknown error"
            }`,
          },
        ],
        isError: true,
      };
    }
  }
);

server.tool(
  "get_constraints",
  "Given a proposed action (e.g. 'add MongoDB support', 'change the auth flow'), return the active decisions most relevant to it — the constraints to weigh before proceeding. Advisory only; not a verdict.",
  {
    action: z.string().describe("The proposed action, in plain language"),
    limit: z.number().optional().default(10).describe("Max constraints (1-50)"),
  },
  async ({ action, limit }) => {
    try {
      const { data } = await apiRequest<
        Envelope<{ action: string; constraints: DecisionData[]; count: number }>
      >("/api/v1/constraints", { action, limit: String(limit || 10) });
      if (data.count === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: `No active decisions appear relevant to: "${action}". No known conflict — but ContextOS may not have complete coverage.`,
            },
          ],
        };
      }
      const text = [
        `## ${data.count} relevant decision(s) for: "${action}"`,
        "Review these before proceeding — they may constrain this action.",
        "",
        ...data.constraints.map(formatDecision),
      ].join("\n\n");
      return { content: [{ type: "text" as const, text }] };
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to fetch constraints: ${
              error instanceof Error ? error.message : "unknown error"
            }`,
          },
        ],
        isError: true,
      };
    }
  }
);

server.tool(
  "check_action",
  "Advisory Decision Guard: given a proposed action, get whether it conflicts with active decisions — no_known_conflict / potential_conflict / requires_review — plus the decisions that drove the verdict. Advisory only; never blocks, never 'allowed'. Call this before making a change that might contradict an existing decision.",
  {
    proposed_action: z
      .string()
      .describe("The action about to be taken, in plain language"),
  },
  async ({ proposed_action }) => {
    try {
      const { data } = await apiPost<
        Envelope<{
          status: string;
          rationale: string;
          confidence: number;
          decisions: Array<{ statement: string; has_exception?: boolean }>;
        }>
      >("/api/v1/check_action", { proposed_action });
      const lines = [
        `## Guard: **${data.status}** (confidence ${data.confidence.toFixed(2)})`,
        data.rationale,
      ];
      if (data.decisions.length) {
        lines.push("", "Decisions considered:");
        for (const d of data.decisions) {
          lines.push(`- ${d.statement}${d.has_exception ? " (has exception)" : ""}`);
        }
      }
      return { content: [{ type: "text" as const, text: lines.join("\n") }] };
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `check_action failed: ${
              error instanceof Error ? error.message : "unknown error"
            }`,
          },
        ],
        isError: true,
      };
    }
  }
);

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // eslint-disable-next-line no-console
  console.error("ContextOS Decision Context MCP server running on stdio");
}

main().catch((error) => {
  // eslint-disable-next-line no-console
  console.error("Fatal error:", error);
  process.exit(1);
});
