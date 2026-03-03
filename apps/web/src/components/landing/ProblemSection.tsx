"use client";

import { useInView } from "@/hooks/useInView";

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

        {/* Comparison */}
        <div
          className={`grid grid-cols-1 md:grid-cols-2 gap-6 transition-all duration-700 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
          style={{ transitionDelay: "250ms" }}
        >
          {/* Before */}
          <div
            className="rounded-2xl p-6 relative overflow-hidden"
            style={{
              background: "#0F0F18",
              border: "1px solid rgba(255,80,80,0.15)",
            }}
          >
            <div
              className="absolute top-0 left-0 right-0 h-px"
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(255,80,80,0.3), transparent)",
              }}
            />
            <div className="flex items-center gap-2 mb-6">
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center"
                style={{ background: "rgba(255,80,80,0.1)", border: "1px solid rgba(255,80,80,0.2)" }}
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="#FF5050">
                  <path d="M6 1L6 11M1 6L11 6" stroke="#FF5050" strokeWidth="1.5" strokeLinecap="round" style={{ transform: "rotate(45deg)", transformOrigin: "center" }} />
                  <path d="M2 2L10 10M10 2L2 10" stroke="#FF5050" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </div>
              <span className="text-sm font-semibold text-[#FF8080]">Before ContextOS</span>
            </div>

            {/* Chaos visual */}
            <div className="relative mb-6">
              {/* Scattered tabs */}
              {[
                { label: "#eng-sprint-12", icon: "S", color: "#4A154B", top: 0, left: 0, rotate: -3 },
                { label: "Notion: Architecture v2", icon: "N", color: "#1e1e1e", top: 8, left: "30%", rotate: 2 },
                { label: "Loom recording 32min", icon: "L", color: "#625DF5", top: 0, right: 0, rotate: 4 },
                { label: "Linear: ENG-421", icon: "Li", color: "#5E6AD2", top: 52, left: "10%", rotate: -1 },
                { label: "Confluence doc...", icon: "C", color: "#0052CC", top: 52, left: "40%", rotate: 3 },
              ].map((tab, i) => (
                <div
                  key={i}
                  className="absolute flex items-center gap-1.5 px-2 py-1 rounded-md text-xs text-white"
                  style={{
                    background: "#141420",
                    border: "1px solid rgba(255,255,255,0.08)",
                    top: tab.top,
                    left: tab.left,
                    right: (tab as {right?: string | number}).right,
                    transform: `rotate(${tab.rotate}deg)`,
                    whiteSpace: "nowrap",
                    fontSize: "10px",
                  }}
                >
                  <div
                    className="w-3.5 h-3.5 rounded flex items-center justify-center text-white font-bold"
                    style={{ background: tab.color, fontSize: "7px" }}
                  >
                    {tab.icon}
                  </div>
                  {tab.label}
                </div>
              ))}
              <div className="h-28" />
            </div>

            {/* Developer frustrated */}
            <div className="flex items-center gap-4 mt-2">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center text-2xl"
                style={{ background: "rgba(255,80,80,0.08)", border: "1px solid rgba(255,80,80,0.15)" }}
              >
                {":("}
              </div>
              <div>
                <div className="text-white font-semibold text-sm">Developer</div>
                <div className="text-[#9CA3AF] text-xs">Hunting through 7+ sources</div>
              </div>
              <div className="ml-auto">
                <div
                  className="px-3 py-1.5 rounded-lg text-sm font-bold"
                  style={{
                    background: "rgba(255,80,80,0.1)",
                    border: "1px solid rgba(255,80,80,0.2)",
                    color: "#FF8080",
                  }}
                >
                  2-6 hours
                </div>
              </div>
            </div>

            <ul className="mt-5 space-y-2">
              {[
                "Searching Slack for the right thread",
                "Reading through long Notion pages",
                "Watching meeting recordings for context",
                "Asking teammates what was decided",
              ].map((item) => (
                <li key={item} className="flex items-center gap-2 text-xs text-[#6B7280]">
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <path d="M2 2L8 8M8 2L2 8" stroke="#FF5050" strokeWidth="1.5" strokeLinecap="round" />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* After */}
          <div
            className="rounded-2xl p-6 relative overflow-hidden"
            style={{
              background: "#0F0F18",
              border: "1px solid rgba(0,212,170,0.15)",
            }}
          >
            <div
              className="absolute top-0 left-0 right-0 h-px"
              style={{
                background:
                  "linear-gradient(90deg, transparent, rgba(0,212,170,0.4), transparent)",
              }}
            />
            <div className="flex items-center gap-2 mb-6">
              <div
                className="w-6 h-6 rounded-full flex items-center justify-center"
                style={{
                  background: "rgba(0,212,170,0.1)",
                  border: "1px solid rgba(0,212,170,0.2)",
                }}
              >
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M2 6L5 9L10 3" stroke="#00D4AA" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <span className="text-sm font-semibold text-[#00D4AA]">With ContextOS</span>
            </div>

            {/* Single clean page visual */}
            <div
              className="rounded-xl p-4 mb-6 relative overflow-hidden"
              style={{
                background: "#141420",
                border: "1px solid rgba(0,212,170,0.1)",
              }}
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-mono text-[#00D4AA] uppercase tracking-wider">Context Page</span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    background: "rgba(0,212,170,0.1)",
                    color: "#00D4AA",
                  }}
                >
                  Generated
                </span>
              </div>
              <div className="space-y-2">
                {["Background & decisions", "Relevant Slack threads", "Meeting moments", "Related docs"].map(
                  (item, i) => (
                    <div key={item} className="flex items-center gap-2">
                      <div
                        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ background: "#00D4AA", opacity: 1 - i * 0.15 }}
                      />
                      <span className="text-xs text-[#9CA3AF]">{item}</span>
                      <div className="flex-1 h-px" style={{ background: "rgba(255,255,255,0.04)" }} />
                      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                        <path d="M2 5L4 7L8 3" stroke="#00D4AA" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </div>
                  )
                )}
              </div>
            </div>

            {/* Developer happy */}
            <div className="flex items-center gap-4 mt-2">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center text-2xl"
                style={{
                  background: "rgba(0,212,170,0.08)",
                  border: "1px solid rgba(0,212,170,0.15)",
                }}
              >
                {":)"}
              </div>
              <div>
                <div className="text-white font-semibold text-sm">Developer</div>
                <div className="text-[#9CA3AF] text-xs">Opens ticket, context is ready</div>
              </div>
              <div className="ml-auto">
                <div
                  className="px-3 py-1.5 rounded-lg text-sm font-bold"
                  style={{
                    background: "rgba(0,212,170,0.1)",
                    border: "1px solid rgba(0,212,170,0.2)",
                    color: "#00D4AA",
                  }}
                >
                  2 minutes
                </div>
              </div>
            </div>

            <ul className="mt-5 space-y-2">
              {[
                "One auto-generated context page",
                "All sources unified in one view",
                "Key decisions highlighted",
                "Ready before you even open the ticket",
              ].map((item) => (
                <li key={item} className="flex items-center gap-2 text-xs text-[#6B7280]">
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <path d="M2 5L4 7L8 3" stroke="#00D4AA" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
