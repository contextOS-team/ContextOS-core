/** Remotion composition constants for the hero animation */

export const FPS = 30;
export const COMPOSITION_WIDTH = 1280;
export const COMPOSITION_HEIGHT = 720;

/** Scene durations in frames */
export const SCENE_1_DURATION = 90; // 3s - Ticket slide-in
export const SCENE_2_DURATION = 120; // 4s - Source search
export const SCENE_3_DURATION = 120; // 4s - Context page
export const LOOP_GAP = 30; // 1s - Dark gap before loop

export const TOTAL_DURATION =
  SCENE_1_DURATION + SCENE_2_DURATION + SCENE_3_DURATION + LOOP_GAP; // 360 frames = 12s

/** Spring configs matching Phase 15 cubic-bezier(0.34, 1.56, 0.64, 1) */
export const SPRING_ENTER = { damping: 13, stiffness: 100, mass: 0.8 };
export const SPRING_SUBTLE = {
  damping: 18,
  stiffness: 120,
  mass: 0.6,
  overshootClamping: true,
};
export const SPRING_BOUNCY = { damping: 10, stiffness: 100, mass: 1 };

/** Stagger delay between sequential animations */
export const STAGGER_FRAMES = 4; // ~133ms at 30fps

/** Cross-fade overlap between scenes */
export const CROSSFADE_FRAMES = 12;

/** Brand and UI colors */
export const COLORS = {
  background: "#0A0A0F",
  teal: "#00D4AA",
  tealGlow: "rgba(0,212,170,0.3)",
  cardBg: "rgba(255,255,255,0.13)",
  cardBorder: "rgba(255,255,255,0.24)",
  cardGradient:
    "linear-gradient(180deg, rgba(255,255,255,0.14) 0%, rgba(255,255,255,0.07) 100%)",
  text: "#FFFFFF",
  textMuted: "#9CA3AF",
  slackPurple: "#611F69",
  slackGreen: "#2EB67D",
  slackYellow: "#ECB22E",
  slackBlue: "#36C5F0",
  slackRed: "#E01E5A",
  github: "#FFFFFF",
  linear: "#5E6AD2",
  aiAccent: "#8B5CF6",
  aiAccentGlow: "rgba(139,92,246,0.3)",
} as const;
