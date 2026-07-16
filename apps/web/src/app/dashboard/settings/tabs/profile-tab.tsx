'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { User, Mail, Lock, Shield, Check } from 'lucide-react'

interface ProfileTabProps {
  userEmail: string
  userFullName: string | null
}

export function ProfileTab({ userEmail, userFullName }: ProfileTabProps) {
  const [displayName, setDisplayName] = useState(userFullName ?? '')
  const [isSavingName, setIsSavingName] = useState(false)
  const [nameSaved, setNameSaved] = useState(false)
  const [nameError, setNameError] = useState<string | null>(null)

  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false)
  const [passwordSaved, setPasswordSaved] = useState(false)
  const [passwordError, setPasswordError] = useState<string | null>(null)

  async function handleSaveDisplayName() {
    setIsSavingName(true)
    setNameError(null)
    setNameSaved(false)
    try {
      const supabase = createClient()
      const { error } = await supabase.auth.updateUser({
        data: { full_name: displayName.trim() },
      })
      if (error) throw error
      setNameSaved(true)
      setTimeout(() => setNameSaved(false), 3000)
    } catch (err) {
      setNameError(err instanceof Error ? err.message : 'Failed to update name')
    } finally {
      setIsSavingName(false)
    }
  }

  async function handleSetPassword(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPasswordError(null)
    setPasswordSaved(false)

    if (newPassword.length < 12) {
      setPasswordError('Password must be at least 12 characters')
      return
    }

    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match')
      return
    }

    setIsUpdatingPassword(true)
    try {
      const supabase = createClient()
      const { error } = await supabase.auth.updateUser({ password: newPassword })
      if (error) {
        setPasswordError(error.message || 'Failed to set password')
        return
      }

      setNewPassword('')
      setConfirmPassword('')
      setPasswordSaved(true)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to set password'
      setPasswordError(message)
    } finally {
      setIsUpdatingPassword(false)
    }
  }

  const hasNameChanged = displayName.trim() !== (userFullName ?? '')

  return (
    <div className="space-y-6">
      {/* Personal Information */}
      <div className="dashboard-panel p-6">
        <div className="flex items-center gap-2 mb-4">
          <User className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Personal Information</h3>
        </div>

        <div className="space-y-4">
          {/* Display Name */}
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Display name
            </label>
            <div className="flex items-center gap-3">
              <input
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="Your name"
                className="dashboard-input h-9 w-full max-w-sm rounded-lg border px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/35"
              />
              <button
                onClick={handleSaveDisplayName}
                disabled={isSavingName || !hasNameChanged || !displayName.trim()}
                className="h-9 px-4 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-[background-color,color,transform] active:scale-[0.96] flex items-center gap-2"
              >
                {nameSaved ? (
                  <>
                    <Check className="h-3.5 w-3.5" />
                    Saved
                  </>
                ) : isSavingName ? (
                  'Saving...'
                ) : (
                  'Save'
                )}
              </button>
            </div>
            {nameError && (
              <p className="mt-1.5 text-xs text-destructive">{nameError}</p>
            )}
          </div>

          {/* Email (read-only) */}
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Email address
            </label>
            <div className="dashboard-input flex items-center gap-2 h-9 w-full max-w-sm rounded-lg border px-3">
              <Mail className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-sm text-muted-foreground">{userEmail}</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground/60">
              Email cannot be changed. Contact support if needed.
            </p>
          </div>
        </div>
      </div>

      {/* Security */}
      <div className="dashboard-panel p-6">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Security</h3>
        </div>

        <div className="space-y-4">
          {/* Set Password */}
          <form onSubmit={handleSetPassword}>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Set or change password
            </label>
            <p className="max-w-lg text-xs leading-5 text-muted-foreground/60 text-pretty">
              Add email-and-password sign-in to this account. Your existing Google sign-in
              will continue to work.
            </p>

            <div className="mt-3 grid max-w-lg gap-3 sm:grid-cols-2">
              <div>
                <label htmlFor="profile-new-password" className="sr-only">
                  New password
                </label>
                <input
                  id="profile-new-password"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  placeholder="New password"
                  minLength={12}
                  required
                  className="dashboard-input h-10 w-full rounded-lg border px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/35"
                />
              </div>
              <div>
                <label htmlFor="profile-confirm-password" className="sr-only">
                  Confirm password
                </label>
                <input
                  id="profile-confirm-password"
                  type="password"
                  autoComplete="new-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="Confirm password"
                  minLength={12}
                  required
                  className="dashboard-input h-10 w-full rounded-lg border px-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/35"
                />
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                type="submit"
                disabled={isUpdatingPassword || !newPassword || !confirmPassword}
                className="h-10 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-[background-color,color,transform] hover:bg-primary/90 active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span className="flex items-center gap-2">
                  {passwordSaved ? (
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  ) : (
                    <Lock className="h-3.5 w-3.5" aria-hidden="true" />
                  )}
                  {isUpdatingPassword
                    ? 'Saving...'
                    : passwordSaved
                      ? 'Password set'
                      : 'Set password'}
                </span>
              </button>
              <p className="text-xs text-muted-foreground/60">Minimum 12 characters.</p>
            </div>

            <div aria-live="polite">
              {passwordSaved && (
                <p className="mt-2 text-xs text-emerald-400">
                  Password saved. You can now sign in with {userEmail} and this password.
                </p>
              )}
              {passwordError && (
                <p className="mt-2 text-xs text-destructive">{passwordError}</p>
              )}
            </div>
          </form>

          {/* Active Sessions */}
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Active sessions
            </label>
            <p className="text-xs text-muted-foreground/60">
              You are currently signed in from this browser.
            </p>
          </div>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="dashboard-panel p-6">
        <h3 className="text-sm font-semibold text-destructive mb-2">Danger zone</h3>
        <p className="text-xs text-muted-foreground mb-3">
          Permanently delete your account and all associated data. This action cannot be undone.
        </p>
        <button
          disabled
          className="h-9 px-4 rounded-lg border border-destructive/30 text-sm font-medium text-destructive hover:bg-destructive/10 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Delete account
        </button>
        <p className="mt-1.5 text-xs text-muted-foreground/50">
          Contact support to delete your account.
        </p>
      </div>
    </div>
  )
}
