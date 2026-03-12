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
  CROSSFADE_FRAMES,
  SCENE_2_DURATION,
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
  { name: "Slack", color: COLORS.teal },
  { name: "GitHub", color: COLORS.teal },
  { name: "Linear", color: COLORS.teal },
];

const SOURCE_STAGGER = STAGGER_FRAMES * 3; // 12 frames between each source
const PROGRESS_DELAY = 15; // frames after source appears before bar fills
const CONTENT_START = 15; // delay for content after card entrance

export const SourcesScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Card entrance animation
  const cardProgress = spring({ frame, fps, config: SPRING_ENTER });
  const cardTranslateY = interpolate(cardProgress, [0, 1], [30, 0]);
  const cardOpacity = interpolate(cardProgress, [0, 1], [0, 1]);
  const cardScale = interpolate(cardProgress, [0, 1], [0.97, 1]);

  // Cross-fade out at end of scene
  const fadeOut = interpolate(
    frame,
    [SCENE_2_DURATION - CROSSFADE_FRAMES, SCENE_2_DURATION],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Animated label transition
  const labelTransitionFrame = 90;
  const searchingOpacity = interpolate(
    frame,
    [labelTransitionFrame - 6, labelTransitionFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const foundOpacity = interpolate(
    frame,
    [labelTransitionFrame, labelTransitionFrame + 6],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const foundScale = interpolate(
    frame,
    [labelTransitionFrame, labelTransitionFrame + 8, labelTransitionFrame + 16],
    [0.95, 1.05, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

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
          width: 820,
          transform: `translateY(${cardTranslateY}px) scale(${cardScale})`,
          opacity: cardOpacity,
        }}
      >
        <MockCard>
          {/* Animated label */}
          <div
            style={{
              fontSize: 18,
              color: COLORS.textMuted,
              marginBottom: 28,
              fontFamily: "monospace",
              position: "relative",
              height: 20,
            }}
          >
            <span style={{ position: "absolute", opacity: searchingOpacity }}>
              Searching sources...
            </span>
            <span
              style={{
                position: "absolute",
                opacity: foundOpacity,
                transform: `scale(${foundScale})`,
                color: COLORS.teal,
              }}
            >
              3 sources found
            </span>
          </div>

          {/* Source rows */}
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {SOURCES.map((source, index) => {
              const sourceDelay = CONTENT_START + index * SOURCE_STAGGER;
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
                    gap: 16,
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
                        fontSize: 20,
                        color: COLORS.text,
                        marginBottom: 8,
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
