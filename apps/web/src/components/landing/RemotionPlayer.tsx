"use client";

import { Player, type PlayerRef } from "@remotion/player";
import { useEffect, useRef } from "react";
import { HeroComposition } from "@/remotion/HeroComposition";
import {
  FPS,
  COMPOSITION_WIDTH,
  COMPOSITION_HEIGHT,
  TOTAL_DURATION,
} from "@/remotion/constants";

interface RemotionHeroPlayerProps {
  onFrameUpdate?: (frame: number) => void;
}

const INITIAL_VISIBLE_FRAME = 132;
const PLAY_RETRY_INTERVAL_MS = 100;
const PLAY_RETRY_WINDOW_MS = 2000;

export function RemotionHeroPlayer({ onFrameUpdate }: RemotionHeroPlayerProps) {
  const playerRef = useRef<PlayerRef>(null);

  useEffect(() => {
    let elapsedMs = 0;

    const startPlayback = () => {
      const player = playerRef.current;

      if (player) {
        if (!player.isPlaying()) {
          player.play();
        }
        window.clearInterval(timer);
        return;
      }

      elapsedMs += PLAY_RETRY_INTERVAL_MS;
      if (elapsedMs >= PLAY_RETRY_WINDOW_MS) {
        window.clearInterval(timer);
      }
    };

    const timer = window.setInterval(startPlayback, PLAY_RETRY_INTERVAL_MS);
    startPlayback();

    return () => window.clearInterval(timer);
  }, []);

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
      component={HeroComposition}
      durationInFrames={TOTAL_DURATION}
      fps={FPS}
      compositionWidth={COMPOSITION_WIDTH}
      compositionHeight={COMPOSITION_HEIGHT}
      initialFrame={INITIAL_VISIBLE_FRAME}
      loop
      autoPlay
      controls={false}
      numberOfSharedAudioTags={0}
      initiallyMuted
      style={{
        width: "100%",
        aspectRatio: `${COMPOSITION_WIDTH} / ${COMPOSITION_HEIGHT}`,
      }}
      acknowledgeRemotionLicense
    />
  );
}
