import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";

/**
 * Registers the "get_feature_context" tool.
 *
 * Retrieves the auto-generated context page for a Linear ticket,
 * including related Slack discussions, Notion docs, and meeting notes.
 */
export function registerGetFeatureContext(server: McpServer): void {
  server.tool(
    "get_feature_context",
    "Get the auto-generated context page for a Linear ticket, including related Slack discussions, Notion docs, and meeting notes",
    {
      ticketId: z.string().describe('Linear ticket ID, e.g. "ENG-123"'),
    },
    async ({ ticketId }) => {
      // TODO: Replace with real context synthesis from connected sources
      const mockContext = {
        ticketId,
        title: `[Mock] Feature context for ${ticketId}`,
        summary:
          "This is a placeholder context page. In production, this will aggregate context from Slack, Notion, Linear, and meeting transcripts.",
        slackThreads: [
          {
            channel: "#eng-general",
            preview: `Discussion about ${ticketId} implementation approach`,
            timestamp: "2025-01-15T10:30:00Z",
            messageCount: 12,
          },
        ],
        notionDocs: [
          {
            title: `${ticketId} — Technical Design Doc`,
            lastEdited: "2025-01-14T16:00:00Z",
            snippet:
              "This document outlines the proposed architecture for...",
          },
        ],
        meetingNotes: [
          {
            title: "Sprint Planning — Jan 13",
            relevantExcerpt: `Discussed priority and scope for ${ticketId}`,
            date: "2025-01-13T09:00:00Z",
          },
        ],
      };

      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(mockContext, null, 2),
          },
        ],
      };
    }
  );
}
