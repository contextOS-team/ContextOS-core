/** Remotion composition constants for the hero animation */

export const FPS = 30;
export const COMPOSITION_WIDTH = 1280;
export const COMPOSITION_HEIGHT = 720;

/** Scene durations in frames — 3 scenes, 12s total */
export const SCENE_1_DURATION = 90; // 3.0s - Dashboard
export const SCENE_2_DURATION = 105; // 3.5s - Sources assemble
export const SCENE_3_DURATION = 165; // 5.5s - Context page

export const TOTAL_DURATION =
  SCENE_1_DURATION + SCENE_2_DURATION + SCENE_3_DURATION; // 360 frames = 12s

/** Spring configs */
export const SPRING_ENTER = { damping: 13, stiffness: 100, mass: 0.8 };
export const SPRING_SUBTLE = {
  damping: 18,
  stiffness: 120,
  mass: 0.6,
  overshootClamping: true,
};

/** Stagger delay between sequential animations */
export const STAGGER_FRAMES = 4;

/** Cross-fade overlap between scenes */
export const CROSSFADE_FRAMES = 12;

/** Colors — background matches landing page #0A0A0F */
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
  pink: "#E879A8",
  amber: "#D4A017",
  green: "#34D399",
  blue: "#60A5FA",
  sky: "#38BDF8",
  emerald: "#10B981",

  cardShadow:
    "0 0 0 1px rgba(255,255,255,0.05), 0 2px 8px rgba(0,0,0,0.4)",
} as const;
