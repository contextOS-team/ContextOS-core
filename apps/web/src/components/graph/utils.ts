import type { GraphNodeData } from './types'

/**
 * Generate an external URL for a graph node based on its entity type and properties.
 * Returns null if no URL can be constructed.
 */
export function getEntityExternalUrl(node: GraphNodeData): string | null {
  const p = node.properties

  // Ticket — Linear format
  if (node.entityType === 'Ticket') {
    const identifier = (p.identifier as string) || node.name
    if (identifier && /^[A-Z]+-\d+$/.test(identifier)) {
      return `https://linear.app/issue/${identifier}`
    }
  }

  // PR — GitHub URL if available in properties
  if (node.entityType === 'PR') {
    if (p.url && typeof p.url === 'string') return p.url
    if (p.html_url && typeof p.html_url === 'string') return p.html_url
  }

  // NotionPage — Notion URL
  if (node.entityType === 'NotionPage') {
    if (p.url && typeof p.url === 'string') return p.url
    if (p.notion_url && typeof p.notion_url === 'string') return p.notion_url
  }

  // SlackThread — Slack deep link
  if (node.entityType === 'SlackThread') {
    if (p.permalink && typeof p.permalink === 'string') return p.permalink
  }

  return null
}
