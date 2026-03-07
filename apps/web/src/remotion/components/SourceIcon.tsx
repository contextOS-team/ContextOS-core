import { COLORS } from "../constants";

type SourceName = "Slack" | "GitHub" | "Linear";

interface SourceIconProps {
  name: SourceName;
  active: boolean;
}

const BRAND_COLORS: Record<SourceName, string> = {
  Slack: COLORS.slackPurple,
  GitHub: COLORS.github,
  Linear: COLORS.linear,
};

/** Minimal SVG icons (not full brand logos) */
const icons: Record<SourceName, React.ReactNode> = {
  // Hash symbol for Slack
  Slack: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path
        d="M5 8H15M5 12H15M8 5V15M12 5V15"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  ),
  // Code brackets for GitHub
  GitHub: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path
        d="M7 5L3 10L7 15M13 5L17 10L13 15"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ),
  // Diamond/arrow for Linear
  Linear: (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path
        d="M10 3L17 10L10 17L3 10L10 3Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  ),
};

export const SourceIcon: React.FC<SourceIconProps> = ({ name, active }) => {
  const brandColor = BRAND_COLORS[name];

  return (
    <div
      style={{
        width: 40,
        height: 40,
        borderRadius: 20,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: active ? brandColor : "rgba(255,255,255,0.08)",
        color: active ? (name === "GitHub" ? "#0A0A0F" : "#FFFFFF") : COLORS.textMuted,
        boxShadow: active ? `0 0 16px ${COLORS.tealGlow}` : "none",
        transition: "none", // No CSS transitions in Remotion
      }}
    >
      {icons[name]}
    </div>
  );
};
