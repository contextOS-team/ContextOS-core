import type { CSSProperties, ReactNode } from "react";
import {
  AbsoluteFill,
  Easing,
  interpolate,
  spring,
  type SpringConfig,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  COLORS,
  CONTEXTOS_PRODUCT_DEMO_DURATION,
  SPRING_ENTER,
  SPRING_SUBTLE,
} from "../constants";

/* --------------------------------------------------------------------------
 * ANIMATION STORYBOARD
 *
 * Read top-to-bottom. Each value is ms from the start of the loop.
 *
 *    0ms   focused ContextOS answer surface is already visible
 *  600ms   Ask ContextOS prompt comes into focus
 * 1050ms   question types: Why did we choose WebSockets?
 * 2550ms   two citations appear beside the answer
 * 3650ms   Answer resolves with the decision rationale
 * 5600ms   one citation opens to show the real source line
 * 7350ms   final state holds without adding more product surfaces
 * ------------------------------------------------------------------------ */

const clamp = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;

const TIMING = {
  shellIn:     0,    // product surface settles
  askFocus:    600,  // question panel receives focus
  typing:      1050, // question text types in
  citations:   2550, // source citations appear
  answer:      3650, // answer card resolves
  sourceOpen:  5600, // one source preview opens
  hold:        7350, // final focused state holds
};

const SHELL = {
  left: 44,
  top: 36,
  width: 1192,
  height: 648,
  radius: 22,
  spring: SPRING_ENTER,
};

const ASK = {
  question: "Why did we choose WebSockets?",
  label: "Ask ContextOS",
  spring: { damping: 20, stiffness: 120, mass: 0.9 },
};

const ANSWER = {
  title: "Answer",
  body: "We chose WebSockets because mobile sync needed sub-500ms updates during incident triage. Polling kept state stale between deploys.",
  spring: SPRING_SUBTLE,
};

const citations = [
  {
    index: 1,
    label: "Slack",
    place: "#eng-mobile",
    quote: "Polling leaves mobile behind after deploys.",
    accent: "#36C5F0",
  },
  {
    index: 2,
    label: "GitHub",
    place: "PR #418",
    quote: "Socket transport approved for live sync.",
    accent: "#EAEAF0",
  },
] as const;

const msToFrame = (ms: number, fps: number) => Math.round((ms / 1000) * fps);

const progress = (
  frame: number,
  fps: number,
  startMs: number,
  endMs: number,
  easing = Easing.out(Easing.cubic),
) =>
  interpolate(
    frame,
    [msToFrame(startMs, fps), msToFrame(endMs, fps)],
    [0, 1],
    { ...clamp, easing },
  );

const springAt = (
  frame: number,
  fps: number,
  startMs: number,
  config: Partial<SpringConfig>,
) =>
  spring({
    frame: frame - msToFrame(startMs, fps),
    fps,
    config,
  });

const typewriterText = (
  value: string,
  frame: number,
  fps: number,
  startMs: number,
  endMs: number,
) => {
  const amount = progress(frame, fps, startMs, endMs, Easing.linear);
  return value.slice(0, Math.max(1, Math.floor(amount * value.length)));
};

const Label = ({ children }: { children: ReactNode }) => (
  <div
    style={{
      color: COLORS.muted,
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      fontSize: 11,
      letterSpacing: "0.13em",
      textTransform: "uppercase",
    }}
  >
    {children}
  </div>
);

const Badge = ({
  children,
  active,
  style,
}: {
  children: ReactNode;
  active?: boolean;
  style?: CSSProperties;
}) => (
  <span
    style={{
      display: "inline-flex",
      alignItems: "center",
      borderRadius: 999,
      border: `1px solid ${active ? "rgba(0,209,156,0.38)" : "rgba(255,255,255,0.08)"}`,
      background: active ? "rgba(0,209,156,0.1)" : "rgba(255,255,255,0.035)",
      color: active ? COLORS.primary : COLORS.muted,
      padding: "7px 11px",
      fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
      fontSize: 11,
      lineHeight: 1,
      ...style,
    }}
  >
    {children}
  </span>
);

const CitationPill = ({
  citation,
  visible,
}: {
  citation: (typeof citations)[number];
  visible: number;
}) => (
  <div
    style={{
      opacity: visible,
      transform: `translateY(${interpolate(visible, [0, 1], [14, 0])}px)`,
      display: "flex",
      alignItems: "center",
      gap: 10,
      borderRadius: 16,
      border: "1px solid rgba(255,255,255,0.07)",
      background: "rgba(255,255,255,0.04)",
      padding: "12px 13px",
    }}
  >
    <span
      style={{
        width: 24,
        height: 24,
        display: "grid",
        placeItems: "center",
        borderRadius: 999,
        background: "rgba(0,209,156,0.1)",
        color: COLORS.primary,
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        fontSize: 13,
      }}
    >
      {citation.index}
    </span>
    <div style={{ minWidth: 0 }}>
      <div style={{ color: COLORS.foreground, fontSize: 15, fontWeight: 680 }}>
        {citation.label}
      </div>
      <div
        style={{
          marginTop: 3,
          color: "#AEB6C2",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSize: 12,
        }}
      >
        {citation.place}
      </div>
    </div>
  </div>
);

export const ContextOSProductDemoScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const shell = springAt(frame, fps, TIMING.shellIn, SHELL.spring);
  const ask = springAt(frame, fps, TIMING.askFocus, ASK.spring);
  const answer = springAt(frame, fps, TIMING.answer, ANSWER.spring);
  const answerFocus = progress(frame, fps, TIMING.answer, TIMING.answer + 720);
  const citationResolve = progress(
    frame,
    fps,
    TIMING.citations + 560,
    TIMING.answer - 120,
  );
  const sourceOpen = progress(frame, fps, TIMING.sourceOpen, TIMING.sourceOpen + 620);
  const holdGlow = progress(frame, fps, TIMING.hold, TIMING.hold + 900);
  const typedQuestion = typewriterText(
    ASK.question,
    frame,
    fps,
    TIMING.typing,
    TIMING.typing + 900,
  );
  const endSoftener = interpolate(
    frame,
    [CONTEXTOS_PRODUCT_DEMO_DURATION - 22, CONTEXTOS_PRODUCT_DEMO_DURATION],
    [1, 0.94],
    clamp,
  );

  return (
    <AbsoluteFill
      style={{
        background: COLORS.background,
        color: COLORS.foreground,
        fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        overflow: "hidden",
        opacity: endSoftener,
      }}
    >
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.026) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.026) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          opacity: 0.24,
        }}
      />

      <div
        style={{
          position: "absolute",
          left: SHELL.left,
          top: SHELL.top,
          width: SHELL.width,
          height: SHELL.height,
          opacity: 1,
          transform: `scale(${interpolate(shell, [0, 1], [0.99, 1])})`,
          borderRadius: SHELL.radius,
          border: "1px solid rgba(255,255,255,0.075)",
          background: "rgba(9,10,15,0.96)",
          boxShadow: `0 22px 80px rgba(0,0,0,0.48), 0 0 ${holdGlow * 48}px rgba(0,209,156,0.1)`,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: 54,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: "1px solid rgba(255,255,255,0.065)",
            padding: "0 22px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 9,
                border: "1px solid rgba(0,209,156,0.48)",
                background: "rgba(0,209,156,0.08)",
              }}
            />
            <div style={{ fontSize: 18, fontWeight: 720 }}>ContextOS</div>
          </div>
          <Badge active>Citations on</Badge>
        </div>

        <main
          style={{
            height: SHELL.height - 54,
            display: "grid",
            gridTemplateColumns: "minmax(0, 1fr) 300px",
            gap: 20,
            padding: 28,
          }}
        >
          <section>
            <div
              style={{
                borderRadius: 24,
                border: `1px solid rgba(0,209,156,${0.16 + ask * 0.16})`,
                background: "rgba(255,255,255,0.04)",
                boxShadow: `0 0 ${ask * 18}px rgba(0,209,156,0.1)`,
                opacity: 1 - answerFocus * 0.28,
                padding: "22px 24px",
                transform: `translateY(${interpolate(ask, [0, 1], [14, 0])}px) scale(${interpolate(answerFocus, [0, 1], [1, 0.975])})`,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
                <Label>{ASK.label}</Label>
                <Badge active>workspace-scoped</Badge>
              </div>
              <div
                style={{
                  marginTop: 18,
                  minHeight: 54,
                  color: COLORS.foreground,
                  fontSize: interpolate(answerFocus, [0, 1], [31, 24]),
                  lineHeight: 1.16,
                  fontWeight: 760,
                }}
              >
                {typedQuestion}
                <span style={{ color: COLORS.primary }}>
                  {frame % 24 < 12 ? "|" : ""}
                </span>
              </div>
            </div>

            <div
              style={{
                marginTop: 24,
                borderRadius: 26,
                border: "1px solid rgba(255,255,255,0.075)",
                background: "linear-gradient(180deg, rgba(18,19,30,0.94), rgba(12,13,20,0.94))",
                boxShadow: "0 18px 48px rgba(0,0,0,0.34)",
                padding: "25px 27px 27px",
                opacity: answer,
                transform: `translateY(${interpolate(answer, [0, 1], [28, 0])}px)`,
              }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <Label>{ANSWER.title}</Label>
                <Badge active>Citations</Badge>
              </div>
              <div
                style={{
                  marginTop: 16,
                  color: COLORS.foreground,
                  fontSize: interpolate(answerFocus, [0, 1], [28, 32]),
                  lineHeight: 1.18,
                  fontWeight: 750,
                  maxWidth: 680,
                }}
              >
                {ANSWER.body}
              </div>
              <div
                style={{
                  marginTop: 20,
                  display: "flex",
                  gap: 10,
                  color: COLORS.muted,
                  fontSize: 13,
                }}
              >
                <Badge>Opened from ENG-421</Badge>
                <Badge>2 sources</Badge>
              </div>
            </div>
          </section>

          <aside>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <Label>Citations</Label>
              <Badge active>
                {citationResolve > 0.96 ? "2 found" : "Resolving citations"}
              </Badge>
            </div>

            <div style={{ marginTop: 16, display: "grid", gap: 11 }}>
              {citations.map((citation, index) => {
                const visible = progress(
                  frame,
                  fps,
                  TIMING.citations + index * 180,
                  TIMING.citations + 420 + index * 180,
                );
                return (
                  <CitationPill
                    key={citation.label}
                    citation={citation}
                    visible={visible}
                  />
                );
              })}
            </div>

            <div
              style={{
                marginTop: 18,
                opacity: sourceOpen,
                transform: `translateY(${interpolate(sourceOpen, [0, 1], [18, 0])}px)`,
                borderRadius: 18,
                border: "1px solid rgba(255,255,255,0.075)",
                background: "rgba(255,255,255,0.04)",
                padding: 16,
              }}
            >
              <Label>Source line</Label>
              <div
                style={{
                  marginTop: 13,
                  color: COLORS.foreground,
                  fontSize: 16,
                  lineHeight: 1.42,
                  fontWeight: 620,
                }}
              >
                {citations[0].quote}
              </div>
              <div
                style={{
                  marginTop: 13,
                  color: "#AEB6C2",
                  fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
                  fontSize: 12,
                }}
              >
                Slack / {citations[0].place}
              </div>
            </div>
          </aside>
        </main>
      </div>
    </AbsoluteFill>
  );
};
