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
      <div className="grid grid-cols-2 gap-2">
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
      <div className="space-y-2">
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
        className="rounded-lg p-3 font-mono text-[11px]"
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

      <div className="max-w-5xl mx-auto relative z-10">
        {/* Header — left-aligned on desktop */}
        <div className="max-w-lg mb-16">
          <div
            className={`mb-4 transition-all duration-600 ${
              inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
            }`}
          >
            <span className="section-label">How It Works</span>
          </div>

          <h2
            className={`text-4xl md:text-5xl font-bold text-white tracking-tight transition-all duration-600 ${
              inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
            }`}
            style={{ transitionDelay: "100ms" }}
          >
            From ticket to context in seconds
          </h2>
        </div>

        {/* Steps — alternating layout */}
        <div className="space-y-12 md:space-y-0 relative">
          {/* Vertical connector line (desktop only) */}
          <div
            className="hidden md:block absolute left-1/2 top-8 bottom-8 w-px -translate-x-1/2"
            style={{
              background:
                "linear-gradient(180deg, rgba(0,212,170,0.3), rgba(0,212,170,0.08), rgba(0,212,170,0.3))",
            }}
          />

          {steps.map((step, i) => {
            const isEven = i % 2 === 0;
            return (
              <div
                key={step.number}
                className={`md:grid md:grid-cols-2 md:gap-12 items-center md:py-8 transition-all duration-700 ${
                  inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                }`}
                style={{ transitionDelay: `${200 + i * 150}ms` }}
              >
                {/* Text side */}
                <div
                  className={`mb-6 md:mb-0 ${
                    isEven ? "md:order-1 md:text-right md:pr-12" : "md:order-2 md:pl-12"
                  }`}
                >
                  {/* Step number */}
                  <div className={`flex items-center gap-3 mb-3 ${isEven ? "md:justify-end" : ""}`}>
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
                      className="text-2xl font-bold tracking-tighter font-mono"
                      style={{ color: "rgba(0,212,170,0.15)" }}
                    >
                      {step.number}
                    </span>
                  </div>
                  <h3 className="text-xl font-semibold text-white mb-2">{step.title}</h3>
                  <p className="text-sm text-[#6B7280] leading-relaxed">{step.description}</p>
                </div>

                {/* Visual side */}
                <div
                  className={`rounded-2xl p-5 card-hover relative ${
                    isEven ? "md:order-2 md:ml-12" : "md:order-1 md:mr-12"
                  }`}
                  style={{
                    background: "#0F0F18",
                    border: "1px solid rgba(255,255,255,0.07)",
                  }}
                >
                  {/* Teal accent line */}
                  <div
                    className="absolute top-0 left-6 right-6 h-px"
                    style={{
                      background:
                        "linear-gradient(90deg, transparent, rgba(0,212,170,0.4), transparent)",
                    }}
                  />
                  {step.visual}
                </div>

                {/* Center dot on timeline (desktop only) */}
                <div
                  className="hidden md:flex absolute left-1/2 -translate-x-1/2 items-center justify-center"
                  style={{ top: `${8 + i * 33.33}rem` }}
                >
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{
                      background: "#00D4AA",
                      boxShadow: "0 0 8px rgba(0,212,170,0.4)",
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
