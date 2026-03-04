'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { createClient } from '@/lib/supabase/client'
import { toast } from 'sonner'

interface StepWorkspaceProps {
  onNext: (name: string) => void
  defaultName?: string
}

export function StepWorkspace({ onNext, defaultName = '' }: StepWorkspaceProps) {
  const [name, setName] = useState(defaultName)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const trimmed = name.trim()
  const isValid = trimmed.length >= 2 && trimmed.length <= 50

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()

    if (!isValid) {
      setError(
        trimmed.length < 2
          ? 'Workspace name must be at least 2 characters.'
          : 'Workspace name must be 50 characters or fewer.'
      )
      return
    }

    setSaving(true)
    setError(null)

    try {
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) throw new Error('Not authenticated')

      // Get user's workspace via workspace_members
      const { data: membership } = await supabase
        .from('workspace_members')
        .select('workspace_id')
        .eq('user_id', user.id)
        .single()

      if (!membership) throw new Error('No workspace found')

      const { error: updateError } = await supabase
        .from('workspaces')
        .update({ name: trimmed })
        .eq('id', membership.workspace_id)

      if (updateError) throw new Error(updateError.message)

      onNext(trimmed)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save workspace name'
      toast.error(message)
      setError(message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Name your workspace</h2>
        <p className="text-sm text-muted-foreground">
          This is where your team&apos;s context lives.
        </p>
      </div>

      <div className="space-y-2">
        <Input
          value={name}
          onChange={(e) => {
            setName(e.target.value)
            setError(null)
          }}
          placeholder="My Workspace"
          autoFocus
          maxLength={50}
        />
        {error && (
          <p className="text-xs text-destructive">{error}</p>
        )}
      </div>

      <Button
        type="submit"
        className="w-full"
        disabled={saving || !trimmed}
      >
        {saving ? 'Saving...' : 'Continue'}
      </Button>
    </form>
  )
}
