'use client'

import { Toaster as SonnerToaster } from 'sonner'

export function Toaster() {
  return (
    <SonnerToaster
      theme="dark"
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast: 'bg-elevated border-border text-foreground',
          description: 'text-muted-foreground',
        },
      }}
    />
  )
}
