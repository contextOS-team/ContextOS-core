import {
  createClient,
  getCachedUser,
  getCachedWorkspaceMember,
} from '@/lib/supabase/server'
import { ActivityTimeline } from './activity-timeline'
import { SyncStatus } from './sync-status'

export default async function ActivityPage() {
  const user = await getCachedUser()

  if (!user) {
    return null // Dashboard layout already redirects unauthenticated users
  }

  // Get workspace_id from membership
  const membership = await getCachedWorkspaceMember(user.id)

  if (!membership) {
    return null // No workspace membership
  }

  const supabase = await createClient()

  // Fetch initial 30 events
  const { data: events } = await supabase
    .from('activity_events')
    .select('*')
    .eq('workspace_id', membership.workspace_id)
    .order('created_at', { ascending: false })
    .limit(30)

  // Fetch last sync time per integration
  const { data: syncStatuses } = await supabase
    .from('activity_events')
    .select('metadata, created_at')
    .eq('workspace_id', membership.workspace_id)
    .eq('event_type', 'sync_completed')
    .order('created_at', { ascending: false })

  const latestByIntegration = new Map<string, string>()
  for (const row of syncStatuses ?? []) {
    const integration = (row.metadata as Record<string, unknown>)
      ?.integration as string
    if (integration && !latestByIntegration.has(integration)) {
      latestByIntegration.set(integration, row.created_at)
    }
  }
  const syncStatusList = Array.from(latestByIntegration.entries()).map(
    ([integration, lastSyncedAt]) => ({ integration, lastSyncedAt })
  )

  return (
    <>
      <SyncStatus syncStatuses={syncStatusList} />
      <ActivityTimeline
        initialEvents={events ?? []}
        workspaceId={membership.workspace_id}
      />
    </>
  )
}
