"use client";

import { Player } from "@remotion/player";
import { useCallback } from "react";
import {
  FPS,
  COMPOSITION_WIDTH,
  COMPOSITION_HEIGHT,
  TOTAL_DURATION,
} from "@/remotion/constants";

export function RemotionHeroPlayer() {
  const lazyComp = useCallback(
    () =>
      import("@/remotion/HeroComposition").then((m) => ({
        default: m.HeroComposition,
      })),
    []
  );

  return (
    <Player
      lazyComponent={lazyComp}
      durationInFrames={TOTAL_DURATION}
      fps={FPS}
      compositionWidth={COMPOSITION_WIDTH}
      compositionHeight={COMPOSITION_HEIGHT}
      loop
      autoPlay
      style={{ width: "100%", borderRadius: "1rem" }}
      acknowledgeRemotionLicense
    />
  );
}
