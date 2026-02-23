import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

/**
 * Registers the "search_context" tool.
 *
 * Performs semantic search across all connected sources — Slack, Notion,
 * Linear, and meeting transcripts — for relevant context.
 */
export function registerSearchContext(server: McpServer): void {
  server.tool(
    "search_context",
    "Search across all connected sources (Slack, Notion, Linear, meetings) for relevant context",
    {
      query: z.string().describe("Natural language search query"),
      sourceTypes: z
        .array(z.string())
        .optional()
        .describe(
          'Optional filter for source types, e.g. ["slack", "notion", "linear", "meetings"]'
        ),
      limit: z
        .number()
        .int()
        .min(1)
        .max(50)
        .optional()
        .describe("Maximum number of results to return (default: 10)"),
    },
    async ({ query, sourceTypes, limit }) => {
      const effectiveLimit = limit ?? 10;

      // TODO: Replace with real semantic search across connected sources
      const mockResults = {
        query,
        sourceTypes: sourceTypes ?? ["all"],
        limit: effectiveLimit,
        results: [
          {
            source: "slack",
            channel: "#eng-general",
            content: `[Mock] Found relevant Slack message matching "${query}"`,
            relevanceScore: 0.92,
            timestamp: "2025-01-15T10:30:00Z",
          },
          {
            source: "notion",
            title: "Technical Design Doc",
            content: `[Mock] Found relevant Notion page matching "${query}"`,
            relevanceScore: 0.87,
            lastEdited: "2025-01-14T16:00:00Z",
          },
          {
            source: "linear",
            ticketId: "ENG-456",
            title: "Related ticket",
            content: `[Mock] Found related Linear ticket matching "${query}"`,
            relevanceScore: 0.81,
          },
          {
            source: "meetings",
            title: "Sprint Planning — Jan 13",
            content: `[Mock] Found relevant meeting transcript matching "${query}"`,
            relevanceScore: 0.76,
            date: "2025-01-13T09:00:00Z",
          },
        ].slice(0, effectiveLimit),
      };

      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(mockResults, null, 2),
          },
        ],
      };
    }
  );
}
