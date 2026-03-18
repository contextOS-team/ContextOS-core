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
} from "../constants";

/* ─────────────────────────────────────────────────────────
 * Scene 2: Ticket header + sources fly in
 *
 *    0ms   ENG-421 header already visible (handed off from Scene 1)
 *  ~400ms  Slack source slides up from below
 *  ~900ms  GitHub source slides up
 * ~1400ms  Jira source slides up
 * ~3000ms  sources fade, header scales up for Scene 3 handoff
 * ───────────────────────────────────────────────────────── */

/** Shared ticket header style — must be identical across all 3 scenes */
const TICKET_HEADER = {
  idSize: 19,
  titleSize: 19,
  padding: "14px 26px",
  gap: 12,
} as const;

interface Source {
  label: string;
  text: string;
  logo: React.ReactNode;
}

const SOURCES: Source[] = [
  {
    label: "Slack",
    text: "Decided on WebSockets over polling",
    logo: (
      <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
        <path d="M53.841 161.321c0 14.832-11.987 26.819-26.819 26.819S.203 176.153.203 161.321c0-14.832 11.987-26.819 26.82-26.819h26.818v26.819zm13.41 0c0-14.832 11.987-26.819 26.819-26.819s26.819 11.987 26.819 26.82v67.047c0 14.831-11.987 26.818-26.82 26.818-14.83 0-26.818-11.987-26.818-26.818v-67.048z" fill="#E01E5A" />
        <path d="M94.07 53.638c-14.832 0-26.82-11.987-26.82-26.819C67.25 11.987 79.239 0 94.07 0s26.819 11.987 26.819 26.819v26.82H94.07zm0 13.613c14.832 0 26.819 11.987 26.819 26.819s-11.987 26.819-26.82 26.819H26.82C11.987 120.889 0 108.902 0 94.07c0-14.832 11.987-26.82 26.819-26.82h67.25z" fill="#36C5F0" />
        <path d="M201.549 94.07c0-14.832 11.988-26.82 26.82-26.82 14.83 0 26.818 11.988 26.818 26.82s-11.987 26.819-26.819 26.819h-26.819V94.07zm-13.41 0c0 14.831-11.987 26.819-26.819 26.819s-26.819-11.988-26.819-26.82V26.82C134.501 11.987 146.489 0 161.32 0c14.832 0 26.82 11.987 26.82 26.819v67.25z" fill="#2EB67D" />
        <path d="M161.321 201.549c14.831 0 26.819 11.988 26.819 26.82 0 14.83-11.988 26.818-26.82 26.818-14.83 0-26.818-11.987-26.818-26.819v-26.819h26.819zm0-13.41c-14.832 0-26.82-11.987-26.82-26.819s11.988-26.819 26.82-26.819h67.25c14.832 0 26.82 11.988 26.82 26.82 0 14.83-11.988 26.818-26.82 26.818h-67.25z" fill="#ECB22E" />
      </svg>
    ),
  },
  {
    label: "GitHub",
    text: "RFC #147 merged — 4 approvals",
    logo: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836a9.59 9.59 0 0 1 2.504.337c1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10Z" fill="white" />
      </svg>
    ),
  },
  {
    label: "Jira",
    text: "Must ship by Sprint 13",
    logo: (
      <svg width="20" height="20" viewBox="0 0 256 256" fill="none">
        <path d="M244.658 0H121.707a55.502 55.502 0 0 0 55.502 55.502h22.649V77.37c.02 30.625 24.841 55.447 55.5 55.502V10.993C255.358 4.923 250.228 0 244.658 0Z" fill="#2684FF" />
        <path d="M183.822 61.262H60.872c.019 30.625 24.84 55.447 55.501 55.502h22.649v21.868c.02 30.597 24.798 55.408 55.396 55.501V72.255c0-6.075-5.13-10.993-10.596-10.993Z" fill="#2684FF" opacity="0.8" />
        <path d="M122.943 122.524H0c0 30.653 24.86 55.502 55.502 55.502h22.72v21.868c.02 30.597 24.798 55.408 55.396 55.502V133.518c0-6.076-5.13-10.994-10.675-10.994Z" fill="#2684FF" opacity="0.65" />
      </svg>
    ),
  },
];

const STAGGER = 16;

export const SourcesScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // --- Exit phase: sources fade, header scales up for Scene 3 ---
  const EXIT_START = SCENE_2_DURATION - CROSSFADE_FRAMES;
  const exitProg = interpolate(
    frame,
    [EXIT_START, SCENE_2_DURATION],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );
  const sourcesExitOpacity = interpolate(exitProg, [0, 1], [1, 0]);
  const headerExitScale = interpolate(exitProg, [0, 1], [1, 1.03]);
  const headerExitOpacity = interpolate(
    frame,
    [SCENE_2_DURATION - 4, SCENE_2_DURATION],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: COLORS.background,
      }}
    >
      {/* Fix 1: Ticket header — identical styling to Scene 1 & 3 */}
      <div
        style={{
          opacity: headerExitOpacity,
          transform: `scale(${headerExitScale})`,
          marginBottom: 36,
        }}
      >
        <div
          style={{
            background: COLORS.card,
            border: `1px solid ${COLORS.border}`,
            borderRadius: 14,
            padding: TICKET_HEADER.padding,
            display: "flex",
            alignItems: "center",
            gap: TICKET_HEADER.gap,
            boxShadow: COLORS.cardShadow,
          }}
        >
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
          <span style={{ color: COLORS.border, fontSize: TICKET_HEADER.titleSize }}>·</span>
          <span
            style={{
              fontSize: TICKET_HEADER.titleSize,
              color: COLORS.foreground,
              fontFamily: "system-ui, sans-serif",
              fontWeight: 500,
            }}
          >
            Real-time sync for mobile
          </span>
        </div>
      </div>

      {/* Sources — all slide up from below (unified direction) */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          width: 580,
          opacity: sourcesExitOpacity,
        }}
      >
        {SOURCES.map((src, i) => {
          const delay = 10 + i * STAGGER;
          const p = spring({
            frame: Math.max(0, frame - delay),
            fps,
            config: SPRING_ENTER,
          });
          const ty = interpolate(p, [0, 1], [40, 0]);

          return (
            <div
              key={src.label}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 16,
                background: COLORS.card,
                border: `1px solid ${COLORS.border}`,
                borderRadius: 14,
                padding: "16px 24px",
                opacity: p,
                transform: `translateY(${ty}px)`,
                boxShadow: COLORS.cardShadow,
              }}
            >
              {/* Logo badge */}
              <div
                style={{
                  width: 42,
                  height: 42,
                  borderRadius: 21,
                  background: `${COLORS.amber}14`,
                  border: `1px solid ${COLORS.amber}28`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                {src.logo}
              </div>

              {/* Text */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: COLORS.amber,
                    fontFamily: "monospace",
                    textTransform: "uppercase" as const,
                    letterSpacing: "0.12em",
                    marginBottom: 4,
                  }}
                >
                  {src.label}
                </div>
                <div
                  style={{
                    fontSize: 16,
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
    </AbsoluteFill>
  );
};
