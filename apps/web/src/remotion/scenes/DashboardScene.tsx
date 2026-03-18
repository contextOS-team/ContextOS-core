import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  COLORS,
  SCENE_1_DURATION,
  SPRING_ENTER,
  SPRING_SUBTLE,
} from "../constants";

/* ─────────────────────────────────────────────────────────
 * Scene 1: Ticket Picker — showing the pain point
 *
 *    0ms   empty
 *  ~200ms  card fades in with ticket list
 *  ~600ms  rows stagger in
 * ~1100ms  ENG-421 row selected — single spring drives
 *          background, glow, border, and scale together
 * ~1500ms  non-selected rows dim — visual isolation
 * ~1700ms  dwell — viewer sits with the selected ticket
 * ~2500ms  card fades, selected ticket lifts to center
 *  3000ms  scene ends — ticket card centered for Scene 2 handoff
 * ───────────────────────────────────────────────────────── */

/** Shared ticket header style — must be identical across all 3 scenes */
const TICKET_HEADER = {
  idSize: 19,
  titleSize: 19,
  padding: "14px 26px",
  gap: 12,
} as const;

const TICKETS = [
  { id: "ENG-398", title: "Fix OAuth token refresh on timeout", status: "Review", time: "1d" },
  { id: "ENG-421", title: "Real-time sync for mobile", status: "In Progress", time: "2h" },
  { id: "ENG-435", title: "Dashboard latency > 2s on cold start", status: "Open", time: "4h" },
  { id: "ENG-442", title: "Migrate user prefs to new schema", status: "Open", time: "6h" },
];

const SELECTED_IDX = 1; // ENG-421

export const DashboardScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Card entrance
  const cardProg = spring({ frame, fps, config: SPRING_ENTER });
  const cardScale = interpolate(cardProg, [0, 1], [0.96, 1]);
  const cardOpacity = interpolate(cardProg, [0, 1], [0, 1]);
  const cardY = interpolate(cardProg, [0, 1], [20, 0]);

  // Row staggers
  const rowProg = (i: number) =>
    spring({
      frame: Math.max(0, frame - 6 - i * 5),
      fps,
      config: SPRING_SUBTLE,
    });

  // Fix 2: Single spring for selection — drives bg, glow, border, scale
  const selectProg = spring({
    frame: Math.max(0, frame - 32),
    fps,
    config: SPRING_ENTER,
  });

  // Fix 3: Non-selected rows dim later, giving more dwell time
  const dimOthersProg = interpolate(
    frame,
    [48, 62],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Fix 3: Exit phase starts later — frame 75 instead of 72
  const EXIT_START = SCENE_1_DURATION - 15;

  const othersOpacity = interpolate(
    frame,
    [EXIT_START, SCENE_1_DURATION - 3],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const liftProg = interpolate(
    frame,
    [EXIT_START, SCENE_1_DURATION],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: COLORS.background,
      }}
    >
      {/* Main ticket list card */}
      <div
        style={{
          width: 700,
          opacity: cardOpacity * othersOpacity,
          transform: `translateY(${cardY}px) scale(${cardScale})`,
        }}
      >
        <div
          style={{
            background: COLORS.card,
            border: `1px solid ${COLORS.border}`,
            borderRadius: 14,
            boxShadow: COLORS.cardShadow,
            overflow: "hidden",
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: "14px 24px",
              borderBottom: `1px solid ${COLORS.border}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span
              style={{
                fontSize: 15,
                fontWeight: 600,
                color: COLORS.foreground,
                fontFamily: "system-ui, sans-serif",
              }}
            >
              My Tickets
            </span>
            <span
              style={{
                fontSize: 13,
                color: COLORS.muted,
                fontFamily: "monospace",
              }}
            >
              4 active
            </span>
          </div>

          {/* Ticket rows */}
          <div style={{ padding: "4px 0" }}>
            {TICKETS.map((ticket, i) => {
              const rp = rowProg(i);
              const isSelected = i === SELECTED_IDX;

              // Fix 2: All selection visuals driven by one spring
              const rowScale = isSelected
                ? interpolate(selectProg, [0, 1], [1, 1.01])
                : 1;
              const rowBg = isSelected
                ? interpolate(selectProg, [0, 1], [0, 0.1])
                : 0;
              const borderOpacity = isSelected
                ? interpolate(selectProg, [0, 1], [0, 1])
                : 0;
              const dotGlow = isSelected
                ? interpolate(selectProg, [0, 1], [0, 8])
                : 0;
              const dotGlowAlpha = isSelected
                ? interpolate(selectProg, [0, 1], [0, 0.4])
                : 0;

              // Non-selected rows dim after selection
              const rowDim = isSelected ? 1 : 1 - dimOthersProg * 0.45;

              return (
                <div
                  key={ticket.id}
                  style={{
                    opacity: rp * rowDim,
                    transform: `translateY(${interpolate(rp, [0, 1], [12, 0])}px) scale(${rowScale})`,
                    padding: "12px 24px",
                    display: "flex",
                    alignItems: "center",
                    gap: 14,
                    background: `rgba(0,212,170,${rowBg})`,
                    borderLeft: `3px solid rgba(0,212,170,${borderOpacity})`,
                  }}
                >
                  {/* Status dot */}
                  <span
                    style={{
                      width: 9,
                      height: 9,
                      borderRadius: 5,
                      background: ticket.status === "In Progress"
                        ? COLORS.primary
                        : ticket.status === "Review"
                          ? COLORS.amber
                          : COLORS.muted,
                      flexShrink: 0,
                      boxShadow: dotGlow > 0
                        ? `0 0 ${dotGlow}px rgba(0,212,170,${dotGlowAlpha})`
                        : "none",
                    }}
                  />

                  {/* Ticket ID */}
                  <span
                    style={{
                      fontFamily: "monospace",
                      fontSize: 14,
                      color: COLORS.violet,
                      fontWeight: 600,
                      flexShrink: 0,
                      width: 72,
                    }}
                  >
                    {ticket.id}
                  </span>

                  {/* Title */}
                  <span
                    style={{
                      fontSize: 15,
                      color: COLORS.foreground,
                      fontFamily: "system-ui, sans-serif",
                      flex: 1,
                      opacity: 0.85,
                    }}
                  >
                    {ticket.title}
                  </span>

                  {/* Status label */}
                  <span
                    style={{
                      fontSize: 12,
                      color: ticket.status === "In Progress"
                        ? COLORS.primary
                        : COLORS.muted,
                      fontFamily: "system-ui, sans-serif",
                      fontWeight: 500,
                      flexShrink: 0,
                    }}
                  >
                    {ticket.status}
                  </span>

                  {/* Time */}
                  <span
                    style={{
                      fontSize: 12,
                      color: COLORS.muted,
                      fontFamily: "monospace",
                      flexShrink: 0,
                      width: 28,
                      textAlign: "right",
                    }}
                  >
                    {ticket.time}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Fix 1: Floating ticket header — identical styling to Scene 2 & 3 */}
      {liftProg > 0 && (
        <AbsoluteFill
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              opacity: liftProg,
              transform: `translateY(${interpolate(liftProg, [0, 1], [30, -14])}px) scale(${interpolate(liftProg, [0, 1], [0.92, 1])})`,
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
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
