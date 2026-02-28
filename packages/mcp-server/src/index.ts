#!/usr/bin/env node
/**
 * ContextOS MCP Server
 *
 * Provides dev ticket context to AI coding assistants via the Model Context Protocol.
 * Acts as a thin HTTP client calling the ContextOS backend API.
 *
 * Tools:
 * - get_feature_context: Full context page for a ticket
 * - search_context: Semantic search across all content
 * - get_related_work: Related PRs, Slack threads, meetings for a ticket
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const API_BASE_URL = process.env.CONTEXTOS_API_URL || "http://localhost:8000";
const API_KEY = process.env.CONTEXTOS_API_KEY || "";

async function apiRequest(
  path: string,
  params?: Record<string, string>
): Promise<unknown> {
  const url = new URL(path, API_BASE_URL);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, value);
      }
    }
  }

  const response = await fetch(url.toString(), {
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`API request failed (${response.status}): ${body}`);
  }

  return response.json();
}

// Create server
const server = new McpServer({
  name: "contextos",
  version: "0.1.0",
});

// Tool: get_feature_context
server.tool(
  "get_feature_context",
  "Get the full context page for a Linear ticket. Returns a synthesized summary of all related information including background, decisions, requirements, related work, and open questions.",
  {
    ticket_identifier: z
      .string()
      .describe(
        'The Linear ticket identifier (e.g., "CON-16", "ENG-42")'
      ),
  },
  async ({ ticket_identifier }) => {
    try {
      const data = await apiRequest(
        `/api/context/${encodeURIComponent(ticket_identifier)}`
      );
      const page = data as Record<string, unknown>;

      return {
        content: [
          {
            type: "text" as const,
            text: [
              `# ${page.title || ticket_identifier}`,
              "",
              page.content || "No context page available. Trigger generation first.",
              "",
              `---`,
              `**Status:** ${page.status || "unknown"}`,
              `**Generated:** ${page.generated_at || "never"}`,
              `**Model:** ${page.generation_model || "unknown"}`,
              `**Tokens used:** ${page.generation_tokens_used || 0}`,
            ].join("\n"),
          },
        ],
      };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown error";
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to get context for ${ticket_identifier}: ${message}\n\nYou may need to trigger generation first with the backend API.`,
          },
        ],
        isError: true,
      };
    }
  }
);

// Tool: search_context
server.tool(
  "search_context",
  "Search across all workspace content (tickets, PRs, Slack messages, meetings) using semantic similarity. Returns ranked results with relevance scores.",
  {
    query: z
      .string()
      .describe("Natural language search query"),
    source_type: z
      .string()
      .optional()
      .describe(
        "Optional filter by source type: linear_ticket, slack_message, github_pull_request, meeting_transcript, etc."
      ),
    limit: z
      .number()
      .optional()
      .default(10)
      .describe("Maximum number of results (1-50, default 10)"),
  },
  async ({ query, source_type, limit }) => {
    try {
      const params: Record<string, string> = {
        q: query,
        limit: String(limit || 10),
      };
      if (source_type) {
        params.source_type = source_type;
      }

      const data = await apiRequest("/api/context/", params);
      const response = data as {
        query: string;
        results: Array<{
          source_type: string;
          source_id: string;
          similarity: number;
          metadata?: Record<string, unknown>;
        }>;
        count: number;
      };

      if (response.count === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: `No results found for: "${query}"`,
            },
          ],
        };
      }

      const lines = [`## Search Results for: "${query}"\n`];
      for (const result of response.results) {
        lines.push(
          `- **[${result.source_type}]** ${result.source_id} (similarity: ${result.similarity})`
        );
      }
      lines.push(`\n_${response.count} results found_`);

      return {
        content: [
          {
            type: "text" as const,
            text: lines.join("\n"),
          },
        ],
      };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown error";
      return {
        content: [
          {
            type: "text" as const,
            text: `Search failed: ${message}`,
          },
        ],
        isError: true,
      };
    }
  }
);

// Tool: get_related_work
server.tool(
  "get_related_work",
  "Get related work items for a Linear ticket — PRs, Slack threads, meeting discussions, and other linked content. Useful for understanding the broader context around a feature or bug.",
  {
    ticket_identifier: z
      .string()
      .describe(
        'The Linear ticket identifier (e.g., "CON-16", "ENG-42")'
      ),
  },
  async ({ ticket_identifier }) => {
    try {
      const data = await apiRequest(
        `/api/context/${encodeURIComponent(ticket_identifier)}`
      );
      const page = data as {
        sources: Array<{
          type: string;
          id: string;
          title: string;
          relevance_score: number;
        }>;
        title?: string;
      };

      const sources = page.sources || [];
      if (sources.length === 0) {
        return {
          content: [
            {
              type: "text" as const,
              text: `No related work found for ${ticket_identifier}. The context page may not have been generated yet.`,
            },
          ],
        };
      }

      const lines = [
        `## Related Work for ${ticket_identifier}\n`,
      ];

      // Group by source type
      const grouped: Record<string, typeof sources> = {};
      for (const source of sources) {
        const key = source.type || "other";
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(source);
      }

      for (const [type, items] of Object.entries(grouped)) {
        lines.push(`### ${type.replace(/_/g, " ").toUpperCase()}`);
        for (const item of items) {
          lines.push(
            `- **${item.title}** (relevance: ${item.relevance_score})`
          );
        }
        lines.push("");
      }

      return {
        content: [
          {
            type: "text" as const,
            text: lines.join("\n"),
          },
        ],
      };
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unknown error";
      return {
        content: [
          {
            type: "text" as const,
            text: `Failed to get related work for ${ticket_identifier}: ${message}`,
          },
        ],
        isError: true,
      };
    }
  }
);

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("ContextOS MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
