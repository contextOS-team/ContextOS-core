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
  CROSSFADE_FRAMES,
  SCENE_1_DURATION,
  SPRING_ENTER,
  SPRING_SUBTLE,
} from "../constants";

export const TicketScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Unified card entrance: translateY + opacity + scale
  const enterProgress = spring({ frame, fps, config: SPRING_ENTER });
  const translateY = interpolate(enterProgress, [0, 1], [30, 0]);
  const enterOpacity = interpolate(enterProgress, [0, 1], [0, 1]);
  const scale = interpolate(enterProgress, [0, 1], [0.97, 1]);

  // Cross-fade out at end of scene
  const fadeOut = interpolate(
    frame,
    [SCENE_1_DURATION - CROSSFADE_FRAMES, SCENE_1_DURATION],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Staggered detail animations
  const detailDelay = 20;
  const detailStagger = 12;

  const priorityProgress = spring({
    frame: Math.max(0, frame - detailDelay),
    fps,
    config: SPRING_SUBTLE,
  });
  const assigneeProgress = spring({
    frame: Math.max(0, frame - detailDelay - detailStagger),
    fps,
    config: SPRING_SUBTLE,
  });
  const statusProgress = spring({
    frame: Math.max(0, frame - detailDelay - detailStagger * 2),
    fps,
    config: SPRING_SUBTLE,
  });

  const detailStyle = (progress: number): React.CSSProperties => ({
    opacity: progress,
    transform: `translateY(${interpolate(progress, [0, 1], [8, 0])}px)`,
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
          transform: `translateY(${translateY}px) scale(${scale})`,
          opacity: enterOpacity,
          width: 700,
        }}
      >
        <MockCard>
          {/* Ticket header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 20,
            }}
          >
            <span
              style={{
                fontFamily: "monospace",
                fontSize: 16,
                color: COLORS.teal,
                fontWeight: 600,
              }}
            >
              ENG-42
            </span>
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: 3,
                background: COLORS.teal,
              }}
            />
          </div>

          {/* Ticket title */}
          <div
            style={{
              fontSize: 24,
              fontWeight: 600,
              color: COLORS.text,
              marginBottom: 24,
              lineHeight: 1.4,
            }}
          >
            Implement user authentication flow
          </div>

          {/* Detail rows */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Priority */}
            <div style={detailStyle(priorityProgress)}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span style={{ fontSize: 15, color: COLORS.textMuted }}>
                  Priority
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 4,
                      background: "#F59E0B",
                    }}
                  />
                  <span style={{ fontSize: 15, color: COLORS.text }}>High</span>
                </div>
              </div>
            </div>

            {/* Assignee */}
            <div style={detailStyle(assigneeProgress)}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span style={{ fontSize: 15, color: COLORS.textMuted }}>
                  Assignee
                </span>
                <span style={{ fontSize: 15, color: COLORS.text }}>
                  Sarah Chen
                </span>
              </div>
            </div>

            {/* Status */}
            <div style={detailStyle(statusProgress)}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span style={{ fontSize: 15, color: COLORS.textMuted }}>
                  Status
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 4,
                      background: COLORS.teal,
                    }}
                  />
                  <span style={{ fontSize: 15, color: COLORS.text }}>
                    In Progress
                  </span>
                </div>
              </div>
            </div>
          </div>
        </MockCard>
      </div>
    </AbsoluteFill>
  );
};
