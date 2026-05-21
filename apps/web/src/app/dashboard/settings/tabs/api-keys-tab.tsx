'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Key, Copy, Check, Loader2, Terminal } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import {
  listApiKeys,
  createApiKey,
  revokeApiKey,
  type ApiKeyResponse,
  type ApiKeyCreatedResponse,
} from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'

export function ApiKeysTab() {
  const [apiKeys, setApiKeys] = useState<ApiKeyResponse[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [newKeyName, setNewKeyName] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  const [createdKey, setCreatedKey] = useState<ApiKeyCreatedResponse | null>(null)
  const [copied, setCopied] = useState(false)
  const copyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchKeys = useCallback(async () => {
    try {
      const resp = await listApiKeys()
      setApiKeys(resp.keys)
    } catch {
      toast.error('Failed to load API keys')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { fetchKeys() }, [fetchKeys])
  useEffect(() => () => { if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current) }, [])

  const handleCreate = async () => {
    if (!newKeyName.trim()) return
    setIsCreating(true)
    try {
      const created = await createApiKey(newKeyName.trim())
      setCreatedKey(created)
      setNewKeyName('')
      await fetchKeys()
      toast.success('API key created')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create key')
    } finally {
      setIsCreating(false)
    }
  }

  const handleCopy = async () => {
    if (!createdKey) return
    try {
      await navigator.clipboard.writeText(createdKey.key)
      setCopied(true)
      if (copyTimeoutRef.current) clearTimeout(copyTimeoutRef.current)
      copyTimeoutRef.current = setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error('Failed to copy to clipboard')
    }
  }

  const handleRevoke = async (keyId: string) => {
    try {
      await revokeApiKey(keyId)
      await fetchKeys()
      toast.success('API key revoked')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to revoke key')
    }
  }

  if (isLoading) return (
    <div className="space-y-3">
      <Skeleton className="h-9 w-full max-w-md" />
      <Skeleton className="h-16 w-full rounded-xl" />
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <Input
          value={newKeyName}
          onChange={(e) => setNewKeyName(e.target.value)}
          placeholder="Key name, e.g. MCP Server"
          className="dashboard-input max-w-sm"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && newKeyName.trim() && !isCreating) handleCreate()
          }}
        />
        <Button onClick={handleCreate} disabled={!newKeyName.trim() || isCreating} size="sm">
          {isCreating && <Loader2 className="h-4 w-4 animate-spin" />}
          Create key
        </Button>
      </div>

      {createdKey && (
        <div className="dashboard-panel p-4 space-y-3 animate-scale-in">
          <div className="flex items-start gap-2">
            <Key className="h-4 w-4 mt-0.5 text-primary shrink-0" />
            <p className="font-mono text-sm break-all flex-1 text-foreground">
              {createdKey.key}
            </p>
            <Button variant="ghost" size="icon-xs" onClick={handleCopy} className="shrink-0">
              {copied ? (
                <Check className="h-3.5 w-3.5 text-primary" />
              ) : (
                <Copy className="h-3.5 w-3.5" />
              )}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Copy this key now — you won&apos;t be able to see it again.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setCreatedKey(null)
              setCopied(false)
            }}
          >
            Done
          </Button>
        </div>
      )}

      {apiKeys.length === 0 ? (
        <div className="dashboard-panel p-8 text-center">
          <div className="mx-auto w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-3">
            <Terminal className="h-5 w-5 text-muted-foreground" />
          </div>
          <p className="text-sm font-medium text-foreground mb-1">No API keys yet</p>
          <p className="text-xs text-muted-foreground max-w-xs mx-auto">
            API keys let external tools like the ContextOS MCP server access your workspace data.
            Create one above to get started.
          </p>
        </div>
      ) : (
        <div className="dashboard-panel overflow-hidden divide-y divide-border">
          {apiKeys.map((apiKey) => (
            <div key={apiKey.id} className="flex items-center gap-3 px-4 py-3">
              <span className="font-medium text-sm">{apiKey.name}</span>
              <span className="font-mono text-sm text-muted-foreground">
                {apiKey.key_prefix}...
              </span>
              <span className="text-xs text-muted-foreground ml-auto mr-2">
                {formatRelativeTime(apiKey.created_at)}
              </span>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                  >
                    Revoke
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>
                      Revoke &lsquo;{apiKey.name}&rsquo;?
                    </AlertDialogTitle>
                    <AlertDialogDescription>
                      This key will stop working immediately. This cannot be undone.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => handleRevoke(apiKey.id)}
                      className="bg-destructive text-white hover:bg-destructive/90"
                    >
                      Revoke
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
