import type { Metadata } from 'next'
import { Suspense } from 'react'
import { LANDING_SEO } from '@/components/landing/landing-copy'
import { PostHogProvider, PostHogPageView } from '@/lib/posthog'
import '../landing.css'

export const metadata: Metadata = {
  title: LANDING_SEO.title,
  description: LANDING_SEO.description,
}

export default function LandingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <>
      <style>{`html, body { background-color: #0A0A0F !important; }`}</style>
      <PostHogProvider>
        <Suspense fallback={null}>
          <PostHogPageView />
        </Suspense>
        <div className="landing-theme landing-grain">
          {children}
        </div>
      </PostHogProvider>
    </>
  )
}
