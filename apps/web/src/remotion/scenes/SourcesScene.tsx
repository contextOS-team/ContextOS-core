import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { MockCard } from "../components/MockCard";
import { ProgressBar } from "../components/ProgressBar";
import { SourceIcon } from "../components/SourceIcon";
import {
  COLORS,
  SPRING_ENTER,
  SPRING_SUBTLE,
  STAGGER_FRAMES,
} from "../constants";

type SourceName = "Slack" | "GitHub" | "Linear";

interface SourceRow {
  name: SourceName;
  color: string;
}

const SOURCES: SourceRow[] = [
  { name: "Slack", color: COLORS.slackGreen },
  { name: "GitHub", color: COLORS.github },
  { name: "Linear", color: COLORS.linear },
];

const SOURCE_STAGGER = STAGGER_FRAMES * 3; // 12 frames between each source
const PROGRESS_DELAY = 15; // frames after source appears before bar fills

export const SourcesScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const labelText = frame > 90 ? "3 sources found" : "Searching sources...";

  return (
    <AbsoluteFill
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: COLORS.background,
      }}
    >
      <div style={{ width: 480 }}>
        <MockCard>
          {/* Label */}
          <div
            style={{
              fontSize: 13,
              color: COLORS.textMuted,
              marginBottom: 20,
              fontFamily: "monospace",
            }}
          >
            {labelText}
          </div>

          {/* Source rows */}
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {SOURCES.map((source, index) => {
              const sourceDelay = index * SOURCE_STAGGER;
              const appearProgress = spring({
                frame: Math.max(0, frame - sourceDelay),
                fps,
                config: SPRING_ENTER,
              });

              const progressBarFrame = Math.max(
                0,
                frame - sourceDelay - PROGRESS_DELAY
              );
              const barProgress = spring({
                frame: progressBarFrame,
                fps,
                config: SPRING_SUBTLE,
              });

              const isActive = barProgress > 0.95;

              return (
                <div
                  key={source.name}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    opacity: appearProgress,
                    transform: `scale(${interpolate(
                      appearProgress,
                      [0, 1],
                      [0.8, 1]
                    )})`,
                  }}
                >
                  <SourceIcon name={source.name} active={isActive} />
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        fontSize: 14,
                        color: COLORS.text,
                        marginBottom: 6,
                        fontWeight: 500,
                      }}
                    >
                      {source.name}
                    </div>
                    <ProgressBar progress={barProgress} color={source.color} />
                  </div>
                </div>
              );
            })}
          </div>
        </MockCard>
      </div>
    </AbsoluteFill>
  );
};
