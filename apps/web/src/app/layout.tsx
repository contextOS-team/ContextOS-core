import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'ContextOS',
  description:
    'AI-generated context for every engineering ticket -- from Linear, Slack, and meetings.',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  )
}
