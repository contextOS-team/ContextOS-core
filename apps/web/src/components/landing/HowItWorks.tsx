"use client";

import { useInView } from "@/hooks/useInView";

const steps = [
  {
    number: "01",
    title: "Connect your tools",
    description:
      "Link your Linear, Slack, Notion, and meeting tools in one click. ContextOS watches for new tickets automatically.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path
          d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"
          stroke="#00D4AA"
          strokeWidth="1.5"
        />
        <path
          d="M8 12h8M12 8l4 4-4 4"
          stroke="#00D4AA"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    visual: (
      <div className="mt-5 grid grid-cols-2 gap-2">
        {[
          { name: "Linear", icon: "Li", color: "#5E6AD2" },
          { name: "Slack", icon: "S", color: "#4A154B" },
          { name: "Notion", icon: "N", color: "#2a2a2a" },
          { name: "Meetings", icon: "M", color: "#1a3a5c" },
        ].map((tool) => (
          <div
            key={tool.name}
            className="flex items-center gap-2 px-3 py-2 rounded-lg"
            style={{
              background: "rgba(0,212,170,0.04)",
              border: "1px solid rgba(0,212,170,0.1)",
            }}
          >
            <div
              className="w-5 h-5 rounded flex items-center justify-center text-white font-bold text-[9px]"
              style={{ background: tool.color }}
            >
              {tool.icon}
            </div>
            <span className="text-xs text-[#9CA3AF]">{tool.name}</span>
            <div
              className="ml-auto w-1.5 h-1.5 rounded-full"
              style={{ background: "#00D4AA" }}
            />
          </div>
        ))}
      </div>
    ),
  },
  {
    number: "02",
    title: "Context assembles automatically",
    description:
      "When a ticket is created or assigned, our AI engine pulls relevant conversations, docs, decisions, and meeting moments into one page.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path
          d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
          stroke="#00D4AA"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    visual: (
      <div className="mt-5 space-y-2">
        {[
          { src: "Slack", text: "We decided to use WebSockets...", ts: "2d ago" },
          { src: "Notion", text: "Architecture decision record", ts: "1w ago" },
          { src: "Meet", text: "Sprint planning — clip 14:23", ts: "3d ago" },
        ].map((item, i) => (
          <div
            key={i}
            className="flex items-start gap-2 px-3 py-2 rounded-lg"
            style={{
              background: "rgba(255,255,255,0.02)",
              border: "1px solid rgba(255,255,255,0.05)",
              animationDelay: `${i * 200}ms`,
            }}
          >
            <div
              className="w-4 h-4 rounded flex items-center justify-center text-white font-bold flex-shrink-0 mt-0.5"
              style={{ background: "#1C1C2E", fontSize: "8px" }}
            >
              {item.src[0]}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-xs text-[#9CA3AF] truncate">{item.text}</div>
            </div>
            <span className="text-[10px] text-[#4B5563] flex-shrink-0">{item.ts}</span>
          </div>
        ))}
        <div className="flex items-center justify-center gap-1 pt-1">
          <div className="h-px flex-1" style={{ background: "rgba(0,212,170,0.15)" }} />
          <span className="text-[10px] font-mono text-[#00D4AA] px-2">AI synthesis complete</span>
          <div className="h-px flex-1" style={{ background: "rgba(0,212,170,0.15)" }} />
        </div>
      </div>
    ),
  },
  {
    number: "03",
    title: "Start coding immediately",
    description:
      "Open any ticket and find a complete context page — every decision, every thread, every relevant doc. No hunting.",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <polyline
          points="16 18 22 12 16 6"
          stroke="#00D4AA"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <polyline
          points="8 6 2 12 8 18"
          stroke="#00D4AA"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    visual: (
      <div
        className="mt-5 rounded-lg p-3 font-mono text-[11px]"
        style={{
          background: "#0A0A0F",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
          <div className="text-[#4B5563] mb-2"><span>{"// ENG-421 context ready"}</span></div>
        <div>
          <span style={{ color: "#00D4AA" }}>const</span>{" "}
          <span style={{ color: "#E0E0E0" }}>context</span>{" "}
          <span style={{ color: "#6B7280" }}>=</span>{" "}
          <span style={{ color: "#00D4AA" }}>await</span>{" "}
          <span style={{ color: "#9CA3AF" }}>getContext</span>
          <span style={{ color: "#6B7280" }}>(</span>
          <span style={{ color: "#FFA657" }}>&apos;ENG-421&apos;</span>
          <span style={{ color: "#6B7280" }}>)</span>
        </div>
        <div className="mt-1 text-[#4B5563]">
          {"// "}
          <span style={{ color: "#00D4AA" }}>
            Background, 4 decisions, 6 sources
          </span>
        </div>
        <div className="mt-2 flex items-center gap-1.5">
          <div
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: "#00D4AA" }}
          />
          <span style={{ color: "#00D4AA" }}>Ready to code</span>
        </div>
      </div>
    ),
  },
];

export default function HowItWorks() {
  const { ref, inView } = useInView();

  return (
    <section
      id="how-it-works"
      className="relative py-24 px-6 overflow-hidden"
      ref={ref as React.RefObject<HTMLElement>}
    >
      {/* Background */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 80% 40% at 50% 50%, rgba(0,212,170,0.03) 0%, transparent 70%)",
        }}
      />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Label */}
        <div
          className={`flex justify-center mb-4 transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          <span className="section-label">How It Works</span>
        </div>

        {/* Headline */}
        <h2
          className={`text-4xl md:text-5xl font-bold text-center text-white mb-16 tracking-tight transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          From ticket to context{" "}
          <span className="teal-gradient-text">in seconds</span>
        </h2>

        {/* Steps */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
          {/* Connector line (desktop only) */}
          <div
            className="hidden md:block absolute top-8 left-[calc(33%+24px)] right-[calc(33%+24px)] h-px"
            style={{
              background:
                "linear-gradient(90deg, rgba(0,212,170,0.3), rgba(0,212,170,0.1), rgba(0,212,170,0.3))",
            }}
          />

          {steps.map((step, i) => (
            <div
              key={step.number}
              className={`rounded-2xl p-6 card-hover relative transition-all duration-700 ${
                inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
              }`}
              style={{
                transitionDelay: `${200 + i * 120}ms`,
                background: "#0F0F18",
                border: "1px solid rgba(255,255,255,0.07)",
              }}
            >
              {/* Teal top accent line */}
              <div
                className="absolute top-0 left-6 right-6 h-px"
                style={{
                  background:
                    "linear-gradient(90deg, transparent, rgba(0,212,170,0.4), transparent)",
                }}
              />

              {/* Number + icon */}
              <div className="flex items-start justify-between mb-4">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{
                    background: "rgba(0,212,170,0.08)",
                    border: "1px solid rgba(0,212,170,0.15)",
                  }}
                >
                  {step.icon}
                </div>
                <span
                  className="text-3xl font-bold tracking-tighter"
                  style={{ color: "rgba(0,212,170,0.12)", fontFamily: "monospace" }}
                >
                  {step.number}
                </span>
              </div>

              <h3 className="text-base font-semibold text-white mb-2">{step.title}</h3>
              <p className="text-sm text-[#6B7280] leading-relaxed">{step.description}</p>

              {step.visual}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
