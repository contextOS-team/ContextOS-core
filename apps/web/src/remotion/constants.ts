/** Remotion composition constants for the hero animation */

export const FPS = 30;
export const COMPOSITION_WIDTH = 1280;
export const COMPOSITION_HEIGHT = 720;

/** Scene durations in frames — 3 scenes, 10.5s total */
export const SCENE_1_DURATION = 90; // 3.0s - Ticket picker
export const SCENE_2_DURATION = 105; // 3.5s - Sources assemble
export const SCENE_3_DURATION = 120; // 4.0s - Context page

export const TOTAL_DURATION =
  SCENE_1_DURATION + SCENE_2_DURATION + SCENE_3_DURATION; // 315 frames = 10.5s

/** Spring configs — smooth and organic */
export const SPRING_ENTER = { damping: 16, stiffness: 80, mass: 1 };
export const SPRING_SUBTLE = {
  damping: 20,
  stiffness: 90,
  mass: 0.8,
  overshootClamping: true,
};

/** Stagger delay between sequential animations */
export const STAGGER_FRAMES = 4;

/** Cross-fade overlap between scenes */
export const CROSSFADE_FRAMES = 14;

/**
 * Colors — 3 functional accents:
 *   primary (teal)  = ContextOS brand, "ready" states
 *   amber           = external tools / sources
 *   violet          = tickets / work items
 */
export const COLORS = {
  background: "#0A0A0F",
  card: "#131320",
  elevated: "#1A1A2C",
  border: "#252538",
  foreground: "#EAEAF0",
  muted: "#7A7A94",
  primary: "#00D4AA",
  primaryGlow: "rgba(0,212,170,0.3)",

  violet: "#8B7CF6",
  amber: "#F59E0B",

  cardShadow:
    "0 0 0 1px rgba(255,255,255,0.05), 0 4px 12px rgba(0,0,0,0.5)",
} as const;
