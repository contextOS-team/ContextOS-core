import type { SuggestionItem } from './api'

const REVIEW_ACTION = 'Review'

export interface SuggestionAction {
  href: string
  label: string
}

export function suggestionAction(suggestion: SuggestionItem): SuggestionAction | null {
  if (suggestion.type === 'missing_source_coverage') {
    if (suggestion.entity_type === 'graph_node' && suggestion.entity_id) {
      return {
        href: `/dashboard/decisions/${encodeURIComponent(suggestion.entity_id)}`,
        label: REVIEW_ACTION,
      }
    }

    return null
  }

  if (!suggestion.action_href) {
    return null
  }

  return {
    href: suggestion.action_href,
    label: suggestion.primary_action ?? REVIEW_ACTION,
  }
}
