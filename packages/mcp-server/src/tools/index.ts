import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerGetFeatureContext } from "./get-feature-context.js";
import { registerSearchContext } from "./search-context.js";
import { registerGetRelatedWork } from "./get-related-work.js";

/**
 * Registers all ContextOS MCP tools with the server.
 */
export function registerTools(server: McpServer): void {
  registerGetFeatureContext(server);
  registerSearchContext(server);
  registerGetRelatedWork(server);
}
