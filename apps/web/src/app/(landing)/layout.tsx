import type { Metadata } from 'next'
import '../landing.css'

export const metadata: Metadata = {
  title: 'ContextOS — Stop gathering context. Start shipping code.',
  description:
    'Engineers waste 2-6 hours per ticket hunting through Slack, Notion, and meeting notes. ContextOS auto-generates everything you need to know — before you write a single line.',
}

export default function LandingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="landing-theme landing-grain">
      {children}
    </div>
  )
}
