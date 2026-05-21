import { redirect } from 'next/navigation'
import { getCachedUser } from '@/lib/supabase/server'
import { Sidebar } from './sidebar'

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const user = await getCachedUser()

  if (!user) {
    redirect('/login')
  }

  // Onboarding redirect is enforced by middleware. Dropping the duplicate
  // Supabase query here removes one round-trip from every dashboard navigation.

  return (
    <div className="relative flex flex-col min-h-screen bg-background">
      <Sidebar
        userEmail={user.email ?? ''}
        userFullName={user.user_metadata?.full_name}
      />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8 lg:px-12">
          {children}
        </div>
      </main>
    </div>
  )
}
