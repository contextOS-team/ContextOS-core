"use client";

import { Player, type PlayerRef } from "@remotion/player";
import { useCallback, useEffect, useRef } from "react";
import {
  FPS,
  COMPOSITION_WIDTH,
  COMPOSITION_HEIGHT,
  TOTAL_DURATION,
} from "@/remotion/constants";

interface RemotionHeroPlayerProps {
  onFrameUpdate?: (frame: number) => void;
}

export function RemotionHeroPlayer({ onFrameUpdate }: RemotionHeroPlayerProps) {
  const playerRef = useRef<PlayerRef>(null);

  const lazyComp = useCallback(
    () =>
      import("@/remotion/HeroComposition").then((m) => ({
        default: m.HeroComposition,
      })),
    []
  );

  useEffect(() => {
    const player = playerRef.current;
    if (!player || !onFrameUpdate) return;

    const handler = () => {
      const frame = player.getCurrentFrame();
      onFrameUpdate(frame);
    };

    player.addEventListener("frameupdate", handler);
    return () => player.removeEventListener("frameupdate", handler);
  }, [onFrameUpdate]);

  return (
    <Player
      ref={playerRef}
      lazyComponent={lazyComp}
      durationInFrames={TOTAL_DURATION}
      fps={FPS}
      compositionWidth={COMPOSITION_WIDTH}
      compositionHeight={COMPOSITION_HEIGHT}
      loop
      autoPlay
      style={{ width: "100%" }}
      acknowledgeRemotionLicense
    />
  );
}
