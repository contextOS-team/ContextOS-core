# Phase 23: Remotion Animated Hero - Research

**Researched:** 2026-03-08
**Domain:** Remotion Player integration, landing page animation, Next.js App Router
**Confidence:** HIGH

## Summary

This phase replaces the current static `demo.mp4` hero video with a Remotion-powered animated product walkthrough rendered in real-time via `@remotion/player`. The Player component is a client-side React component that renders Remotion compositions inline -- no server-side rendering or video file generation needed. For this use case (Player-only, no rendering/Lambda), the integration is lightweight: install `remotion` + `@remotion/player`, create composition components, and embed the `<Player>` in a `"use client"` component.

Remotion v4 is the current major version (latest v4.0.434 as of March 2026). The `spring()` function provides physics-based animation with configurable mass/damping/stiffness. The `<Sequence>` and `<Series>` components handle multi-scene temporal layout. At 30fps with a 10-12 second duration, the composition needs ~300-360 frames total.

Modern 2026 SaaS landing pages (Linear, Vercel, Stripe) favor intentional micro-motion over flashy effects: precise spring animations, staggered reveals, subtle scale transitions, and clean minimalist aesthetic. The project's existing spring curve `cubic-bezier(0.34, 1.56, 0.64, 1)` maps well to Remotion's spring config with moderate overshoot (damping ~12-14, stiffness ~100).

**Primary recommendation:** Install `remotion` and `@remotion/player` only (no CLI/bundler/renderer needed). Create a `remotion/` folder with three scene components and a root composition. Embed via `<Player>` in a client component with `next/dynamic` lazy loading. Use `<Series>` for sequential scene layout and `spring()` for all motion.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- 3-scene product walkthrough: Scene 1 (0-3s) ticket card slides in, Scene 2 (3-7s) source icons activate with progress bars, Scene 3 (7-11s) context page materializes
- Stylized mockup fidelity -- recognizable as ContextOS but simplified
- ~10-12 second total duration per loop
- @remotion/player embedded directly (real-time React rendering, no pre-rendered video)
- Replaces demo.mp4 entirely
- Player container keeps existing scroll-driven perspective effect (rotateX + scale)
- Linear/Vercel minimal aesthetic
- Spring easing consistent with Phase 15 dashboard animations
- Stagger delays 100-150ms, subtle scale 0.95->1
- Teal glow #00D4AA on active elements, dark #0A0A0F background
- Card shadows + glass borders, no particles, no noise effects
- Source icons use real brand colors; teal only for progress/active states
- Auto-play on page load, loops continuously, ~1s pause between loops
- Headline, subheadline, badge, CTAs remain as regular HTML
- Remotion Player renders only the product walkthrough area

### Claude's Discretion
- Exact Remotion composition structure and component decomposition
- Spring animation parameters and timing fine-tuning
- How to handle the loop-to-restart transition (fade, reset, or smooth)
- Responsive sizing of the Player at different breakpoints
- Whether to lazy-load the Remotion Player for performance
- Research findings on modern landing page hero best practices to inform motion design choices

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `remotion` | ^4.0.434 | Core animation primitives (useCurrentFrame, spring, interpolate, Sequence, Series, AbsoluteFill) | Required peer dependency for @remotion/player |
| `@remotion/player` | ^4.0.434 | Embeddable React player component for real-time composition rendering | Official way to embed Remotion in existing apps without video rendering |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `lucide-react` | (already installed) | Icons for UI elements in animation scenes | For ticket/action icons in mockup scenes |
| `next/dynamic` | (built-in) | Lazy loading the Player component | Wrap Player import to code-split Remotion from main bundle |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @remotion/player | Pre-rendered MP4 via @remotion/renderer | Larger file, no runtime flexibility, but zero JS cost -- not chosen because user locked real-time rendering |
| @remotion/player | Framer Motion timeline | No composition model, no frame-based control, harder multi-scene orchestration |
| @remotion/player | Rive/Lottie | Different paradigm (state machines), not React-native rendering, different toolchain |

### NOT Needed
These Remotion packages are NOT required for Player-only integration:
- `@remotion/cli` -- only for Remotion Studio preview (useful in dev but optional)
- `@remotion/bundler` -- for server-side rendering pipelines
- `@remotion/renderer` -- for FFmpeg-based video rendering
- `@remotion/lambda` -- for AWS Lambda rendering

**Installation:**
```bash
cd apps/web && pnpm add remotion @remotion/player
```

Optionally for dev preview in Remotion Studio:
```bash
pnpm add -D @remotion/cli
```

## Architecture Patterns

### Recommended Project Structure
```
apps/web/src/
├── remotion/
│   ├── HeroComposition.tsx      # Root composition (all 3 scenes)
│   ├── scenes/
│   │   ├── TicketScene.tsx       # Scene 1: Ticket card (0-90 frames)
│   │   ├── SourcesScene.tsx     # Scene 2: Source icons + progress (90-210 frames)
│   │   └── ContextScene.tsx     # Scene 3: Context page (210-330 frames)
│   ├── components/
│   │   ├── MockCard.tsx         # Reusable card with glass border styling
│   │   ├── ProgressBar.tsx      # Animated progress bar with teal fill
│   │   ├── SourceIcon.tsx       # Brand-colored source icon (Slack/GitHub/Linear)
│   │   └── SectionBlock.tsx     # Context page section block
│   └── constants.ts             # FPS, duration, colors, spring configs
├── components/landing/
│   ├── Hero.tsx                 # Modified: Player replaces <video>
│   └── RemotionPlayer.tsx       # Client component wrapping <Player>
```

### Pattern 1: Series-Based Multi-Scene Composition
**What:** Use `<Series>` to sequence three scenes that play one after another
**When to use:** When scenes are sequential and non-overlapping (which they are here)
**Example:**
```typescript
// Source: https://www.remotion.dev/docs/series
import { AbsoluteFill, Series, useVideoConfig } from "remotion";
import { TicketScene } from "./scenes/TicketScene";
import { SourcesScene } from "./scenes/SourcesScene";
import { ContextScene } from "./scenes/ContextScene";

const SCENE_1_FRAMES = 90;  // 3s at 30fps
const SCENE_2_FRAMES = 120; // 4s at 30fps
const SCENE_3_FRAMES = 120; // 4s at 30fps
// Total: 330 frames = 11s

export const HeroComposition: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#0A0A0F" }}>
      <Series>
        <Series.Sequence durationInFrames={SCENE_1_FRAMES}>
          <TicketScene />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENE_2_FRAMES}>
          <SourcesScene />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENE_3_FRAMES}>
          <ContextScene />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
```

### Pattern 2: Spring-Driven Element Animation
**What:** Use `spring()` + `interpolate()` for all element motion within scenes
**When to use:** Every animated property (opacity, translateY, scale, width)
**Example:**
```typescript
// Source: https://www.remotion.dev/docs/spring
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

export const TicketScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Card slides in from right with spring
  const slideIn = spring({
    frame,
    fps,
    config: { damping: 13, stiffness: 100, mass: 0.8 },
  });

  const translateX = interpolate(slideIn, [0, 1], [120, 0]);
  const opacity = interpolate(slideIn, [0, 1], [0, 1]);
  const scale = interpolate(slideIn, [0, 1], [0.95, 1]);

  // Staggered detail population
  const detailDelay = 12; // ~400ms at 30fps
  const detail1 = spring({ frame: frame - detailDelay, fps, config: { damping: 15 } });
  const detail2 = spring({ frame: frame - detailDelay * 2, fps, config: { damping: 15 } });

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
      <div
        style={{
          transform: `translateX(${translateX}px) scale(${scale})`,
          opacity,
        }}
      >
        {/* Card content with staggered details */}
      </div>
    </AbsoluteFill>
  );
};
```

### Pattern 3: Player Embedding with Lazy Loading
**What:** Wrap Player in a client component, lazy-load with next/dynamic
**When to use:** Always -- Remotion Player is client-only
**Example:**
```typescript
// RemotionPlayer.tsx - "use client"
"use client";

import { Player } from "@remotion/player";
import { useCallback } from "react";
import type { HeroComposition } from "@/remotion/HeroComposition";

const lazyComponent = () => import("@/remotion/HeroComposition").then(m => ({ default: m.HeroComposition }));

const FPS = 30;
const DURATION_FRAMES = 360; // 12s total (11s animation + 1s pause)
const WIDTH = 1280;
const HEIGHT = 720;

export function RemotionHeroPlayer() {
  const LazyComp = useCallback(lazyComponent, []);

  return (
    <Player
      lazyComponent={LazyComp}
      durationInFrames={DURATION_FRAMES}
      fps={FPS}
      compositionWidth={WIDTH}
      compositionHeight={HEIGHT}
      loop
      autoPlay
      style={{ width: "100%" }}
      acknowledgeRemotionLicense
    />
  );
}
```

```typescript
// Hero.tsx - dynamically import RemotionPlayer
import dynamic from "next/dynamic";

const RemotionHeroPlayer = dynamic(
  () => import("./RemotionPlayer").then(m => ({ default: m.RemotionHeroPlayer })),
  { ssr: false }
);
```

### Pattern 4: Loop-to-Restart Transition via Blank Frames
**What:** Add ~30 blank frames (1s) at composition end for pause between loops
**When to use:** The user wants ~1s pause between loop end and restart
**Example:**
```typescript
// In HeroComposition, after the last Series.Sequence:
// The total durationInFrames passed to Player is SCENE_TOTAL + 30
// The last 30 frames simply show the final state fading out or holding
// When the Player loops, there's a natural 1s gap

// Alternative: use an exit fade on the last scene
const exitFade = interpolate(frame, [SCENE_3_FRAMES - 15, SCENE_3_FRAMES], [1, 0], {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
});
```

### Anti-Patterns to Avoid
- **CSS transitions/animations inside Remotion compositions:** "Always animate using useCurrentFrame()" -- CSS animations are not frame-synced and will flicker during rendering
- **Non-memoized inputProps:** Always wrap inputProps in useMemo() to prevent Player re-renders
- **Inline lazyComponent:** Always wrap lazyComponent in useCallback() -- otherwise React creates a new function reference every render, causing constant remounting
- **Using `<Composition>` in Player:** "The Player does not use `<Composition>`'s. Pass your component directly"
- **Rendering Player server-side:** Player is client-only. Always use `"use client"` directive and/or `dynamic({ ssr: false })`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-scene timing | Manual frame math with useCurrentFrame offsets | `<Series>` component | Automatic sequential timing, handles duration calculation |
| Spring physics | Custom easing functions or CSS cubic-bezier | `spring()` from remotion | Physics-based, configurable mass/damping/stiffness, frame-synced |
| Value mapping | Manual lerp functions | `interpolate()` | Handles extrapolation clamping, multi-stop ranges |
| Composition layout | Manual absolute positioning | `<AbsoluteFill>` | Full-bleed overlay with proper stacking |
| Lazy loading | Custom dynamic import wrapper | `lazyComponent` prop on Player | Built-in Suspense integration |
| Frame timing | setTimeout/requestAnimationFrame | `useCurrentFrame()` + `useVideoConfig()` | Frame-perfect, deterministic, renders correctly at any playback speed |

**Key insight:** Remotion's entire value is deterministic frame-based animation. Every animated value MUST flow through `useCurrentFrame()` -- never use browser animation APIs (requestAnimationFrame, CSS transitions, setInterval) inside compositions.

## Common Pitfalls

### Pitfall 1: Bundle Size Explosion
**What goes wrong:** Installing full Remotion suite (CLI, bundler, renderer) when only Player is needed
**Why it happens:** Templates include everything; tutorials show full setup
**How to avoid:** Only install `remotion` + `@remotion/player`. The `remotion` package is the core (~lightweight), and `@remotion/player` adds the Player component. Skip CLI/bundler/renderer.
**Warning signs:** node_modules grows significantly, FFmpeg binaries appear

### Pitfall 2: Server-Side Rendering Crashes
**What goes wrong:** Next.js tries to render Player during SSR, crashes because Player uses browser APIs
**Why it happens:** Forgetting `"use client"` or not using `dynamic({ ssr: false })`
**How to avoid:** Two-layer defense: (1) `"use client"` on RemotionPlayer.tsx, (2) `dynamic(() => import("./RemotionPlayer"), { ssr: false })` in Hero.tsx
**Warning signs:** "window is not defined" or "document is not defined" errors during build

### Pitfall 3: Autoplay Browser Restrictions
**What goes wrong:** Video doesn't autoplay on page load
**Why it happens:** Browser autoplay policies (primarily for audio content)
**How to avoid:** Since this animation has NO audio, autoplay should work fine. Muted/silent content is allowed to autoplay. If audio were ever added, use `initiallyMuted={true}` and `numberOfSharedAudioTags`.
**Warning signs:** Player shows first frame but doesn't start playing

### Pitfall 4: Non-Memoized Props Causing Re-renders
**What goes wrong:** Player re-renders on every parent state change (scroll handler updates)
**Why it happens:** Passing new object references to inputProps or lazyComponent on each render
**How to avoid:** (1) Memoize inputProps with useMemo, (2) Wrap lazyComponent in useCallback, (3) Keep Player component separate from scroll-tracking state
**Warning signs:** Janky playback during scrolling, high CPU usage

### Pitfall 5: Scroll Handler + Player Performance
**What goes wrong:** The existing scroll-driven perspective effect (rotateX/scale) runs on every scroll event, potentially causing Player re-renders
**Why it happens:** scrollY state change re-renders the entire Hero component including Player
**How to avoid:** Split into two components: (1) HeroContent with scroll state and perspective transforms on a wrapper div, (2) RemotionHeroPlayer as a separate component that doesn't depend on scroll state. The perspective transform goes on a div WRAPPING the Player, not on the Player itself.
**Warning signs:** Animation stutters during scrolling

### Pitfall 6: Layout Shift on Player Load
**What goes wrong:** Page content shifts when Player loads asynchronously
**Why it happens:** Dynamic import means Player isn't rendered immediately; container has no intrinsic size
**How to avoid:** Set explicit aspect-ratio on the Player container div (16/9 or matching compositionWidth/compositionHeight), with a min-height fallback. Use the existing video container's dimensions.
**Warning signs:** CLS (Cumulative Layout Shift) increase

### Pitfall 7: Responsive Sizing Mismatch
**What goes wrong:** Player renders at fixed compositionWidth/Height but container is responsive
**Why it happens:** Remotion compositions have fixed dimensions; scaling is handled by the Player's style prop
**How to avoid:** Set `style={{ width: "100%" }}` on Player -- it automatically scales maintaining aspect ratio. The compositionWidth/Height define the internal coordinate system, not the display size.
**Warning signs:** Player renders too small or overflows on mobile

## Code Examples

### Complete Player Integration in Hero.tsx
```typescript
// apps/web/src/components/landing/Hero.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import { usePostHog } from "posthog-js/react";
import dynamic from "next/dynamic";

// Lazy-load the Remotion Player (client-only, code-split)
const RemotionHeroPlayer = dynamic(
  () => import("./RemotionPlayer").then((m) => ({ default: m.RemotionHeroPlayer })),
  {
    ssr: false,
    loading: () => (
      // Placeholder matching aspect ratio to prevent layout shift
      <div
        style={{
          width: "100%",
          aspectRatio: "16/9",
          backgroundColor: "#0A0A0F",
          borderRadius: "1rem",
        }}
      />
    ),
  }
);

export default function Hero() {
  // ... existing scroll/visible state logic unchanged ...
  // The perspective wrapper div stays the same
  // Replace <video> with <RemotionHeroPlayer />
}
```

### Spring Config for Premium SaaS Feel
```typescript
// apps/web/src/remotion/constants.ts
// Source: https://www.remotion.dev/docs/spring

export const FPS = 30;
export const COMPOSITION_WIDTH = 1280;
export const COMPOSITION_HEIGHT = 720;

// Scene durations in frames
export const SCENE_1_DURATION = 90;   // 3s - Ticket card
export const SCENE_2_DURATION = 120;  // 4s - Sources
export const SCENE_3_DURATION = 120;  // 4s - Context page
export const LOOP_GAP = 30;           // 1s - Pause before loop
export const TOTAL_DURATION = SCENE_1_DURATION + SCENE_2_DURATION + SCENE_3_DURATION + LOOP_GAP;

// Spring configs matching Phase 15 cubic-bezier(0.34, 1.56, 0.64, 1)
export const SPRING_ENTER = {
  damping: 13,
  stiffness: 100,
  mass: 0.8,
  // Moderate overshoot matching the 1.56 control point
};

export const SPRING_SUBTLE = {
  damping: 18,
  stiffness: 120,
  mass: 0.6,
  overshootClamping: true,
  // For progress bars, opacity fades -- no bounce
};

export const SPRING_BOUNCY = {
  damping: 10,
  stiffness: 100,
  mass: 1,
  // For the final "tada" moments -- checkmarks, highlights
};

// Stagger delay in frames (100-150ms at 30fps = 3-5 frames)
export const STAGGER_FRAMES = 4; // ~133ms

// Brand colors
export const COLORS = {
  background: "#0A0A0F",
  teal: "#00D4AA",
  tealGlow: "rgba(0,212,170,0.3)",
  cardBg: "rgba(255,255,255,0.03)",
  cardBorder: "rgba(255,255,255,0.08)",
  text: "#FFFFFF",
  textMuted: "#9CA3AF",
  // Source brand colors
  slack: { purple: "#4A154B", green: "#2EB67D", yellow: "#ECB22E" },
  github: "#FFFFFF",
  linear: "#5E6AD2",
};
```

### Responsive Player Sizing
```typescript
// The Player's compositionWidth/Height define internal coordinates.
// The style prop controls display size. width:"100%" scales proportionally.
// For different breakpoints, wrap in a responsive container:

<div className="mx-auto max-w-3xl w-full">
  {/* On mobile, the Player naturally scales down because max-w-3xl constrains width */}
  {/* The Player maintains aspect ratio (compositionWidth/compositionHeight) */}
  <RemotionHeroPlayer />
</div>

// No need for different compositionWidth at breakpoints --
// Remotion scales the render to fit the container.
```

### Staggered Element Animation Pattern
```typescript
// Source: https://www.remotion.dev/docs/spring
import { useCurrentFrame, useVideoConfig, spring, interpolate, AbsoluteFill } from "remotion";
import { SPRING_ENTER, STAGGER_FRAMES } from "../constants";

export const SourcesScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const sources = [
    { name: "Slack", color: "#4A154B", icon: "MessageSquare" },
    { name: "GitHub", color: "#FFFFFF", icon: "Github" },
    { name: "Linear", color: "#5E6AD2", icon: "Layout" },
  ];

  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", gap: 24 }}>
      {sources.map((source, i) => {
        const delay = i * STAGGER_FRAMES;
        const enter = spring({
          frame: frame - delay,
          fps,
          config: SPRING_ENTER,
        });
        const opacity = interpolate(enter, [0, 1], [0, 1]);
        const scale = interpolate(enter, [0, 1], [0.95, 1]);

        // Progress bar fills after icon appears
        const progressDelay = delay + 15; // 500ms after icon
        const progress = spring({
          frame: frame - progressDelay,
          fps,
          config: { damping: 20, stiffness: 80 },
        });

        return (
          <div key={source.name} style={{ opacity, transform: `scale(${scale})` }}>
            {/* Source icon + progress bar */}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pre-rendered MP4 hero videos | Real-time rendered compositions via @remotion/player | 2024-2025 | Dynamic content, smaller initial payload, runtime customizable |
| Lottie/After Effects exports | React-native compositions (Remotion, Rive) | 2024-2025 | Developer-friendly, version-controlled, component-reusable |
| Heavy parallax + particle effects | Intentional micro-motion, spring physics | 2025-2026 | Premium SaaS feel (Linear/Vercel style), better performance |
| Full-bleed hero videos | Embedded product previews/walkthroughs | 2025-2026 | Shows value proposition immediately, higher conversion |
| CSS keyframe animations | Physics-based springs | 2024-2025 | More natural motion, consistent feel across interactions |

**2026 Landing Page Trends (relevant):**
- Narrative hero animations that show the product flow in seconds (exactly what this phase does)
- Intentional restraint -- fewer, more meaningful animations beat flashy effects
- Spring physics for natural feel (Linear pioneered this)
- Dark backgrounds with selective glow accents (matches ContextOS brand)
- Interactive product previews replacing static screenshots/videos

## Open Questions

1. **Remotion License for Production**
   - What we know: Remotion v4 requires a license for companies with 3+ employees using it in production. The `acknowledgeRemotionLicense` prop suppresses console warnings.
   - What's unclear: Whether this project needs a paid license or qualifies for the free tier
   - Recommendation: Set `acknowledgeRemotionLicense={true}` on Player. Check https://remotion.dev/license for current terms. Remotion is free for individuals and companies with fewer than 3 employees.

2. **Turbopack Compatibility**
   - What we know: The project uses `next dev --turbopack`. Remotion Player is a client-side React component that should work fine with Turbopack since it doesn't need webpack overrides (those are only for @remotion/bundler).
   - What's unclear: Whether there are any Turbopack-specific issues with Remotion imports
   - Recommendation: Test early. If Turbopack fails, add `transpilePackages: ["remotion", "@remotion/player"]` to next.config.ts

3. **Optimal Composition Dimensions**
   - What we know: The existing video container is max-w-3xl (~768px). Player scales from compositionWidth/Height.
   - What's unclear: Best internal resolution for crisp rendering without performance overhead
   - Recommendation: Use 1280x720 (16:9) as composition dimensions. This provides sufficient detail while keeping render performance good. The Player scales down to container size automatically.

## Sources

### Primary (HIGH confidence)
- [Remotion Player API](https://www.remotion.dev/docs/player/player) - Complete Player component props and ref API
- [Remotion Player Best Practices](https://www.remotion.dev/docs/player/best-practices) - Performance optimization, memoization, autoplay
- [Remotion spring() API](https://www.remotion.dev/docs/spring) - Physics animation parameters and config
- [Remotion interpolate() API](https://www.remotion.dev/docs/interpolate) - Value mapping with extrapolation
- [Remotion Sequence API](https://www.remotion.dev/docs/sequence) - Time-shifting and multi-scene layout
- [Remotion Series API](https://www.remotion.dev/docs/series) - Sequential scene composition
- [Remotion Animating Properties](https://www.remotion.dev/docs/animating-properties) - Core animation patterns
- [Remotion Brownfield Installation](https://www.remotion.dev/docs/brownfield) - Installing in existing projects
- [Remotion Next.js Template (App Dir)](https://github.com/remotion-dev/template-next-app-dir) - Official Next.js App Router template

### Secondary (MEDIUM confidence)
- [SaaS Landing Page Trends 2026](https://www.saasframe.io/blog/10-saas-landing-page-trends-for-2026-with-real-examples) - Industry trends
- [Interactive Hero Animations 2026](https://dev.to/uianimation/why-saas-websites-are-moving-to-interactive-hero-animations-in-2026-16l4) - Pattern analysis
- [Next.js Lazy Loading Guide](https://nextjs.org/docs/app/guides/lazy-loading) - Dynamic imports with ssr:false

### Tertiary (LOW confidence)
- [Remotion Best Practices Skill (LobeHub)](https://lobehub.com/skills/guanyang-antigravity-skills-remotion) - Community-curated patterns (not verified against official docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Remotion docs clearly document Player-only setup
- Architecture: HIGH - Series/Sequence/spring patterns are well-documented core APIs
- Pitfalls: HIGH - SSR, memoization, and autoplay issues are documented in official best practices
- Spring parameters: MEDIUM - Exact damping/stiffness values to match existing cubic-bezier are approximate and need visual tuning
- 2026 trends: MEDIUM - Multiple sources agree on direction but specifics vary

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (Remotion v4 is stable, API unlikely to change within 30 days)
