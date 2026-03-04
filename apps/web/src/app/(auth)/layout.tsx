export default function AuthLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="flex min-h-screen">
      {/* Left: Brand panel (desktop only) */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-center items-center p-12 bg-background relative overflow-hidden">
        {/* Subtle teal radial glow */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,oklch(0.75_0.18_170/0.08),transparent_70%)]" />

        <div className="relative z-10 text-center">
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
            ContextOS
          </h1>
          <p className="mt-4 text-lg text-muted-foreground max-w-sm">
            AI-generated context for every engineering ticket
          </p>
        </div>
      </div>

      {/* Right: Form panel on elevated surface */}
      <div className="flex w-full lg:w-1/2 flex-col items-center justify-center bg-elevated p-8">
        <div className="w-full max-w-md">{children}</div>
      </div>
    </div>
  )
}
