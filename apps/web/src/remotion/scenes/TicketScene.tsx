import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { MockCard } from "../components/MockCard";
import { COLORS, SPRING_ENTER, SPRING_SUBTLE, STAGGER_FRAMES } from "../constants";

export const TicketScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Card slide-in animation
  const enterProgress = spring({ frame, fps, config: SPRING_ENTER });
  const translateX = interpolate(enterProgress, [0, 1], [120, 0]);
  const opacity = interpolate(enterProgress, [0, 1], [0, 1]);
  const scale = interpolate(enterProgress, [0, 1], [0.95, 1]);

  // Staggered detail animations (after card lands, ~12 frame delay each)
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
      }}
    >
      <div
        style={{
          transform: `translateX(${translateX}px) scale(${scale})`,
          opacity,
          width: 500,
        }}
      >
        <MockCard>
          {/* Ticket header */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 16,
            }}
          >
            <span
              style={{
                fontFamily: "monospace",
                fontSize: 14,
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
              fontSize: 18,
              fontWeight: 600,
              color: COLORS.text,
              marginBottom: 20,
              lineHeight: 1.4,
            }}
          >
            Implement user authentication flow
          </div>

          {/* Detail rows */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {/* Priority */}
            <div style={detailStyle(priorityProgress)}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                }}
              >
                <span style={{ fontSize: 13, color: COLORS.textMuted }}>
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
                  <span style={{ fontSize: 13, color: COLORS.text }}>High</span>
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
                <span style={{ fontSize: 13, color: COLORS.textMuted }}>
                  Assignee
                </span>
                <span style={{ fontSize: 13, color: COLORS.text }}>
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
                <span style={{ fontSize: 13, color: COLORS.textMuted }}>
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
                  <span style={{ fontSize: 13, color: COLORS.text }}>
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
