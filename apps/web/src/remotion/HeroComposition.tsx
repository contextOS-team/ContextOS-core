import { AbsoluteFill, Series } from "remotion";
import {
  COLORS,
  SCENE_1_DURATION,
  SCENE_2_DURATION,
  SCENE_3_DURATION,
} from "./constants";
import { DashboardScene } from "./scenes/DashboardScene";
import { SourcesScene } from "./scenes/SourcesScene";
import { ContextScene } from "./scenes/ContextScene";

export const HeroComposition: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.background }}>
      <Series>
        <Series.Sequence durationInFrames={SCENE_1_DURATION}>
          <DashboardScene />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENE_2_DURATION}>
          <SourcesScene />
        </Series.Sequence>
        <Series.Sequence durationInFrames={SCENE_3_DURATION}>
          <ContextScene />
        </Series.Sequence>
      </Series>
    </AbsoluteFill>
  );
};
