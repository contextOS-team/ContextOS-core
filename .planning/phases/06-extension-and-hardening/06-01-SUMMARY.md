---
phase: 06-extension-and-hardening
plan: 01
subsystem: ui
tags: [chrome-extension, manifest-v3, linear, spa-navigation, dom-manipulation]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Supabase auth and session tokens for API authentication
provides:
  - Chrome extension Manifest V3 with Linear ticket detection
  - Popup UI displaying context page sections with error/empty states
  - Background service worker for API communication
  - Content script handling SPA navigation on Linear
affects: [06-extension-and-hardening]

# Tech tracking
tech-stack:
  added: ["@types/chrome"]
  patterns: [vanilla-dom-popup, chrome-storage-api, spa-url-detection]

key-files:
  created:
    - apps/web/public/manifest.json
    - apps/web/src/extension/background.ts
    - apps/web/src/extension/content.ts
    - apps/web/src/extension/popup.html
    - apps/web/src/extension/popup.tsx
    - apps/web/src/extension/styles.css
    - apps/web/public/icons/icon-16.png
    - apps/web/public/icons/icon-48.png
    - apps/web/public/icons/icon-128.png
  modified:
    - apps/web/package.json

key-decisions:
  - "Vanilla DOM manipulation in popup instead of React to avoid build pipeline dependency"
  - "Monkey-patched history.pushState/replaceState + MutationObserver for SPA navigation detection"
  - "API token stored in chrome.storage.local with settings panel for manual configuration"

patterns-established:
  - "Extension popup uses vanilla TypeScript DOM manipulation (no framework runtime)"
  - "Content script detects SPA navigation via pushState/replaceState + title MutationObserver"
  - "Background service worker mediates between content script and popup via chrome.runtime messages"

requirements-completed: [EXT-01]

# Metrics
duration: 7min
completed: 2026-02-25
---

# Phase 06 Plan 01: Chrome Extension Summary

**Manifest V3 Chrome extension with Linear ticket detection, context page popup, and configurable API authentication**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-25T06:52:22Z
- **Completed:** 2026-02-25T06:59:33Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- Chrome Manifest V3 extension with Linear host permissions and service worker background
- Content script reliably detects ticket identifiers from Linear SPA navigation (pushState, replaceState, popstate, title mutations)
- Popup displays 5 context sections (origin story, business requirements, technical decisions, related work, AI prompt) with loading/empty/error/unauthorized states
- Settings panel for API token and backend URL configuration
- Placeholder PNG icons (16/48/128px) for toolbar display

## Task Commits

Each task was committed atomically:

1. **Task 1: Chrome extension manifest and service worker** - `f85706c` (feat)
2. **Task 2: Extension popup UI with context page display** - `8948b4b` (feat)

## Files Created/Modified
- `apps/web/public/manifest.json` - Manifest V3 configuration with permissions, content scripts, and service worker
- `apps/web/src/extension/content.ts` - Content script extracting Linear ticket IDs with SPA navigation handling
- `apps/web/src/extension/background.ts` - Service worker for ticket state management and backend API communication
- `apps/web/src/extension/popup.html` - HTML entry point for extension popup
- `apps/web/src/extension/popup.tsx` - Vanilla DOM popup rendering context sections with state management
- `apps/web/src/extension/styles.css` - Standalone utility styles for popup UI
- `apps/web/public/icons/icon-{16,48,128}.png` - Placeholder toolbar icons
- `apps/web/package.json` - Added @types/chrome dev dependency

## Decisions Made
- **Vanilla DOM over React:** Popup uses vanilla TypeScript DOM manipulation instead of React to keep the extension self-contained and avoid needing a separate build pipeline for the popup bundle.
- **SPA detection strategy:** Combined history.pushState/replaceState monkey-patching with MutationObserver on document title and popstate listener to cover all Linear SPA navigation patterns.
- **Manual token configuration:** Users paste their API token in a settings panel (gear icon) rather than trying to share Supabase session cookies across origins, which is simpler and more secure for v1.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed @types/chrome for TypeScript support**
- **Found during:** Task 1 (manifest and service worker)
- **Issue:** Extension files use chrome.* APIs which require type declarations not present in the project
- **Fix:** Installed @types/chrome as devDependency; fixed npm ENOTEMPTY error in stale node_modules
- **Files modified:** apps/web/package.json, apps/web/package-lock.json
- **Verification:** All extension files pass tsc --noEmit without errors
- **Committed in:** f85706c (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Essential for TypeScript type checking of chrome.* APIs. No scope creep.

## Issues Encountered
- npm install failed with ENOTEMPTY on a stale msw/lib/core directory in node_modules; resolved by removing the stale directory before install.

## User Setup Required
None - extension files are ready to load as unpacked extension from chrome://extensions.

## Next Phase Readiness
- Extension is ready to load in Chrome developer mode
- Context page API endpoint does not exist yet (handled gracefully with 404 state)
- Once backend context API is built, extension will work end-to-end without changes
- Custom icons can replace placeholder PNGs when branding is finalized

## Self-Check: PASSED

All 10 created/modified files verified on disk. Both task commits (f85706c, 8948b4b) verified in git log.

---
*Phase: 06-extension-and-hardening*
*Completed: 2026-02-25*
