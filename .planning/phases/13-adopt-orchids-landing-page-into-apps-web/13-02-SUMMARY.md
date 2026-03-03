---
phase: 13-adopt-orchids-landing-page-into-apps-web
plan: 02
status: complete
---

# 13-02 Summary: Wire Landing Page into Next.js Routing

## One-liner
Wired landing page into Next.js routing at `/` with dark theme layout isolation, middleware updates, and ongoing design polish.

## What was done
- Created `(landing)` route group with layout importing `landing.css` and applying `landing-theme` class
- Composed all 9 section components into the landing page at `/`
- Updated Supabase middleware to allow `/` as a public path
- Removed old redirect `page.tsx`
- Extensive design polish: CSS hover utilities, gradient text rationing, asymmetric layouts, ProblemSection redesign with before/after comparison

## Files modified
- `apps/web/src/app/(landing)/layout.tsx` — Landing-specific layout with dark theme
- `apps/web/src/app/(landing)/page.tsx` — Landing page composing all sections
- `apps/web/src/lib/supabase/middleware.ts` — Added `/` as public path
- `apps/web/src/app/landing.css` — Hover utility classes
- `apps/web/src/components/landing/*.tsx` — Design polish across all components

## Outcome
Landing page is live at `/` with dark teal theme, all 9 sections, scroll animations. Dashboard at `/dashboard` remains untouched.
