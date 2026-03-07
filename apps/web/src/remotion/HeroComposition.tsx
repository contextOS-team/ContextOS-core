import { AbsoluteFill, Series } from "remotion";
import {
  COLORS,
  SCENE_1_DURATION,
  SCENE_2_DURATION,
  SCENE_3_DURATION,
} from "./constants";
import { ContextScene } from "./scenes/ContextScene";
import { SourcesScene } from "./scenes/SourcesScene";
import { TicketScene } from "./scenes/TicketScene";

export const HeroComposition: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.background }}>
      <Series>
        <Series.Sequence durationInFrames={SCENE_1_DURATION}>
          <TicketScene />
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
