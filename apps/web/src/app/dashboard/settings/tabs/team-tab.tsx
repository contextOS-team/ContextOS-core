'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Skeleton } from '@/components/ui/skeleton'
import { listTeamMembers, type TeamMember } from '@/lib/api'

function getInitials(name: string): string {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

export function TeamTab() {
  const [members, setMembers] = useState<TeamMember[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    listTeamMembers()
      .then((resp) => setMembers(resp.members))
      .catch(() => toast.error('Failed to load team'))
      .finally(() => setIsLoading(false))
  }, [])

  if (isLoading) {
    return (
      <div className="dashboard-panel overflow-hidden divide-y divide-border">
        {[1, 2].map((i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-3">
            <Skeleton className="h-8 w-8 rounded-full" />
            <div className="space-y-1.5">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-3 w-40" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div>
      <p className="text-xs text-muted-foreground mb-3">
        {members.length} member{members.length !== 1 ? 's' : ''} in this workspace
      </p>
      <div className="dashboard-panel overflow-hidden divide-y divide-border">
        {members.map((member) => {
          const name = member.full_name || member.email
          const initials = getInitials(name)
          return (
            <div key={member.user_id} className="flex items-center gap-3 px-4 py-3">
              <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-semibold shrink-0">
                {initials}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">
                  {member.full_name || member.email}
                </p>
                {member.full_name && (
                  <p className="text-xs text-muted-foreground truncate">{member.email}</p>
                )}
              </div>
              <span
                className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${
                  member.role === 'owner'
                    ? 'bg-primary/10 text-primary'
                    : 'bg-muted text-muted-foreground'
                }`}
              >
                {member.role === 'owner' ? 'Owner' : 'Member'}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
