'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  updateWorkspaceName,
  type WorkspaceResponse,
} from '@/lib/api'

interface GeneralTabProps {
  workspace: WorkspaceResponse
  onUpdate: (ws: WorkspaceResponse) => void
}

export function GeneralTab({ workspace, onUpdate }: GeneralTabProps) {
  const [workspaceName, setWorkspaceName] = useState(workspace.name)
  const [originalName] = useState(workspace.name)
  const [isSaving, setIsSaving] = useState(false)
  const nameChanged = workspaceName.trim() !== originalName && workspaceName.trim().length > 0

  const handleSave = async () => {
    if (!nameChanged) return
    setIsSaving(true)
    try {
      const updated = await updateWorkspaceName(workspaceName.trim())
      onUpdate(updated)
      toast.success('Workspace name updated')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="rounded-xl border bg-card p-6">
      <div className="flex flex-col gap-4 max-w-sm">
        <Label htmlFor="workspace-name" className="text-sm font-medium">
          Workspace name
        </Label>
        <div className="flex gap-2">
          <Input
            id="workspace-name"
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
            placeholder="My workspace"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && nameChanged && !isSaving) handleSave()
            }}
          />
          <Button onClick={handleSave} disabled={!nameChanged || isSaving} size="sm">
            {isSaving && <Loader2 className="h-4 w-4 animate-spin" />}
            Save
          </Button>
        </div>
      </div>
    </div>
  )
}
