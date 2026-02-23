import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

/**
 * Registers the "get_related_work" tool.
 *
 * Finds related Linear tickets, PRs, and discussions for a given ticket
 * or topic. Accepts either a ticketId or a free-text query (or both).
 */
export function registerGetRelatedWork(server: McpServer): void {
  server.tool(
    "get_related_work",
    "Find related Linear tickets, PRs, and discussions for a given ticket or topic",
    {
      ticketId: z
        .string()
        .optional()
        .describe('Linear ticket ID to find related work for, e.g. "ENG-123"'),
      query: z
        .string()
        .optional()
        .describe("Free-text query to find related work by topic"),
    },
    async ({ ticketId, query }) => {
      if (!ticketId && !query) {
        return {
          content: [
            {
              type: "text" as const,
              text: JSON.stringify({
                error:
                  "At least one of ticketId or query must be provided",
              }),
            },
          ],
          isError: true,
        };
      }

      const searchTerm = ticketId ?? query;

      // TODO: Replace with real related-work lookup from Linear, GitHub, Slack
      const mockRelatedWork = {
        ticketId: ticketId ?? null,
        query: query ?? null,
        relatedTickets: [
          {
            ticketId: "ENG-120",
            title: `[Mock] Predecessor ticket related to ${searchTerm}`,
            status: "Done",
            relationship: "blocks",
          },
          {
            ticketId: "ENG-130",
            title: `[Mock] Follow-up ticket related to ${searchTerm}`,
            status: "In Progress",
            relationship: "blocked-by",
          },
        ],
        relatedPRs: [
          {
            number: 42,
            title: `[Mock] PR implementing part of ${searchTerm}`,
            status: "merged",
            repository: "contextos-core",
            url: "https://github.com/org/contextos-core/pull/42",
          },
        ],
        relatedDiscussions: [
          {
            source: "slack",
            channel: "#eng-general",
            preview: `[Mock] Discussion thread about ${searchTerm}`,
            timestamp: "2025-01-15T10:30:00Z",
            messageCount: 8,
          },
        ],
      };

      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(mockRelatedWork, null, 2),
          },
        ],
      };
    }
  );
}
