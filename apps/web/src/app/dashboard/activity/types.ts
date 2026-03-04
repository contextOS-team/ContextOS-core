import {
  RefreshCw,
  CheckCircle2,
  Sparkles,
  Plug,
  Unplug,
  UserPlus,
  type LucideIcon,
} from 'lucide-react'

export type EventType =
  | 'sync_started'
  | 'sync_completed'
  | 'context_generated'
  | 'integration_connected'
  | 'integration_disconnected'
  | 'user_signed_up'

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
  user_signed_up: UserPlus,
}
