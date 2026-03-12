import Link from 'next/link'
import { Sparkles, Search, Copy } from 'lucide-react'

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-screen">
      {/* Left: Brand panel (desktop only) */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-center items-center p-12 bg-background relative overflow-hidden">
        {/* Animated gradient orbs */}
        <div
          className="absolute top-1/2 left-1/2 h-[500px] w-[500px] rounded-full bg-primary/15 blur-[120px]"
          style={{ animation: 'auth-drift 20s ease-in-out infinite' }}
        />
        <div
          className="absolute top-1/3 left-1/3 h-[300px] w-[300px] rounded-full bg-primary/10 blur-[100px]"
          style={{ animation: 'auth-drift-reverse 25s ease-in-out infinite' }}
        />

        {/* Faint grid pattern for visual mass */}
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage:
              'linear-gradient(oklch(0.75 0.18 170 / 0.5) 1px, transparent 1px), linear-gradient(90deg, oklch(0.75 0.18 170 / 0.5) 1px, transparent 1px)',
            backgroundSize: '64px 64px',
          }}
        />

        <div className="relative z-10 text-center max-w-md">
          <h1 className="text-5xl font-bold tracking-tight bg-gradient-to-r from-primary via-primary/90 to-primary/60 bg-clip-text text-transparent">
            ContextOS
          </h1>
          <p className="mt-4 text-lg text-muted-foreground">
            Every ticket tells the full story
          </p>

          {/* Feature cards */}
          <div className="mt-12 space-y-3 text-left">
            <div className="border border-border/50 rounded-lg p-3 flex items-start gap-3">
              <Sparkles className="h-4 w-4 text-primary mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-foreground">Automatic Context</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  AI gathers Slack, GitHub, and meeting context per ticket
                </p>
              </div>
            </div>
            <div className="border border-border/50 rounded-lg p-3 flex items-start gap-3">
              <Search className="h-4 w-4 text-primary mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-foreground">Source-Aware</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Searches only your connected integrations
                </p>
              </div>
            </div>
            <div className="border border-border/50 rounded-lg p-3 flex items-start gap-3">
              <Copy className="h-4 w-4 text-primary mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-foreground">Ready to Paste</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Copy the AI prompt directly into your workflow
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* CSS keyframes for orb animations */}
        <style dangerouslySetInnerHTML={{ __html: `
          @keyframes auth-drift {
            0%, 100% { transform: translate(-50%, -50%) translate(0, 0); }
            25% { transform: translate(-50%, -50%) translate(30px, -20px); }
            50% { transform: translate(-50%, -50%) translate(-20px, 30px); }
            75% { transform: translate(-50%, -50%) translate(20px, 20px); }
          }
          @keyframes auth-drift-reverse {
            0%, 100% { transform: translate(0, 0); }
            25% { transform: translate(-20px, 25px); }
            50% { transform: translate(25px, -15px); }
            75% { transform: translate(-15px, -20px); }
          }
        `}} />
      </div>

      {/* Right: Form panel on elevated surface with left divider */}
      <div className="flex w-full lg:w-1/2 flex-col bg-elevated lg:border-l lg:border-border p-8">
        <div className="flex flex-1 justify-center pt-24 lg:pt-32">
          <div className="w-full max-w-md">{children}</div>
        </div>
        <footer className="text-center text-xs text-muted-foreground/50 pb-6">
          &copy; {new Date().getFullYear()} ContextOS
          {' '}&middot;{' '}
          <Link href="/terms" className="hover:text-muted-foreground transition-colors">Terms</Link>
          {' '}&middot;{' '}
          <Link href="/privacy" className="hover:text-muted-foreground transition-colors">Privacy</Link>
        </footer>
      </div>
    </div>
  )
}
