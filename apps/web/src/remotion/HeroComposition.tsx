import { AbsoluteFill } from "remotion";
import { COLORS } from "./constants";
import { ContextOSProductDemoScene } from "./scenes/ContextOSProductDemoScene";

export const HeroComposition: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.background }}>
      <ContextOSProductDemoScene />
    </AbsoluteFill>
  );
};
