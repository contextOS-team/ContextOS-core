"use client";

import { useInView } from "@/hooks/useInView";
import {
  LinearLogo,
  SlackLogo,
  GitHubLogo,
  NotionLogo,
  FathomLogo,
} from "@/components/icons/brand-logos";
import type { ComponentType, SVGProps } from "react";

type Integration = {
  name: string;
  description: string;
  status: "live" | "soon";
  icon: string | null;
  color: string;
  Logo?: ComponentType<SVGProps<SVGSVGElement>>;
};

const integrations: Integration[] = [
  { name: "Linear", description: "Issue tracking", status: "live", icon: null, color: "#5E6AD2", Logo: LinearLogo },
  { name: "Slack", description: "Team messaging", status: "live", icon: null, color: "#4A154B", Logo: SlackLogo },
  { name: "GitHub", description: "Code & PRs", status: "live", icon: null, color: "#1e1e1e", Logo: GitHubLogo },
  { name: "Notion", description: "Docs & wikis", status: "live", icon: null, color: "#2a2a2a", Logo: NotionLogo },
  { name: "Fathom", description: "Transcripts & clips", status: "live", icon: null, color: "#00BEFF", Logo: FathomLogo },
  { name: "Confluence", description: "Documentation", status: "soon", icon: "C", color: "#0052CC" },
  { name: "Google Docs", description: "Documents", status: "soon", icon: "G", color: "#4285F4" },
  { name: "Figma", description: "Design files", status: "soon", icon: "F", color: "#1C1C1E" },
  { name: "Loom", description: "Video messages", status: "soon", icon: "L", color: "#625DF5" },
];

export default function Integrations() {
  const { ref, inView } = useInView();

  return (
    <section
      id="integrations"
      className="relative py-24 px-6 overflow-hidden"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 40% at 30% 60%, rgba(0,212,170,0.04) 0%, transparent 60%)",
        }}
      />

      <div className="max-w-5xl mx-auto relative z-10">
        {/* Label */}
        <div
          className={`flex justify-center mb-4 transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          <span className="section-label">Integrations</span>
        </div>

        {/* Headline */}
        <h2
          className={`text-4xl md:text-5xl font-bold text-center text-white mb-4 tracking-tight transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          Works with your{" "}
          <span className="teal-gradient-text">existing stack</span>
        </h2>

        <p
          className={`text-center text-[#6B7280] mb-14 max-w-lg mx-auto transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "150ms" }}
        >
          Connect your tools in one click. More integrations shipping every sprint.
        </p>

        {/* Grid */}
        <div
          className={`grid grid-cols-2 md:grid-cols-4 gap-4 transition-all duration-700 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
          style={{ transitionDelay: "250ms" }}
        >
          {integrations.map((integration, i) => (
            <div
              key={integration.name}
              className="rounded-xl p-4 relative overflow-hidden card-hover"
              style={{
                background: "#0F0F18",
                border: "1px solid rgba(255,255,255,0.07)",
                opacity: integration.status === "soon" ? 0.55 : 1,
                transitionDelay: `${i * 50}ms`,
              }}
            >
              {integration.status === "live" && (
                <div
                  className="absolute top-0 left-0 right-0 h-px"
                  style={{
                    background:
                      "linear-gradient(90deg, transparent, rgba(0,212,170,0.3), transparent)",
                  }}
                />
              )}

              <div className="flex items-start justify-between mb-3">
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center text-white"
                  style={{ background: integration.color }}
                >
                  {integration.Logo ? (
                    <integration.Logo width={16} height={16} fill="currentColor" />
                  ) : (
                    <span className="font-bold text-xs">{integration.icon}</span>
                  )}
                </div>
                {integration.status === "soon" ? (
                  <span
                    className="text-[9px] px-1.5 py-0.5 rounded font-mono uppercase tracking-wide"
                    style={{
                      background: "rgba(255,255,255,0.05)",
                      color: "#4B5563",
                      border: "1px solid rgba(255,255,255,0.06)",
                    }}
                  >
                    Soon
                  </span>
                ) : (
                  <div
                    className="flex items-center gap-1 text-[9px] font-mono"
                    style={{ color: "#00D4AA" }}
                  >
                    <div
                      className="w-1.5 h-1.5 rounded-full"
                      style={{ background: "#00D4AA" }}
                    />
                    Live
                  </div>
                )}
              </div>

              <div className="text-sm font-medium text-white">{integration.name}</div>
              <div className="text-xs text-[#4B5563] mt-0.5">{integration.description}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
