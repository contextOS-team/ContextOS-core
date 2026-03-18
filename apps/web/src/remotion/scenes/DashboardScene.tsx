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
  STAGGER_FRAMES,
} from "../constants";

/* ─────────────────────────────────────────────────────────
 * Scene 1: Dashboard — the product at a glance
 *
 *    0ms   empty
 *  ~200ms  greeting + widgets stagger in
 * ~1700ms  ENG-421 row pulses teal
 * ~2600ms  cross-fade out
 * ───────────────────────────────────────────────────────── */

const WIDGET_STAGGER = STAGGER_FRAMES * 3;

export const DashboardScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enterProg = spring({ frame, fps, config: SPRING_ENTER });
  const zoom = interpolate(enterProg, [0, 1], [1.06, 1]);
  const enterOpacity = interpolate(enterProg, [0, 1], [0, 1]);

  const fadeOut = interpolate(
    frame,
    [SCENE_1_DURATION - 12, SCENE_1_DURATION],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const wp = (i: number) =>
    spring({
      frame: Math.max(0, frame - 4 - i * WIDGET_STAGGER),
      fps,
      config: SPRING_SUBTLE,
    });

  const ws = (i: number): React.CSSProperties => {
    const p = wp(i);
    return {
      opacity: p,
      transform: `translateY(${interpolate(p, [0, 1], [8, 0])}px)`,
    };
  };

  // Pulse on ENG-421 row — starts at frame 32 (~1s), holds longer
  const pulse = interpolate(
    frame,
    [32, 42, 60, 78],
    [0, 0.8, 0.5, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Bar chart
  const bars = [0.3, 0.6, 1, 0.45, 0.7, 0.2, 0];
  const dayLabels = ["M", "T", "W", "T", "F", "S", "S"];

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
          width: 880,
          transform: `scale(${zoom})`,
          opacity: enterOpacity,
        }}
      >
        {/* Greeting */}
        <div style={{ ...ws(0), marginBottom: 20 }}>
          <div
            style={{
              fontSize: 22,
              fontWeight: 600,
              color: COLORS.foreground,
              fontFamily: "system-ui, sans-serif",
            }}
          >
            Good morning, Alex
          </div>
          <div
            style={{
              fontSize: 14,
              color: COLORS.muted,
              fontFamily: "system-ui, sans-serif",
              marginTop: 4,
            }}
          >
            2 items need attention
          </div>
        </div>

        {/* 2-col */}
        <div style={{ display: "flex", gap: 16 }}>
          {/* Left */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Needs Attention */}
            <div style={ws(1)}>
              <Card label="Needs Attention">
                <Row
                  dotColor={COLORS.amber}
                  left="ENG-421"
                  text="Real-time sync — context missing"
                  right="2h"
                  highlight={pulse}
                />
                <Row
                  dotColor={COLORS.muted}
                  left="ENG-398"
                  text="Auth flow — PR awaiting review"
                  right="1d"
                />
              </Card>
            </div>

            {/* This Week */}
            <div style={ws(2)}>
              <Card label="This Week">
                <div
                  style={{
                    display: "flex",
                    alignItems: "flex-end",
                    gap: 10,
                    height: 56,
                  }}
                >
                  {bars.map((v, i) => {
                    const bp = wp(2);
                    const h = v * 48 * bp;
                    const isWed = i === 2;
                    return (
                      <div
                        key={i}
                        style={{
                          flex: 1,
                          display: "flex",
                          flexDirection: "column",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <div
                          style={{
                            width: "100%",
                            maxWidth: 22,
                            height: Math.max(h, v > 0 ? 2 : 0),
                            borderRadius: 3,
                            background: isWed
                              ? COLORS.emerald
                              : v > 0
                                ? `${COLORS.emerald}40`
                                : "transparent",
                          }}
                        />
                        <span
                          style={{
                            fontSize: 10,
                            color: isWed ? COLORS.emerald : COLORS.muted,
                            fontFamily: "monospace",
                          }}
                        >
                          {dayLabels[i]}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </Card>
            </div>
          </div>

          {/* Right */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
            {/* Activity */}
            <div style={ws(1)}>
              <Card label="Recent Activity" action="View all">
                <ActivityRow
                  initial="S"
                  color={COLORS.pink}
                  text="@maya mentioned ENG-421"
                  time="12m"
                />
                <ActivityRow
                  initial="G"
                  color={COLORS.green}
                  text="PR #147 merged"
                  time="1h"
                />
                <ActivityRow
                  initial="L"
                  color={COLORS.violet}
                  text="ENG-421 → In Progress"
                  time="3h"
                />
              </Card>
            </div>

            {/* Graph */}
            <div style={ws(2)}>
              <Card label="My Work" action="View graph →">
                <MiniGraph frame={frame} fps={fps} />
              </Card>
            </div>
          </div>
        </div>

        {/* Integration dots */}
        <div
          style={{
            ...ws(3),
            display: "flex",
            justifyContent: "center",
            gap: 22,
            marginTop: 18,
          }}
        >
          {["Linear", "GitHub", "Slack", "Jira", "Telegram"].map((n) => (
            <div
              key={n}
              style={{ display: "flex", alignItems: "center", gap: 5 }}
            >
              <span
                style={{
                  width: 5,
                  height: 5,
                  borderRadius: 3,
                  background: COLORS.emerald,
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  color: COLORS.muted,
                  fontFamily: "monospace",
                }}
              >
                {n}
              </span>
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ---- Sub-components ---- */

const Card: React.FC<{
  label: string;
  action?: string;
  children: React.ReactNode;
}> = ({ label, action, children }) => (
  <div
    style={{
      background: COLORS.card,
      border: `1px solid ${COLORS.border}`,
      borderRadius: 12,
      padding: "14px 16px",
      boxShadow: COLORS.cardShadow,
    }}
  >
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        marginBottom: 10,
      }}
    >
      <span
        style={{
          fontFamily: "monospace",
          fontSize: 10,
          textTransform: "uppercase" as const,
          letterSpacing: "0.14em",
          color: COLORS.muted,
        }}
      >
        {label}
      </span>
      {action && (
        <span style={{ fontSize: 10, color: `${COLORS.muted}80` }}>
          {action}
        </span>
      )}
    </div>
    {children}
  </div>
);

const Row: React.FC<{
  dotColor: string;
  left: string;
  text: string;
  right: string;
  highlight?: number;
}> = ({ dotColor, left, text, right, highlight = 0 }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "6px 0",
      borderRadius: 6,
      background:
        highlight > 0 ? `rgba(0,212,170,${highlight * 0.08})` : "transparent",
    }}
  >
    <span
      style={{
        width: 7,
        height: 7,
        borderRadius: 4,
        background: dotColor,
        flexShrink: 0,
        boxShadow:
          highlight > 0
            ? `0 0 ${highlight * 12}px rgba(0,212,170,${highlight * 0.5})`
            : "none",
      }}
    />
    <span
      style={{
        fontFamily: "monospace",
        fontSize: 12,
        color: COLORS.primary,
        fontWeight: 600,
        flexShrink: 0,
      }}
    >
      {left}
    </span>
    <span
      style={{
        fontSize: 13,
        color: COLORS.foreground,
        fontFamily: "system-ui, sans-serif",
        flex: 1,
        opacity: 0.8,
      }}
    >
      {text}
    </span>
    <span
      style={{
        fontSize: 11,
        color: COLORS.muted,
        fontFamily: "monospace",
        flexShrink: 0,
      }}
    >
      {right}
    </span>
  </div>
);

const ActivityRow: React.FC<{
  initial: string;
  color: string;
  text: string;
  time: string;
}> = ({ initial, color, text, time }) => (
  <div
    style={{
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "5px 0",
    }}
  >
    <div
      style={{
        width: 22,
        height: 22,
        borderRadius: 11,
        background: `${color}18`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      <span
        style={{
          fontSize: 11,
          fontWeight: 700,
          color,
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {initial}
      </span>
    </div>
    <span
      style={{
        fontSize: 13,
        color: COLORS.foreground,
        fontFamily: "system-ui, sans-serif",
        flex: 1,
        opacity: 0.8,
      }}
    >
      {text}
    </span>
    <span
      style={{
        fontSize: 10,
        color: COLORS.muted,
        fontFamily: "monospace",
        flexShrink: 0,
      }}
    >
      {time}
    </span>
  </div>
);

const MiniGraph: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const nodes = [
    { x: 55, y: 30, color: COLORS.violet, shape: "rect" as const },
    { x: 135, y: 55, color: COLORS.amber, shape: "diamond" as const },
    { x: 90, y: 90, color: COLORS.pink, shape: "circle" as const },
    { x: 180, y: 35, color: COLORS.green, shape: "circle" as const },
  ];
  const edges = [
    [0, 1],
    [0, 2],
    [1, 3],
    [2, 1],
  ];

  return (
    <svg width="100%" height="110" viewBox="0 0 230 110">
      {edges.map(([a, b], i) => (
        <line
          key={i}
          x1={nodes[a].x}
          y1={nodes[a].y}
          x2={nodes[b].x}
          y2={nodes[b].y}
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={1}
        />
      ))}
      {nodes.map((n, i) => {
        const np = spring({
          frame: Math.max(0, frame - 8 - i * 5),
          fps,
          config: SPRING_SUBTLE,
        });
        const s = interpolate(np, [0, 1], [0, 1]);
        if (n.shape === "rect") {
          const sz = 12 * s;
          return (
            <rect
              key={i}
              x={n.x - sz / 2}
              y={n.y - sz / 2}
              width={sz}
              height={sz}
              rx={2}
              fill={n.color}
              opacity={np * 0.9}
            />
          );
        }
        if (n.shape === "diamond") {
          const sz = 10 * s;
          return (
            <rect
              key={i}
              x={n.x - sz / 2}
              y={n.y - sz / 2}
              width={sz}
              height={sz}
              rx={1}
              fill={n.color}
              opacity={np * 0.9}
              transform={`rotate(45 ${n.x} ${n.y})`}
            />
          );
        }
        return (
          <circle
            key={i}
            cx={n.x}
            cy={n.y}
            r={6 * s}
            fill={n.color}
            opacity={np * 0.9}
          />
        );
      })}
    </svg>
  );
};
