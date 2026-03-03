"use client";

import { useInView } from "@/hooks/useInView";
import {
  LinearLogo,
  SlackLogo,
  GitHubLogo,
  NotionLogo,
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

function EmailIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <rect x="2" y="4" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M2 6L9 11L16 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function GoogleDocIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <path d="M5 2H11L14 5V15C14 15.5523 13.5523 16 13 16H5C4.44772 16 4 15.5523 4 15V3C4 2.44772 4.44772 2 5 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M11 2V5H14" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M7 9H11M7 12H10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function Pill({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div
      className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm text-[#9CA3AF]"
      style={{
        border: "1px solid rgba(255,255,255,0.1)",
        background: "rgba(255,255,255,0.03)",
      }}
    >
      <span className="text-[#9CA3AF]">{icon}</span>
      {label}
    </div>
  );
}

const toolPills = [
  { label: "Slack", icon: <SlackLogo width={18} height={18} color="currentColor" />, top: "0%", left: "8%" },
  { label: "Notion", icon: <NotionLogo width={18} height={18} />, top: "0%", left: "52%" },
  { label: "Linear", icon: <LinearLogo width={18} height={18} />, top: "35%", left: "5%" },
  { label: "Meeting", icon: <MeetingIcon />, top: "35%", left: "55%" },
  { label: "Google Doc", icon: <GoogleDocIcon />, top: "68%", left: "3%" },
  { label: "Email", icon: <EmailIcon />, top: "68%", left: "48%" },
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
            "radial-gradient(ellipse 60% 50% at 50% 50%, rgba(0,212,170,0.04) 0%, transparent 60%)",
        }}
      />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Section label */}
        <div
          className={`flex justify-center mb-4 transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          <span className="section-label">The Problem</span>
        </div>

        {/* Headline */}
        <h2
          className={`text-4xl md:text-5xl font-bold text-center text-white mb-4 tracking-tight transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          The real bottleneck isn&apos;t coding.
          <br />
          <span className="teal-gradient-text">It&apos;s context.</span>
        </h2>

        <p
          className={`text-center text-[#6B7280] mb-16 max-w-xl mx-auto transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "150ms" }}
        >
          Before an engineer writes a single line of code, they spend hours piecing
          together what this ticket is actually about.
        </p>

        {/* Comparison cards with arrow */}
        <div
          className={`flex flex-col md:flex-row items-stretch gap-4 md:gap-0 transition-all duration-700 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
          style={{ transitionDelay: "250ms" }}
        >
          {/* Before card */}
          <div
            className="flex-1 rounded-2xl p-8 relative overflow-hidden"
            style={{
              border: "1px dashed rgba(255,255,255,0.15)",
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
            <h3 className="text-xl font-bold text-white mb-10">
              Before ContextOS
            </h3>

            {/* Tool pills scattered around sad face */}
            <div className="relative h-56 mb-6">
              {/* Left column pills */}
              <div className="absolute" style={{ top: "4%", left: "18%" }}>
                <Pill icon={toolPills[0].icon} label={toolPills[0].label} />
              </div>
              <div className="absolute" style={{ top: "36%", left: "14%" }}>
                <Pill icon={toolPills[2].icon} label={toolPills[2].label} />
              </div>
              <div className="absolute" style={{ top: "68%", left: "16%" }}>
                <Pill icon={toolPills[4].icon} label={toolPills[4].label} />
              </div>

              {/* Right column pills - offset vertically */}
              <div className="absolute" style={{ top: "8%", right: "16%" }}>
                <Pill icon={toolPills[1].icon} label={toolPills[1].label} />
              </div>
              <div className="absolute" style={{ top: "40%", right: "14%" }}>
                <Pill icon={toolPills[3].icon} label={toolPills[3].label} />
              </div>
              <div className="absolute" style={{ top: "72%", right: "18%" }}>
                <Pill icon={toolPills[5].icon} label={toolPills[5].label} />
              </div>

              {/* Sad face - dead center */}
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
                <div
                  className="w-12 h-12 rounded-full flex items-center justify-center"
                  style={{
                    background: "rgba(255,80,80,0.08)",
                    border: "1px solid rgba(255,80,80,0.2)",
                  }}
                >
                  <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                    <circle cx="11" cy="11" r="10" stroke="#FF6B6B" strokeWidth="1.5" />
                    <circle cx="8" cy="9" r="1.2" fill="#FF6B6B" />
                    <circle cx="14" cy="9" r="1.2" fill="#FF6B6B" />
                    <path d="M8 15C8 15 9.5 13 11 13C12.5 13 14 15 14 15" stroke="#FF6B6B" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                </div>
              </div>
            </div>

            {/* Time stat */}
            <div className="text-center">
              <div
                className="text-2xl md:text-3xl font-bold font-mono mb-2"
                style={{ color: "#FF6B6B" }}
              >
                2-6 hours
              </div>
              <p className="text-sm text-[#6B7280]">
                Spent gathering context before coding
              </p>
            </div>
          </div>

          {/* Arrow between cards */}
          <div className="flex items-center justify-center px-4 py-4 md:py-0">
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
              style={{
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                className="md:rotate-0 rotate-90"
              >
                <path
                  d="M3 8H13M13 8L9 4M13 8L9 12"
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
            className="flex-1 rounded-2xl p-8 relative overflow-hidden"
            style={{
              border: "1px dashed rgba(255,255,255,0.15)",
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
            <h3 className="text-xl font-bold text-white mb-10">
              With ContextOS
            </h3>

            {/* Context ready card */}
            <div className="flex justify-center mb-8">
              <div
                className="rounded-xl p-5 w-64 relative"
                style={{
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.08)",
                }}
              >
                <div className="flex items-center gap-2 mb-4">
                  <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                    <rect x="1" y="1" width="16" height="16" rx="3" stroke="#00D4AA" strokeWidth="1.5" />
                    <path d="M5 9L8 12L13 6" stroke="#00D4AA" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span className="text-white font-mono text-sm font-medium">
                    Context ready
                  </span>
                </div>
                {/* Placeholder lines */}
                <div className="space-y-2.5">
                  <div
                    className="h-2 rounded-full"
                    style={{ background: "rgba(255,255,255,0.08)", width: "90%" }}
                  />
                  <div
                    className="h-2 rounded-full"
                    style={{ background: "rgba(255,255,255,0.06)", width: "75%" }}
                  />
                  <div
                    className="h-2 rounded-full"
                    style={{ background: "rgba(255,255,255,0.04)", width: "60%" }}
                  />
                </div>
              </div>
            </div>

            {/* Happy face - centered with green glow */}
            <div className="flex justify-center mb-6">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center"
                style={{
                  background: "rgba(0,212,170,0.08)",
                  border: "1px solid rgba(0,212,170,0.2)",
                }}
              >
                <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                  <circle cx="11" cy="11" r="10" stroke="#00D4AA" strokeWidth="1.5" />
                  <circle cx="8" cy="9" r="1.2" fill="#00D4AA" />
                  <circle cx="14" cy="9" r="1.2" fill="#00D4AA" />
                  <path d="M8 13C8 13 9.5 15 11 15C12.5 15 14 13 14 13" stroke="#00D4AA" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </div>
            </div>

            {/* Time stat */}
            <div className="text-center">
              <div
                className="text-2xl md:text-3xl font-bold font-mono mb-2"
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
    </section>
  );
}
