import Link from 'next/link'

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-screen">
      {/* Left: Brand panel (desktop only) */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-center items-center p-12 bg-background relative overflow-hidden">
        {/* Animated gradient orb behind wordmark */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[500px] w-[500px] rounded-full bg-primary/15 blur-[120px]" />
        <div className="absolute top-1/3 left-1/3 h-[300px] w-[300px] rounded-full bg-primary/10 blur-[100px]" />

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
            AI-generated context for every engineering ticket
          </p>
          <div className="mt-12 flex items-center justify-center gap-8 text-sm text-muted-foreground/80">
            <span className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-primary/70" />
              Linear &amp; GitHub
            </span>
            <span className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-primary/70" />
              Codebase-aware
            </span>
            <span className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-primary/70" />
              Auto-generated
            </span>
          </div>
        </div>
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
