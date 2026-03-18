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
  SCENE_2_DURATION,
  SPRING_ENTER,
  SPRING_SUBTLE,
} from "../constants";

/* ─────────────────────────────────────────────────────────
 * Scene 2: Zoom into ticket → sources assemble
 *
 *    0ms   ticket header visible at top
 *  ~300ms  first source slides in
 *  ~700ms  second source
 * ~1100ms  third source
 * ~1800ms  "3 sources found" + teal flash
 * ~2600ms  cross-fade out
 * ───────────────────────────────────────────────────────── */

interface Source {
  color: string;
  initial: string;
  label: string;
  text: string;
}

const SOURCES: Source[] = [
  {
    color: COLORS.pink,
    initial: "S",
    label: "Slack",
    text: "Decided on WebSockets over polling",
  },
  {
    color: COLORS.green,
    initial: "G",
    label: "GitHub",
    text: "RFC #147 merged — 4 approvals",
  },
  {
    color: COLORS.blue,
    initial: "J",
    label: "Jira",
    text: "Must ship by Sprint 13",
  },
];

const STAGGER = 14;

export const SourcesScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeOut = interpolate(
    frame,
    [SCENE_2_DURATION - CROSSFADE_FRAMES, SCENE_2_DURATION],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Ticket header entrance
  const headerProg = spring({ frame, fps, config: SPRING_SUBTLE });

  // Counter
  const allIn = 8 + STAGGER * 2 + 18;
  const counterProg = spring({
    frame: Math.max(0, frame - allIn),
    fps,
    config: SPRING_SUBTLE,
  });

  // Flash
  const flashFrame = allIn + 8;
  const flash = interpolate(
    frame,
    [flashFrame, flashFrame + 6, flashFrame + 18],
    [0, 0.4, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Timeline spine — grows downward from ticket to sources
  const spineProg = spring({
    frame: Math.max(0, frame - 6),
    fps,
    config: SPRING_SUBTLE,
  });

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: COLORS.background,
        opacity: fadeOut,
      }}
    >
      {/* Ticket header — wrapped in a card */}
      <div
        style={{
          opacity: headerProg,
          transform: `translateY(${interpolate(headerProg, [0, 1], [10, 0])}px)`,
          marginBottom: 0,
        }}
      >
        <div
          style={{
            background: COLORS.card,
            border: `1px solid ${COLORS.border}`,
            borderRadius: 12,
            padding: "14px 24px",
            display: "flex",
            alignItems: "center",
            gap: 12,
            boxShadow: COLORS.cardShadow,
          }}
        >
          <span
            style={{
              fontFamily: "monospace",
              fontSize: 18,
              color: COLORS.primary,
              fontWeight: 600,
            }}
          >
            ENG-421
          </span>
          <span style={{ color: COLORS.border, fontSize: 18 }}>·</span>
          <span
            style={{
              fontSize: 18,
              color: COLORS.foreground,
              fontFamily: "system-ui, sans-serif",
              fontWeight: 500,
            }}
          >
            Real-time sync for mobile
          </span>
        </div>
      </div>

      {/* Timeline spine */}
      <div
        style={{
          width: 1,
          height: interpolate(spineProg, [0, 1], [0, 28]),
          background: `rgba(0,212,170,${interpolate(spineProg, [0, 1], [0, 0.2])})`,
          marginBottom: 0,
        }}
      />

      {/* Sources */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 12,
          width: 520,
        }}
      >
        {SOURCES.map((src, i) => {
          const delay = 8 + i * STAGGER;
          const p = spring({
            frame: Math.max(0, frame - delay),
            fps,
            config: SPRING_ENTER,
          });
          const tx = i % 2 === 0
            ? interpolate(p, [0, 1], [-60, 0])
            : interpolate(p, [0, 1], [60, 0]);

          return (
            <div
              key={src.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 14,
                background: COLORS.card,
                border: `1px solid ${COLORS.border}`,
                borderRadius: 12,
                padding: "14px 20px",
                opacity: p,
                transform: `translateX(${tx}px)`,
                boxShadow: COLORS.cardShadow,
              }}
            >
              {/* Badge */}
              <div
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 17,
                  background: `${src.color}15`,
                  border: `1px solid ${src.color}30`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <span
                  style={{
                    fontSize: 15,
                    fontWeight: 700,
                    color: src.color,
                    fontFamily: "system-ui, sans-serif",
                  }}
                >
                  {src.initial}
                </span>
              </div>

              {/* Text */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 600,
                    color: src.color,
                    fontFamily: "monospace",
                    textTransform: "uppercase" as const,
                    letterSpacing: "0.12em",
                    marginBottom: 3,
                  }}
                >
                  {src.label}
                </div>
                <div
                  style={{
                    fontSize: 15,
                    color: COLORS.foreground,
                    fontFamily: "system-ui, sans-serif",
                    opacity: 0.85,
                  }}
                >
                  {src.text}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Counter */}
      <div
        style={{
          marginTop: 28,
          opacity: counterProg,
          transform: `scale(${interpolate(counterProg, [0, 1], [0.95, 1])})`,
        }}
      >
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 14,
            color: COLORS.primary,
            letterSpacing: "0.08em",
          }}
        >
          3 sources found
        </span>
      </div>

      {/* Flash */}
      {flash > 0.01 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(ellipse at center, rgba(0,212,170,${flash * 0.2}) 0%, transparent 60%)`,
            pointerEvents: "none" as const,
          }}
        />
      )}
    </AbsoluteFill>
  );
};
