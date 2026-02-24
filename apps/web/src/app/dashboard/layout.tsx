import Link from 'next/link'
import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { SignOutButton } from './sign-out-button'

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <Link href="/dashboard" className="text-lg font-semibold">
              ContextOS
            </Link>
            <nav className="flex items-center gap-4">
              <Link
                href="/dashboard"
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                Home
              </Link>
              <Link
                href="/dashboard/integrations"
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                Integrations
              </Link>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm text-muted-foreground">
              {user.email}
            </span>
            <SignOutButton />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
    </div>
  )
}
