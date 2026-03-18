"use client";

import { useInView } from "@/hooks/useInView";
import {
  LinearLogo,
  SlackLogo,
  NotionLogo,
  TelegramLogo,
  JiraLogo,
} from "@/components/icons/brand-logos";

/* Small inline icons for tools without brand logos */
function MeetingIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <rect x="2" y="3" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="9" cy="9" r="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M13 6L16 4V14L13 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}



function Pill({ icon, label, rotate, opacity }: { icon: React.ReactNode; label: string; rotate?: number; opacity?: number }) {
  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs text-[#9CA3AF]"
      style={{
        border: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(255,255,255,0.03)",
        transform: rotate ? `rotate(${rotate}deg)` : undefined,
        opacity: opacity ?? 1,
      }}
    >
      <span className="text-[#9CA3AF]">{icon}</span>
      {label}
    </div>
  );
}

const toolPills = [
  { label: "Slack", icon: <SlackLogo width={18} height={18} color="currentColor" /> },
  { label: "Notion", icon: <NotionLogo width={18} height={18} /> },
  { label: "Linear", icon: <LinearLogo width={18} height={18} /> },
  { label: "Meeting", icon: <MeetingIcon /> },
  { label: "Telegram", icon: <TelegramLogo width={18} height={18} fill="currentColor" /> },
  { label: "Jira", icon: <JiraLogo width={18} height={18} fill="currentColor" /> },
];

export default function ProblemSection() {
  const { ref, inView } = useInView();

  return (
    <section
      id="problem"
      className="relative py-24 px-6 overflow-hidden"
      ref={ref as React.RefObject<HTMLElement>}
    >
      {/* Background radial */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 30% 50%, rgba(0,212,170,0.04) 0%, transparent 60%)",
        }}
      />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Asymmetric layout: text left, cards right */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-start">
          {/* Left column — sticky text */}
          <div className="lg:col-span-4 lg:sticky lg:top-32">
            <div
              className={`transition-all duration-600 ${
                inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
              }`}
            >
              <span className="section-label">The Problem</span>
            </div>

            <h2
              className={`text-4xl md:text-5xl font-bold text-white mt-4 mb-6 tracking-tight transition-all duration-600 ${
                inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
              }`}
              style={{ transitionDelay: "100ms" }}
            >
              The real bottleneck isn&apos;t coding.
              <br />
              It&apos;s context.
            </h2>

            <p
              className={`text-[#6B7280] leading-relaxed transition-all duration-600 ${
                inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
              }`}
              style={{ transitionDelay: "150ms" }}
            >
              Before an engineer writes a single line of code, they spend hours piecing
              together what this ticket is actually about.
            </p>
          </div>

          {/* Right column — before/after cards stacked */}
          <div
            className={`lg:col-span-8 flex flex-col items-center transition-all duration-700 ${
              inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
            }`}
            style={{ transitionDelay: "250ms" }}
          >
            {/* Before card */}
            <div
              className="rounded-2xl p-6 relative overflow-hidden w-full max-w-xl"
              style={{
                border: "1px solid rgba(255,80,80,0.12)",
                background: "rgba(255,255,255,0.02)",
                boxShadow: "inset 0 0 80px rgba(255,80,80,0.06), 0 0 60px rgba(255,80,80,0.04)",
              }}
            >
              {/* Red ambient glow */}
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background: "radial-gradient(ellipse 70% 60% at 50% 50%, rgba(255,80,80,0.06) 0%, transparent 70%)",
                }}
              />
              <h3 className="text-lg font-bold text-white mb-5 relative z-10">
                Before ContextOS
              </h3>

              {/* Tool pills scattered around sad face — irregular, organic layout */}
              <div className="relative h-36 mb-4">
                {/* Scattered pills with varied positions, rotations, opacity */}
                <div className="absolute" style={{ top: "0%", left: "5%" }}>
                  <Pill icon={toolPills[0].icon} label={toolPills[0].label} rotate={-2} />
                </div>
                <div className="absolute" style={{ top: "30%", left: "2%" }}>
                  <Pill icon={toolPills[2].icon} label={toolPills[2].label} rotate={1.5} opacity={0.85} />
                </div>
                <div className="absolute" style={{ top: "68%", left: "10%" }}>
                  <Pill icon={toolPills[4].icon} label={toolPills[4].label} rotate={-1} opacity={0.75} />
                </div>

                <div className="absolute" style={{ top: "6%", right: "3%" }}>
                  <Pill icon={toolPills[1].icon} label={toolPills[1].label} rotate={2.5} opacity={0.8} />
                </div>
                <div className="absolute" style={{ top: "36%", right: "7%" }}>
                  <Pill icon={toolPills[3].icon} label={toolPills[3].label} rotate={-1.5} />
                </div>
                <div className="absolute" style={{ top: "64%", right: "1%" }}>
                  <Pill icon={toolPills[5].icon} label={toolPills[5].label} rotate={3} opacity={0.7} />
                </div>

                {/* Sad face - center, larger as focal point */}
                <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
                  <div
                    className="w-12 h-12 rounded-full flex items-center justify-center"
                    style={{
                      background: "rgba(255,80,80,0.1)",
                      border: "1px solid rgba(255,80,80,0.25)",
                    }}
                  >
                    <svg width="24" height="24" viewBox="0 0 22 22" fill="none">
                      <circle cx="11" cy="11" r="10" stroke="#FF6B6B" strokeWidth="1.5" />
                      <circle cx="8" cy="9" r="1.2" fill="#FF6B6B" />
                      <circle cx="14" cy="9" r="1.2" fill="#FF6B6B" />
                      <path d="M8 15C8 15 9.5 13 11 13C12.5 13 14 15 14 15" stroke="#FF6B6B" strokeWidth="1.5" strokeLinecap="round" />
                    </svg>
                  </div>
                </div>
              </div>

              {/* Time stat */}
              <div className="text-center relative z-10">
                <div
                  className="text-xl md:text-2xl font-bold font-mono mb-1"
                  style={{ color: "#FF6B6B" }}
                >
                  2-6 hours
                </div>
                <p className="text-sm text-[#6B7280]">
                  Spent gathering context before coding
                </p>
              </div>
            </div>

            {/* Arrow */}
            <div className="flex justify-center py-3">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                style={{
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.1)",
                }}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path
                    d="M8 3V13M8 13L4 9M8 13L12 9"
                    stroke="#6B7280"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
            </div>

            {/* After card */}
            <div
              className="rounded-2xl p-6 relative overflow-hidden w-full max-w-xl"
              style={{
                border: "1px solid rgba(0,212,170,0.12)",
                background: "rgba(255,255,255,0.02)",
                boxShadow: "inset 0 0 80px rgba(0,212,170,0.06), 0 0 60px rgba(0,212,170,0.04)",
              }}
            >
              {/* Green ambient glow */}
              <div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background: "radial-gradient(ellipse 70% 60% at 50% 50%, rgba(0,212,170,0.06) 0%, transparent 70%)",
                }}
              />
              <h3 className="text-lg font-bold text-white mb-5 relative z-10">
                With ContextOS
              </h3>

              {/* Context ready card */}
              <div className="flex justify-center mb-5">
                <div
                  className="rounded-xl p-4 w-56 relative"
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.08)",
                  }}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <svg width="16" height="16" viewBox="0 0 18 18" fill="none">
                      <rect x="1" y="1" width="16" height="16" rx="3" stroke="#00D4AA" strokeWidth="1.5" />
                      <path d="M5 9L8 12L13 6" stroke="#00D4AA" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                    <span className="text-white font-mono text-sm font-medium">
                      Context ready
                    </span>
                  </div>
                  {/* Placeholder lines */}
                  <div className="space-y-2">
                    <div
                      className="h-1.5 rounded-full"
                      style={{ background: "rgba(255,255,255,0.08)", width: "90%" }}
                    />
                    <div
                      className="h-1.5 rounded-full"
                      style={{ background: "rgba(255,255,255,0.06)", width: "75%" }}
                    />
                  </div>
                </div>
              </div>

              {/* Happy face */}
              <div className="flex justify-center mb-4">
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center"
                  style={{
                    background: "rgba(0,212,170,0.08)",
                    border: "1px solid rgba(0,212,170,0.2)",
                  }}
                >
                  <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
                    <circle cx="11" cy="11" r="10" stroke="#00D4AA" strokeWidth="1.5" />
                    <circle cx="8" cy="9" r="1.2" fill="#00D4AA" />
                    <circle cx="14" cy="9" r="1.2" fill="#00D4AA" />
                    <path d="M8 13C8 13 9.5 15 11 15C12.5 15 14 13 14 13" stroke="#00D4AA" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </div>
              </div>

              {/* Time stat */}
              <div className="text-center relative z-10">
                <div
                  className="text-xl md:text-2xl font-bold font-mono mb-1"
                  style={{ color: "#00D4AA" }}
                >
                  2 minutes
                </div>
                <p className="text-sm text-[#6B7280]">
                  Everything organized. Ready to code.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
