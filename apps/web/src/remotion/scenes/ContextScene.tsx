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
 *    0ms   card shell appears (header handed off from Scene 2)
 *  ~300ms  sidebar sources stagger in
 *  ~600ms  Summary section
 *  ~900ms  Key Decisions section
 * ~1000ms  "ready" badge fades in
 * ~1200ms  Requirements section
 * ~1700ms  "ready" badge breathes teal
 * ~3600ms  cross-fade out
 * ───────────────────────────────────────────────────────── */

/** Shared ticket header style — must be identical across all 3 scenes */
const TICKET_HEADER = {
  idSize: 19,
  titleSize: 19,
  gap: 12,
} as const;

const SECTION_STAGGER = STAGGER_FRAMES * 5;

const SOURCE_GROUPS = [
  { label: "Slack", count: "1" },
  { label: "GitHub", count: "1" },
  { label: "Jira", count: "1" },
];

const SECTIONS = [
  {
    title: "Summary",
    borderColor: COLORS.primary,
    bgTint: "rgba(0,212,170,0.04)",
    lines: [
      "Team decided on WebSockets over polling for real-time sync.",
      "RFC approved with 4 reviewers.",
    ],
  },
  {
    title: "Key Decisions",
    borderColor: COLORS.violet,
    bgTint: "transparent",
    lines: [
      "WebSocket protocol selected — lower latency than polling approach",
    ],
  },
  {
    title: "Requirements",
    borderColor: COLORS.amber,
    bgTint: "transparent",
    lines: [
      "Must ship by Sprint 13 — mobile client dependency",
    ],
  },
];

export const ContextScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeOut = interpolate(
    frame,
    [SCENE_3_DURATION - CROSSFADE_FRAMES, SCENE_3_DURATION],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const sp = (i: number) =>
    spring({
      frame: Math.max(0, frame - 8 - i * SECTION_STAGGER),
      fps,
      config: SPRING_SUBTLE,
    });

  const ss = (p: number): React.CSSProperties => ({
    opacity: p,
    transform: `translateY(${interpolate(p, [0, 1], [14, 0])}px)`,
  });

  const sidebarProg = sp(0);

  // Fix 5: "ready" badge fades in separately at frame 35
  const badgeProg = spring({
    frame: Math.max(0, frame - 35),
    fps,
    config: SPRING_ENTER,
  });

  // Breathing glow starts at frame 50 (right after badge appears)
  const breathCycle = Math.max(0, frame - 50);
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
      <div style={{ width: 920 }}>
        <div
          style={{
            background: COLORS.card,
            border: `1px solid ${COLORS.border}`,
            borderRadius: 14,
            boxShadow: `${COLORS.cardShadow}, 0 0 60px rgba(0,212,170,0.04)`,
            overflow: "hidden",
          }}
        >
          {/* Fix 1: Header — identical ticket header styling */}
          <div
            style={{
              padding: "20px 28px",
              borderBottom: `1px solid ${COLORS.border}`,
              background: COLORS.elevated,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: TICKET_HEADER.gap }}>
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: TICKET_HEADER.idSize,
                  color: COLORS.violet,
                  fontWeight: 600,
                }}
              >
                ENG-421
              </span>
              <span
                style={{
                  fontSize: TICKET_HEADER.titleSize,
                  fontWeight: 600,
                  color: COLORS.foreground,
                  fontFamily: "system-ui, sans-serif",
                }}
              >
                Real-time sync for mobile
              </span>
            </div>
            {/* Fix 5: Status badge fades in separately, then breathes */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                background: "rgba(0,212,170,0.1)",
                borderRadius: 20,
                padding: "5px 14px",
                opacity: badgeProg,
                transform: `scale(${interpolate(badgeProg, [0, 1], [0.9, 1])})`,
                boxShadow: breathGlow > 0
                  ? `0 0 ${breathGlow * 18}px rgba(0,212,170,${breathGlow * 0.4})`
                  : "none",
              }}
            >
              <span
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: 4,
                  background: COLORS.primary,
                  boxShadow: breathGlow > 0
                    ? `0 0 ${breathGlow * 10}px ${COLORS.primary}`
                    : "none",
                }}
              />
              <span
                style={{ fontSize: 14, color: COLORS.primary, fontWeight: 500 }}
              >
                ready
              </span>
            </div>
          </div>

          {/* Body */}
          <div style={{ display: "flex", minHeight: 300 }}>
            {/* Sidebar */}
            <div
              style={{
                ...ss(sidebarProg),
                width: 180,
                borderRight: `1px solid ${COLORS.border}`,
                padding: "20px 20px",
                flexShrink: 0,
              }}
            >
              <div
                style={{
                  fontFamily: "monospace",
                  fontSize: 11,
                  textTransform: "uppercase" as const,
                  letterSpacing: "0.14em",
                  color: COLORS.muted,
                  marginBottom: 16,
                }}
              >
                Sources (3)
              </div>
              {SOURCE_GROUPS.map((src, i) => {
                const p = spring({
                  frame: Math.max(0, frame - 14 - i * 7),
                  fps,
                  config: SPRING_SUBTLE,
                });
                return (
                  <div
                    key={src.label}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      marginBottom: 13,
                      opacity: p,
                      transform: `translateX(${interpolate(p, [0, 1], [-8, 0])}px)`,
                    }}
                  >
                    <span
                      style={{
                        width: 9,
                        height: 9,
                        borderRadius: 5,
                        background: COLORS.amber,
                        flexShrink: 0,
                      }}
                    />
                    <span
                      style={{
                        fontSize: 15,
                        color: COLORS.foreground,
                        fontFamily: "system-ui, sans-serif",
                      }}
                    >
                      {src.label}
                    </span>
                    <span
                      style={{
                        fontSize: 13,
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
            <div style={{ flex: 1, padding: "20px 28px" }}>
              {SECTIONS.map((section, i) => {
                const p = sp(i + 1);
                return (
                  <div key={section.title} style={{ ...ss(p), marginBottom: 18 }}>
                    <div
                      style={{
                        borderLeft: `3px solid ${section.borderColor}`,
                        background: section.bgTint,
                        borderRadius: 8,
                        padding: "16px 20px",
                      }}
                    >
                      <div
                        style={{
                          fontSize: 17,
                          fontWeight: 600,
                          color: COLORS.foreground,
                          fontFamily: "system-ui, sans-serif",
                          marginBottom: 10,
                        }}
                      >
                        {section.title}
                      </div>
                      {section.lines.map((line, li) => (
                        <div
                          key={li}
                          style={{
                            fontSize: 14,
                            color: COLORS.foreground,
                            fontFamily: "system-ui, sans-serif",
                            opacity: 0.75,
                            lineHeight: "1.6",
                            marginBottom: li < section.lines.length - 1 ? 5 : 0,
                          }}
                        >
                          {line}
                        </div>
                      ))}
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
