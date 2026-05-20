// Phase 41: Sidebar is now a wrapper around ChromeNav so the rest of the
// dashboard layout system (auth guard, layout.tsx import) doesn't need to change.
// The actual nav lives in apps/web/src/app/dashboard/chrome/chrome-nav.tsx.
'use client'

export { ChromeNav as Sidebar } from './chrome/chrome-nav'
