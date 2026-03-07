import type { CSSProperties, ReactNode } from "react";
import { COLORS } from "../constants";

interface MockCardProps {
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export const MockCard: React.FC<MockCardProps> = ({
  children,
  style,
}) => {
  return (
    <div
      style={{
        background: COLORS.cardBg,
        border: `1px solid ${COLORS.cardBorder}`,
        borderRadius: 16,
        boxShadow: `0 4px 24px rgba(0,0,0,0.4)`,
        padding: 24,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
