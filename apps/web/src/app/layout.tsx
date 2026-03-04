import type { Metadata } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import { SentryInit } from '@/lib/sentry-init'
import { DarkModeApplier } from '@/components/dashboard/dark-mode-applier'
import { Toaster } from '@/components/ui/sonner'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
})

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
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{
          __html: `document.documentElement.classList.add('dark')`
        }} />
      </head>
      <body className="font-sans antialiased">
        <SentryInit />
        <DarkModeApplier />
        <Toaster />
        {children}
      </body>
    </html>
  )
}
