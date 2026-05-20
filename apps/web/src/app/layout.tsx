import type { Metadata } from 'next'
import { Geist, Geist_Mono, Instrument_Serif, Inter, JetBrains_Mono } from 'next/font/google'
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

const geistSans = Geist({
  subsets: ['latin', 'cyrillic'],
  variable: '--font-geist-sans',
  display: 'swap',
})

const geistMono = Geist_Mono({
  subsets: ['latin'],
  variable: '--font-geist-mono',
  display: 'swap',
})

const instrumentSerif = Instrument_Serif({
  weight: '400',
  style: ['normal', 'italic'],
  subsets: ['latin'],
  variable: '--font-serif',
  display: 'swap',
})

export const metadata: Metadata = {
  title: {
    default: 'ContextOS - AI-generated context for engineering tickets',
    template: '%s | ContextOS',
  },
  description:
    'AI-generated context for every engineering ticket — from Linear, Slack, GitHub, and meetings. Stop context-switching, start shipping.',
  metadataBase: new URL('https://contextos.pro'),
  openGraph: {
    title: 'ContextOS - AI-generated context for engineering tickets',
    description:
      'AI-generated context for every engineering ticket — from Linear, Slack, GitHub, and meetings. Stop context-switching, start shipping.',
    url: 'https://contextos.pro',
    siteName: 'ContextOS',
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'ContextOS - AI-generated context for engineering tickets',
    description:
      'AI-generated context for every engineering ticket — from Linear, Slack, GitHub, and meetings.',
  },
  robots: {
    index: true,
    follow: true,
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} ${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable} dark`}
    >
      <head />
      <body className="font-sans antialiased" suppressHydrationWarning>
        <SentryInit />
        <DarkModeApplier />
        <Toaster />
        {children}
      </body>
    </html>
  )
}
