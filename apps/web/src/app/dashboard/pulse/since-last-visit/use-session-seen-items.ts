'use client'

import { createContext, createElement, useContext, useMemo, useRef, type ReactNode } from 'react'

interface SeenItemsContextValue {
  markSeen: (id: string) => void
  hasSeen: (id: string) => boolean
}

const SeenItemsContext = createContext<SeenItemsContextValue | null>(null)

/**
 * Markers persist across the session they were seen in. The set is
 * intentionally a ref so re-renders don't fire when items are added.
 */
export function SeenItemsProvider({ children }: { children: ReactNode }) {
  const seenIdsRef = useRef<Set<string>>(new Set())

  const value = useMemo<SeenItemsContextValue>(
    () => ({
      markSeen: (id: string) => {
        seenIdsRef.current.add(id)
      },
      hasSeen: (id: string) => seenIdsRef.current.has(id),
    }),
    []
  )

  return createElement(SeenItemsContext.Provider, { value }, children)
}

export function useSessionSeenItems(): SeenItemsContextValue {
  const context = useContext(SeenItemsContext)

  if (!context) {
    throw new Error('useSessionSeenItems must be used within SeenItemsProvider')
  }

  return context
}
