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
        background: COLORS.cardGradient,
        border: `1px solid ${COLORS.cardBorder}`,
        borderRadius: 16,
        boxShadow: `0 0 40px rgba(0,212,170,0.10), 0 0 80px rgba(0,212,170,0.06)`,
        padding: 40,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
