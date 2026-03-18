import {
  RefreshCw,
  CheckCircle2,
  Sparkles,
  Plug,
  Unplug,
  TicketPlus,
  GitMerge,
  Mic,
  FilePlus,
  MessageSquare,
  type LucideIcon,
} from 'lucide-react'

export type EventType =
  | 'sync_started'
  | 'sync_completed'
  | 'context_generated'
  | 'integration_connected'
  | 'integration_disconnected'
  | 'ticket_created'
  | 'pr_merged'
  | 'meeting_recorded'
  | 'page_created'
  | 'messages_digest'

export interface ActivityEvent {
  id: string
  workspace_id: string
  actor_id: string | null
  event_type: EventType
  metadata: Record<string, unknown>
  created_at: string
}

export const EVENT_ICONS: Record<EventType, LucideIcon> = {
  sync_started: RefreshCw,
  sync_completed: CheckCircle2,
  context_generated: Sparkles,
  integration_connected: Plug,
  integration_disconnected: Unplug,
  ticket_created: TicketPlus,
  pr_merged: GitMerge,
  meeting_recorded: Mic,
  page_created: FilePlus,
  messages_digest: MessageSquare,
}

/** Official brand colors per integration, keyed by metadata.integration value */
export const INTEGRATION_COLORS: Record<string, string> = {
  linear: '#5E6AD2',
  github: '#8b949e',
  gitlab: '#FC6D26',
  jira: '#0052CC',
  notion: '#9CA3AF',
  slack: '#4A154B',
  fathom: '#7C3AED',
  telegram: '#0088CC',
}

/** Structured digest extraction types (mirrors backend Pydantic models) */

export interface DigestDecision {
  title: string
  rationale: string
  participants: string[]
}

export interface DigestActionItem {
  description: string
  assignee: string | null
}

export interface DigestTopic {
  title: string
  ticket_refs: string[]
}

/** Semantic category for visual grouping */
export type EventCategory = 'sync' | 'integration' | 'content' | 'digest'

export function getEventCategory(type: EventType): EventCategory {
  switch (type) {
    case 'sync_started':
    case 'sync_completed':
      return 'sync'
    case 'integration_connected':
    case 'integration_disconnected':
      return 'integration'
    case 'messages_digest':
      return 'digest'
    default:
      return 'content'
  }
}
