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

/** Recognizable brand mark SVGs */
const icons: Record<SourceName, React.ReactNode> = {
  Slack: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      {/* Slack 4-dot logo */}
      <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zM6.313 15.165a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill={COLORS.slackGreen}/>
      <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zM8.834 6.313a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill={COLORS.slackBlue}/>
      <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zM17.688 8.834a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.165 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill={COLORS.slackYellow}/>
      <path d="M15.165 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.165 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zM15.165 17.688a2.527 2.527 0 0 1-2.52-2.523 2.526 2.526 0 0 1 2.52-2.52h6.313A2.527 2.527 0 0 1 24 15.165a2.528 2.528 0 0 1-2.522 2.523h-6.313z" fill={COLORS.slackRed}/>
    </svg>
  ),
  GitHub: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="currentColor">
      {/* GitHub Octocat mark */}
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
    </svg>
  ),
  Linear: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      {/* Linear logo mark */}
      <path d="M1.15 12.82a11.18 11.18 0 0 0 10.03 10.03L1.15 12.82z" fill={COLORS.linear}/>
      <path d="M1.66 15.58l6.76 6.76a11.21 11.21 0 0 1-6.76-6.76z" fill={COLORS.linear} opacity="0.7"/>
      <path d="M3.95 18.86l1.19 1.19a11.17 11.17 0 0 1-1.19-1.19z" fill={COLORS.linear} opacity="0.4"/>
      <path d="M22.85 11.18A11.18 11.18 0 0 0 12.82 1.15l10.03 10.03z" fill={COLORS.linear}/>
      <path d="M12 1a11 11 0 1 0 11 11A11 11 0 0 0 12 1zm0 19.5a8.5 8.5 0 1 1 8.5-8.5 8.51 8.51 0 0 1-8.5 8.5z" fill={COLORS.linear}/>
    </svg>
  ),
};

export const SourceIcon: React.FC<SourceIconProps> = ({ name, active }) => {
  return (
    <div
      style={{
        width: 48,
        height: 48,
        borderRadius: 24,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: active ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.06)",
        color: COLORS.text,
        boxShadow: active ? `0 0 16px ${COLORS.tealGlow}` : "none",
      }}
    >
      {icons[name]}
    </div>
  );
};
