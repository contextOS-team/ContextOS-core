import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  COLORS,
  CROSSFADE_FRAMES,
  SCENE_3_DURATION,
  SPRING_ENTER,
  SPRING_SUBTLE,
  STAGGER_FRAMES,
} from "../constants";

/* ─────────────────────────────────────────────────────────
 * Scene 3: Context Page — the money shot
 *
 * Clean layout: header + sidebar sources + 3 content sections.
 * Only show what's readable at video scale.
 * ───────────────────────────────────────────────────────── */

const SECTION_STAGGER = STAGGER_FRAMES * 5;

const SOURCE_GROUPS = [
  { label: "Slack", color: COLORS.pink, count: "1" },
  { label: "GitHub", color: COLORS.green, count: "1" },
  { label: "Jira", color: COLORS.blue, count: "1" },
];

const SECTIONS = [
  {
    title: "Summary",
    borderColor: COLORS.primary,
    bgTint: "rgba(0,212,170,0.04)",
    content:
      "Real-time sync for mobile using WebSockets. Architecture decided with mobile team input.",
  },
  {
    title: "Key Decisions",
    borderColor: COLORS.violet,
    bgTint: "transparent",
    content: "WebSockets over polling — <200ms latency budget",
    bullet: true,
  },
  {
    title: "Requirements",
    borderColor: COLORS.amber,
    bgTint: "transparent",
    content: "Ship by Sprint 13 per mobile team",
  },
];

export const ContextScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const cardProg = spring({ frame, fps, config: SPRING_ENTER });
  const cardY = interpolate(cardProg, [0, 1], [24, 0]);
  const cardOpacity = interpolate(cardProg, [0, 1], [0, 1]);
  const cardScale = interpolate(cardProg, [0, 1], [0.98, 1]);

  const fadeOut = interpolate(
    frame,
    [SCENE_3_DURATION - CROSSFADE_FRAMES, SCENE_3_DURATION],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const sp = (i: number) =>
    spring({
      frame: Math.max(0, frame - 8 - i * SECTION_STAGGER),
      fps,
      config: SPRING_SUBTLE,
    });

  const ss = (p: number): React.CSSProperties => ({
    opacity: p,
    transform: `translateY(${interpolate(p, [0, 1], [10, 0])}px)`,
  });

  const headerProg = sp(0);
  const sidebarProg = sp(0.5);

  // Breathing glow on "ready" badge during dwell time (frame 80+)
  const breathCycle = Math.max(0, frame - 80);
  const breathGlow = breathCycle > 0
    ? 0.3 + 0.3 * Math.sin(breathCycle * 0.08)
    : 0;

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
          width: 860,
          transform: `translateY(${cardY}px) scale(${cardScale})`,
          opacity: cardOpacity,
        }}
      >
        <div
          style={{
            background: COLORS.card,
            border: `1px solid ${COLORS.border}`,
            borderRadius: 12,
            boxShadow: `${COLORS.cardShadow}, 0 0 50px rgba(0,212,170,0.04)`,
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <div
            style={{
              ...ss(headerProg),
              padding: "20px 28px",
              borderBottom: `1px solid ${COLORS.border}`,
              background: COLORS.elevated,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: 16,
                  color: COLORS.primary,
                  fontWeight: 600,
                }}
              >
                ENG-421
              </span>
              <span
                style={{
                  fontSize: 19,
                  fontWeight: 600,
                  color: COLORS.foreground,
                  fontFamily: "system-ui, sans-serif",
                }}
              >
                Real-time sync for mobile
              </span>
            </div>
            {/* Status badge with breathing glow */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                background: "rgba(16,185,129,0.1)",
                borderRadius: 20,
                padding: "4px 12px",
                boxShadow: breathGlow > 0
                  ? `0 0 ${breathGlow * 16}px rgba(16,185,129,${breathGlow * 0.4})`
                  : "none",
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 3,
                  background: COLORS.emerald,
                  boxShadow: breathGlow > 0
                    ? `0 0 ${breathGlow * 8}px ${COLORS.emerald}`
                    : "none",
                }}
              />
              <span
                style={{ fontSize: 13, color: COLORS.emerald, fontWeight: 500 }}
              >
                ready
              </span>
            </div>
          </div>

          {/* Body */}
          <div style={{ display: "flex", minHeight: 320 }}>
            {/* Sidebar */}
            <div
              style={{
                ...ss(sidebarProg),
                width: 160,
                borderRight: `1px solid ${COLORS.border}`,
                padding: "18px 16px",
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  fontFamily: "monospace",
                  fontSize: 10,
                  textTransform: "uppercase" as const,
                  letterSpacing: "0.14em",
                  color: COLORS.muted,
                  marginBottom: 14,
                }}
              >
                Sources (3)
              </div>
              {SOURCE_GROUPS.map((src, i) => {
                const p = spring({
                  frame: Math.max(0, frame - 14 - i * 6),
                  fps,
                  config: SPRING_SUBTLE,
                });
                return (
                  <div
                    key={src.label}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 9,
                      marginBottom: 11,
                      opacity: p,
                      transform: `translateX(${interpolate(p, [0, 1], [-6, 0])}px)`,
                    }}
                  >
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 4,
                        background: src.color,
                        flexShrink: 0,
                      }}
                    />
                    <span
                      style={{
                        fontSize: 14,
                        color: COLORS.foreground,
                        fontFamily: "system-ui, sans-serif",
                      }}
                    >
                      {src.label}
                    </span>
                    <span
                      style={{
                        fontSize: 12,
                        color: COLORS.muted,
                        marginLeft: "auto",
                        fontFamily: "monospace",
                      }}
                    >
                      {src.count}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Content */}
            <div style={{ flex: 1, padding: "18px 24px" }}>
              {SECTIONS.map((section, i) => {
                const p = sp(i + 1);
                return (
                  <div key={section.title} style={{ ...ss(p), marginBottom: 16 }}>
                    <div
                      style={{
                        borderLeft: `3px solid ${section.borderColor}`,
                        background: section.bgTint,
                        borderRadius: 6,
                        padding: "14px 18px",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 16,
                          fontWeight: 600,
                          color: COLORS.foreground,
                          fontFamily: "system-ui, sans-serif",
                          marginBottom: 8,
                        }}
                      >
                        {section.title}
                      </div>
                      <div
                        style={{
                          fontSize: 14,
                          color: COLORS.muted,
                          lineHeight: 1.6,
                          fontFamily: "system-ui, sans-serif",
                        }}
                      >
                        {section.bullet ? (
                          <span>
                            <span
                              style={{
                                color: COLORS.primary,
                                fontWeight: 600,
                                marginRight: 8,
                              }}
                            >
                              •
                            </span>
                            {section.content}
                          </span>
                        ) : (
                          section.content
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
