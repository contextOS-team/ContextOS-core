import { COLORS } from "../constants";

interface ProgressBarProps {
  progress: number; // 0-1 spring value
  color?: string;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  progress,
  color = COLORS.teal,
}) => {
  const isActive = progress > 0.01;

  return (
    <div
      style={{
        width: "100%",
        height: 6,
        borderRadius: 3,
        background: "rgba(255,255,255,0.06)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${Math.min(progress * 100, 100)}%`,
          height: "100%",
          borderRadius: 3,
          background: color,
          boxShadow: isActive ? `0 0 12px ${COLORS.tealGlow}` : "none",
        }}
      />
    </div>
  );
};
