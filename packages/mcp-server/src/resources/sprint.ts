import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";

/**
 * Registers the sprint overview resource.
 *
 * Exposes sprint-level overviews as MCP resources via the URI template:
 * contextos://sprints/{sprintId}
 */
export function registerSprintResource(server: McpServer): void {
  server.resource(
    "sprint-overview",
    new ResourceTemplate("contextos://sprints/{sprintId}", {
      list: undefined,
    }),
    {
      name: "Sprint Overview",
      description: "Overview and context for a sprint's tickets",
      mimeType: "application/json",
    },
    async (uri, { sprintId }) => {
      const id = Array.isArray(sprintId) ? sprintId[0] : sprintId;

      // TODO: Replace with real sprint context from the synthesis engine
      const mockSprintOverview = {
        sprintId: id,
        name: `[Mock] Sprint ${id}`,
        goal: "Deliver core context synthesis pipeline and MCP server integration",
        startDate: "2025-01-13T00:00:00Z",
        endDate: "2025-01-24T00:00:00Z",
        tickets: [
          {
            ticketId: "ENG-120",
            title: "Set up MCP server scaffold",
            status: "Done",
            assignee: "developer@example.com",
          },
          {
            ticketId: "ENG-121",
            title: "Implement Slack connector",
            status: "In Progress",
            assignee: "developer@example.com",
          },
          {
            ticketId: "ENG-122",
            title: "Implement Notion connector",
            status: "To Do",
            assignee: "developer2@example.com",
          },
          {
            ticketId: "ENG-123",
            title: "Context synthesis engine — MVP",
            status: "In Progress",
            assignee: "developer@example.com",
          },
        ],
        summary:
          "This is a placeholder sprint overview. In production, this will contain an aggregated view of all ticket contexts, key discussions, blockers, and progress for the sprint.",
        lastUpdated: new Date().toISOString(),
      };

      return {
        contents: [
          {
            uri: uri.href,
            mimeType: "application/json",
            text: JSON.stringify(mockSprintOverview, null, 2),
          },
        ],
      };
    }
  );
}
