import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerTicketResource } from "./ticket.js";
import { registerSprintResource } from "./sprint.js";

/**
 * Registers all ContextOS MCP resources with the server.
 */
export function registerResources(server: McpServer): void {
  registerTicketResource(server);
  registerSprintResource(server);
}
