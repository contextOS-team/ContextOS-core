import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { MockCard } from "../components/MockCard";
import {
  COLORS,
  SPRING_BOUNCY,
  SPRING_ENTER,
  SPRING_SUBTLE,
  STAGGER_FRAMES,
} from "../constants";

const SECTION_STAGGER = STAGGER_FRAMES * 4; // 16 frames between sections

export const ContextScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Card slide-up animation
  const cardProgress = spring({ frame, fps, config: SPRING_ENTER });
  const cardTranslateY = interpolate(cardProgress, [0, 1], [40, 0]);
  const cardOpacity = interpolate(cardProgress, [0, 1], [0, 1]);

  // Section fade-in animations
  const sectionProgress = (index: number) =>
    spring({
      frame: Math.max(0, frame - 10 - index * SECTION_STAGGER),
      fps,
      config: SPRING_SUBTLE,
    });

  const headerProgress = sectionProgress(0);
  const bgProgress = sectionProgress(1);
  const decisionsProgress = sectionProgress(2);
  const promptProgress = sectionProgress(3);

  // AI Prompt glow pulse
  const promptGlow = spring({
    frame: Math.max(0, frame - 10 - 3 * SECTION_STAGGER),
    fps,
    config: SPRING_BOUNCY,
  });

  // End-of-scene fade out (frame > 100, fade over 20 frames)
  const fadeOut = interpolate(frame, [100, 120], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const sectionStyle = (progress: number): React.CSSProperties => ({
    opacity: progress,
    transform: `translateY(${interpolate(progress, [0, 1], [12, 0])}px)`,
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: COLORS.background,
        opacity: fadeOut,
      }}
    >
      <div
        style={{
          width: 560,
          transform: `translateY(${cardTranslateY}px)`,
          opacity: cardOpacity,
        }}
      >
        <MockCard>
          {/* Header */}
          <div style={sectionStyle(headerProgress)}>
            <div
              style={{
                fontSize: 20,
                fontWeight: 700,
                color: COLORS.text,
                marginBottom: 20,
              }}
            >
              ENG-42: Authentication Flow
            </div>
          </div>

          {/* Background section */}
          <div style={{ ...sectionStyle(bgProgress), marginBottom: 16 }}>
            <div
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: COLORS.text,
                marginBottom: 8,
              }}
            >
              Background
            </div>
            <div
              style={{
                fontSize: 13,
                color: COLORS.textMuted,
                lineHeight: 1.6,
              }}
            >
              OAuth 2.0 with JWT refresh tokens discussed in Slack #engineering.
              <br />
              Sarah proposed PKCE flow for SPA security (see thread from Feb 14).
            </div>
          </div>

          {/* Key Decisions section */}
          <div style={{ ...sectionStyle(decisionsProgress), marginBottom: 16 }}>
            <div
              style={{
                fontSize: 14,
                fontWeight: 600,
                color: COLORS.text,
                marginBottom: 8,
              }}
            >
              Key Decisions
            </div>
            <div
              style={{
                fontSize: 13,
                color: COLORS.textMuted,
                lineHeight: 1.8,
              }}
            >
              <div style={{ display: "flex", gap: 8 }}>
                <span style={{ color: COLORS.teal }}>*</span>
                <span>Use jose library for JWT (no native crypto dependency)</span>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <span style={{ color: COLORS.teal }}>*</span>
                <span>15-min access token, 7-day refresh with rotation</span>
              </div>
            </div>
          </div>

          {/* AI Prompt section */}
          <div style={sectionStyle(promptProgress)}>
            <div
              style={{
                borderLeft: `3px solid ${COLORS.teal}`,
                background: "rgba(0,212,170,0.06)",
                borderRadius: 8,
                padding: 16,
                boxShadow:
                  promptGlow > 0.5
                    ? `0 0 20px ${COLORS.tealGlow}`
                    : "none",
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: COLORS.teal,
                  marginBottom: 8,
                  textTransform: "uppercase" as const,
                  letterSpacing: 1,
                }}
              >
                AI Prompt
              </div>
              <div
                style={{
                  fontSize: 13,
                  color: COLORS.textMuted,
                  lineHeight: 1.6,
                  fontFamily: "monospace",
                }}
              >
                Implement OAuth 2.0 PKCE flow with jose JWT, 15-min access
                tokens, and 7-day rotating refresh tokens...
              </div>
            </div>
          </div>
        </MockCard>
      </div>
    </AbsoluteFill>
  );
};
