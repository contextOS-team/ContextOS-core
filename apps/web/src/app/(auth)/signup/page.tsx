'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { createClient } from '@/lib/supabase/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { SocialButtons } from '@/components/auth/social-buttons'

export default function SignupPage() {
  const router = useRouter()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  async function handleSignUp(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    if (password.length < 6) {
      setError('Password must be at least 6 characters')
      setLoading(false)
      return
    }

    try {
      const supabase = createClient()
      const { error, data } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: fullName,
          },
          emailRedirectTo: `${process.env.NEXT_PUBLIC_APP_URL || window.location.origin}/auth/callback`,
        },
      })

      if (error) {
        setError(error.message)
        return
      }

      // Supabase anti-enumeration: when an email is already registered it returns
      // a stub user with identities=[] (not an error). Surface as a clear error.
      if (data.user && data.user.identities && data.user.identities.length === 0) {
        setError('This email is already registered. Sign in instead.')
        return
      }

      if (data.session) {
        router.push('/onboarding')
        router.refresh()
        return
      }

      setSuccess(true)
    } catch (err) {
      console.error('signup failed', err)
      setError(err instanceof Error ? err.message : 'Sign up failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="space-y-6 stagger-children">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Check your email</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            We sent a confirmation link to <strong>{email}</strong>. Click the link
            to activate your account.
          </p>
        </div>
        <div className="text-center">
          <p className="text-sm text-muted-foreground">
            Already confirmed?{' '}
            <Link href="/login" className="text-primary underline underline-offset-4 hover:text-primary/80">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 stagger-children">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Create Account</h1>
        <p className="text-sm text-muted-foreground">
          Sign up for ContextOS to get started
        </p>
      </div>

      {error && (
        <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <SocialButtons />

      {/* Separator */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <span className="w-full border-t" />
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-elevated px-2 text-muted-foreground">or</span>
        </div>
      </div>

      <form onSubmit={handleSignUp} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="full-name">Full name</Label>
          <Input
            id="full-name"
            type="text"
            placeholder="Your name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            placeholder="Min 6 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
          />
        </div>
        <Button type="submit" size="lg" className="w-full" disabled={loading}>
          {loading ? 'Creating account...' : 'Sign Up'}
        </Button>
      </form>

      <div className="text-center">
        <p className="text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link href="/login" className="text-primary underline underline-offset-4 hover:text-primary/80">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
