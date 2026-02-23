import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { ResourceTemplate } from "@modelcontextprotocol/sdk/server/mcp.js";

/**
 * Registers the ticket context resource.
 *
 * Exposes individual Linear ticket context pages as MCP resources
 * via the URI template: contextos://tickets/{ticketId}
 */
export function registerTicketResource(server: McpServer): void {
  server.resource(
    "ticket-context",
    new ResourceTemplate("contextos://tickets/{ticketId}", {
      list: undefined,
    }),
    {
      name: "Linear Ticket Context",
      description: "Context page for a specific Linear ticket",
      mimeType: "application/json",
    },
    async (uri, { ticketId }) => {
      const id = Array.isArray(ticketId) ? ticketId[0] : ticketId;

      // TODO: Replace with real ticket context from the synthesis engine
      const mockTicketContext = {
        ticketId: id,
        title: `[Mock] Context for ticket ${id}`,
        status: "In Progress",
        assignee: "developer@example.com",
        summary:
          "This is a placeholder ticket context. In production, this will contain the full synthesized context page including related discussions, documents, and decisions.",
        contextSources: {
          slackThreads: 3,
          notionDocs: 2,
          meetingMentions: 1,
          relatedTickets: 4,
        },
        lastUpdated: new Date().toISOString(),
      };

      return {
        contents: [
          {
            uri: uri.href,
            mimeType: "application/json",
            text: JSON.stringify(mockTicketContext, null, 2),
          },
        ],
      };
    }
  );
}
