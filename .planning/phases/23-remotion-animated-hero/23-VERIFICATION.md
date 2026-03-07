---
phase: 23-remotion-animated-hero
verified: 2026-03-08T04:00:00Z
status: human_needed
score: 9/11 must-haves verified
re_verification: false
human_verification:
  - test: "Verify animated hero plays on landing page"
    expected: "3-scene animated walkthrough auto-plays: ticket card slide-in, source search progress, context page materialization"
    why_human: "Visual rendering quality, animation smoothness, and spring physics feel cannot be verified programmatically"
  - test: "Verify scroll-driven perspective effect"
    expected: "Player container tilts with rotateX(12->0) and scales (0.88->1.0) as user scrolls"
    why_human: "Scroll interaction behavior requires browser runtime"
  - test: "Verify no layout shift on load"
    expected: "16:9 placeholder holds space while Player lazy-loads, no CLS"
    why_human: "Layout stability during dynamic loading requires visual confirmation"
  - test: "Verify mobile responsiveness"
    expected: "Player scales proportionally at 375px width, no overflow"
    why_human: "Responsive behavior needs visual confirmation at various breakpoints"
---

# Phase 23: Remotion Animated Hero Verification Report

**Phase Goal:** Replace the static demo.mp4 hero video with a Remotion-powered 3-scene animated product walkthrough (ticket card -> source search -> context page) rendered in real-time via @remotion/player, matching the Linear/Vercel minimal aesthetic with spring animations and brand colors
**Verified:** 2026-03-08T04:00:00Z
**Status:** human_needed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Remotion packages installed and importable in apps/web | VERIFIED | `remotion: ^4.0.434` and `@remotion/player: ^4.0.434` in apps/web/package.json |
| 2 | HeroComposition renders 3 sequential scenes totaling ~360 frames at 30fps | VERIFIED | HeroComposition.tsx uses Series with TicketScene(90f) + SourcesScene(120f) + ContextScene(120f) + 30f gap = 360 total; FPS=30 in constants.ts |
| 3 | Scene 1 shows a ticket card (ENG-42) sliding in with details populating | VERIFIED | TicketScene.tsx renders ENG-42 card with spring translateY/opacity/scale entrance, staggered priority/assignee/status details with SPRING_SUBTLE |
| 4 | Scene 2 shows Slack/GitHub/Linear source icons activating with progress bars | VERIFIED | SourcesScene.tsx renders 3 source rows with SourceIcon + ProgressBar, staggered appearance, animated labels ("Searching sources..." -> "3 sources found") |
| 5 | Scene 3 shows a context page materializing with sections fading in | VERIFIED | ContextScene.tsx renders 4 sections (header, background, key decisions, AI prompt) with staggered spring fade-in, teal glow on AI prompt via SPRING_BOUNCY |
| 6 | Landing page hero shows animated Remotion walkthrough instead of static video | VERIFIED | Hero.tsx uses `dynamic(() => import("./RemotionPlayer")...)` with ssr:false; no `<video>` element remains (only HTML comments reference "video") |
| 7 | Animation auto-plays on page load and loops continuously with ~1s gap | VERIFIED | RemotionPlayer.tsx passes `autoPlay`, `loop` props to Player; LOOP_GAP=30 frames (1s at 30fps) |
| 8 | Scroll-driven perspective effect (rotateX 12->0, scale 0.88->1.0) works on Player container | VERIFIED (code) | Hero.tsx computes rotateX/scale from scrollY, applies to parent div wrapping RemotionHeroPlayer; Player receives no scroll props |
| 9 | No layout shift when Player loads (placeholder with matching aspect ratio) | VERIFIED (code) | dynamic loading callback renders `<div style={{aspectRatio: "16/9", backgroundColor: "#0A0A0F", borderRadius: "1rem"}}/>` |
| 10 | Player is code-split and lazy-loaded (not in main bundle) | VERIFIED | `next/dynamic` with `ssr: false` and `lazyComponent` callback in RemotionPlayer.tsx; HeroComposition loaded via dynamic import |
| 11 | Headline, subheadline, badge, CTAs remain as regular HTML unchanged | VERIFIED | Hero.tsx preserves badge ("Now in early access"), h1 ("Stop gathering context..."), p (subheadline), and two CTA links with PostHog tracking |

**Score:** 11/11 truths verified at code level; 4 require human visual confirmation

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/web/src/remotion/constants.ts` | FPS, dimensions, spring configs, colors, durations | VERIFIED | All exports present: FPS=30, 1280x720, TOTAL_DURATION=360, 3 spring configs, COLORS object with brand colors |
| `apps/web/src/remotion/HeroComposition.tsx` | Root composition using Series for 3 scenes | VERIFIED | Exports HeroComposition, uses Series.Sequence for 3 scenes with correct durations |
| `apps/web/src/remotion/scenes/TicketScene.tsx` | Scene 1: Ticket card slide-in | VERIFIED | 198 lines, spring-based animation with useCurrentFrame, MockCard, staggered details, crossfade out |
| `apps/web/src/remotion/scenes/SourcesScene.tsx` | Scene 2: Source icons with progress bars | VERIFIED | 179 lines, staggered sources, ProgressBar/SourceIcon components, animated label transition |
| `apps/web/src/remotion/scenes/ContextScene.tsx` | Scene 3: Context page materialization | VERIFIED | 195 lines, 4-section staggered fade-in, AI prompt teal glow with SPRING_BOUNCY, crossfade out |
| `apps/web/src/remotion/components/MockCard.tsx` | Reusable glass card container | VERIFIED | Inline styles only, gradient background, teal glow shadow, accepts style override |
| `apps/web/src/remotion/components/ProgressBar.tsx` | Animated horizontal progress bar | VERIFIED | Inline styles, progress-driven width, tealGlow shadow when active |
| `apps/web/src/remotion/components/SourceIcon.tsx` | Source brand icon with active glow | VERIFIED | Real brand SVGs (Slack 4-color, GitHub octocat, Linear mark), tealGlow on active |
| `apps/web/src/components/landing/RemotionPlayer.tsx` | Client component wrapping Player | VERIFIED | "use client", Player with lazyComponent via useCallback, all required props |
| `apps/web/src/components/landing/Hero.tsx` | Modified hero with dynamic Player import | VERIFIED | next/dynamic with ssr:false, placeholder div, scroll perspective preserved |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| Hero.tsx | RemotionPlayer.tsx | next/dynamic with ssr:false | WIRED | `dynamic(() => import("./RemotionPlayer").then(m => ({default: m.RemotionHeroPlayer})), {ssr: false})` |
| RemotionPlayer.tsx | HeroComposition.tsx | lazyComponent import | WIRED | `import("@/remotion/HeroComposition").then(m => ({default: m.HeroComposition}))` |
| HeroComposition.tsx | scenes/*.tsx | Series.Sequence composition | WIRED | 3 Series.Sequence children wrapping TicketScene, SourcesScene, ContextScene |
| scenes/*.tsx | constants.ts | spring config and color imports | WIRED | All 3 scenes import COLORS, SPRING_ENTER, SPRING_SUBTLE, CROSSFADE_FRAMES from constants |
| Landing page | Hero.tsx | Component import | WIRED | `page.tsx` imports Hero from `@/components/landing` barrel export |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-----------|-------------|--------|----------|
| HERO-ANIM-01 | 23-01-PLAN | Remotion composition scenes | SATISFIED | All 3 scenes exist with frame-based spring animations, no CSS transitions |
| HERO-ANIM-02 | 23-01-PLAN | Constants and shared components | SATISFIED | constants.ts, MockCard, ProgressBar, SourceIcon all present with correct exports |
| HERO-ANIM-03 | 23-02-PLAN | Player integration into Hero | SATISFIED | RemotionPlayer.tsx wraps @remotion/player, Hero.tsx dynamically imports it |
| HERO-ANIM-04 | 23-02-PLAN | Visual quality and UX | NEEDS HUMAN | Code-level verification passes; visual quality requires human confirmation |

**Note:** HERO-ANIM-01 through HERO-ANIM-04 are referenced in ROADMAP.md and PLAN frontmatter but are not defined in REQUIREMENTS.md. The requirement IDs are tracked by the roadmap's success criteria only.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| MockCard.tsx | 6 | `className?: string` prop defined but unused in render | Info | Unused prop type; no functional impact |
| Hero.tsx | 154, 161 | Comments say "Demo video" / "Glow behind video" | Info | Stale comments referencing old video; cosmetic only |

No blocker or warning-level anti-patterns found. All Remotion components use inline styles (no className/Tailwind). All animations use frame-based spring/interpolate (no CSS transitions/animations). No TODO/FIXME/placeholder markers. No empty implementations.

### Human Verification Required

### 1. Animated Hero Visual Playback

**Test:** Run `cd apps/web && pnpm dev`, visit http://localhost:3000. Watch the hero area.
**Expected:** 3-scene animated walkthrough plays automatically: (1) ENG-42 ticket card slides in with staggered details, (2) Slack/GitHub/Linear icons appear with filling progress bars, (3) context page materializes with AI prompt teal glow. Animation loops with ~1s dark gap.
**Why human:** Spring animation smoothness, visual timing, and aesthetic quality cannot be verified programmatically.

### 2. Scroll Perspective Effect

**Test:** On the landing page, scroll down slowly while watching the animation container.
**Expected:** Container starts tilted (rotateX ~12deg, scale 0.88) and flattens/scales to normal as you scroll past.
**Why human:** Scroll interaction behavior requires runtime browser testing.

### 3. Loading State and Layout Stability

**Test:** Hard-refresh the landing page (Cmd+Shift+R) and watch the hero area.
**Expected:** A dark placeholder (matching 16:9 aspect ratio) holds space while the Remotion Player loads. No content jump or layout shift.
**Why human:** CLS during lazy loading requires visual observation of initial page render.

### 4. Mobile Responsiveness

**Test:** Resize browser to ~375px width (or use DevTools device mode).
**Expected:** Player scales down proportionally within the container, no horizontal overflow or cropping issues.
**Why human:** Responsive layout at various breakpoints requires visual confirmation.

### Gaps Summary

No code-level gaps found. All 11 observable truths are verified at the code level. All 10 required artifacts exist, are substantive (not stubs), and are properly wired together. All 5 key links are confirmed connected. All 4 commits referenced in summaries exist in git history.

Four items require human visual verification: animation playback quality, scroll perspective behavior, loading state stability, and mobile responsiveness. These are inherently visual/interactive behaviors that cannot be confirmed through static code analysis.

---

_Verified: 2026-03-08T04:00:00Z_
_Verifier: Claude (gsd-verifier)_
