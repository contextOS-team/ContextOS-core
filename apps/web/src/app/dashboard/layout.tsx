import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import { Sidebar } from './sidebar'

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

  // Onboarding redirect is enforced by middleware. Dropping the duplicate
  // Supabase query here removes one round-trip from every dashboard navigation.

  return (
    <div className="relative flex flex-col min-h-screen bg-background dashboard-grain">
      <Sidebar
        userEmail={user.email ?? ''}
        userFullName={user.user_metadata?.full_name}
      />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-6 py-10 lg:px-10">
          {children}
        </div>
      </main>
    </div>
  )
}
