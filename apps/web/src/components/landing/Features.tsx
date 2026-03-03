"use client";

import { useInView } from "@/hooks/useInView";

function LargeCardMockup() {
  return (
    <div
      className="rounded-xl overflow-hidden mt-4"
      style={{
        background: "#0A0A0F",
        border: "1px solid rgba(255,255,255,0.06)",
        fontFamily: "monospace",
        fontSize: "11px",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", background: "#0F0F18" }}
      >
        <span className="text-[#00D4AA]">ENG-421</span>
        <span className="text-[#4B5563]">&#183;</span>
        <span className="text-[#6B7280]">Unified Context</span>
        <div className="ml-auto flex gap-1">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: `rgba(0,212,170,${0.4 - i * 0.1})` }}
            />
          ))}
        </div>
      </div>

      {/* Timeline */}
      <div className="p-3 space-y-2">
        {[
          { source: "Slack", time: "Nov 12", text: "Decided on WebSockets approach", color: "#4A154B" },
          { source: "Notion", time: "Nov 10", text: "Architecture decision recorded", color: "#2a2a2a" },
          { source: "Meet", time: "Nov 14", text: "Sprint planning clip — 14:23", color: "#1a3a5c" },
          { source: "Linear", time: "Nov 15", text: "Ticket created, assigned to you", color: "#5E6AD2" },
        ].map((item, i) => (
          <div key={i} className="flex items-start gap-2">
            <div className="flex flex-col items-center">
              <div
                className="w-4 h-4 rounded flex items-center justify-center text-white font-bold flex-shrink-0"
                style={{ background: item.color, fontSize: "7px" }}
              >
                {item.source[0]}
              </div>
              {i < 3 && (
                <div className="w-px h-3 mt-0.5" style={{ background: "rgba(255,255,255,0.06)" }} />
              )}
            </div>
            <div className="flex-1 min-w-0 pb-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[#6B7280] text-[9px]">{item.source}</span>
                <span className="text-[#3D4450] text-[9px]">{item.time}</span>
              </div>
              <div className="text-[#9CA3AF] text-[10px] leading-relaxed">{item.text}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

const features = [
  {
    id: "cross-tool",
    size: "large",
    label: "Cross-tool synthesis",
    description:
      "Pulls from Slack threads, Notion docs, Linear comments, and meeting transcripts into a unified timeline",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M2 8h12M8 2v12" stroke="#00D4AA" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="8" cy="8" r="2" fill="#00D4AA" fillOpacity="0.3" />
      </svg>
    ),
    visual: <LargeCardMockup />,
  },
  {
    id: "smart-relevance",
    size: "medium",
    label: "Smart relevance",
    description:
      "AI filters noise and surfaces only what matters for this specific ticket",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M14 2L10 6M6 10L2 14M14 2H10M14 2V6"
          stroke="#00D4AA"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <path
          d="M2 2L5 5M11 11L14 14"
          stroke="#00D4AA"
          strokeWidth="1.5"
          strokeLinecap="round"
          opacity="0.5"
        />
      </svg>
    ),
    visual: (
      <div className="mt-4 space-y-1.5">
        {[
          { label: "Highly relevant", score: 94, color: "#00D4AA" },
          { label: "Relevant", score: 71, color: "#00A882" },
          { label: "Filtered out", score: 12, color: "#2D2D3A" },
        ].map((item) => (
          <div key={item.label}>
            <div className="flex justify-between text-[10px] mb-1">
              <span className="text-[#6B7280]">{item.label}</span>
              <span style={{ color: item.color }}>{item.score}%</span>
            </div>
            <div className="h-1 rounded-full" style={{ background: "rgba(255,255,255,0.05)" }}>
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${item.score}%`, background: item.color }}
              />
            </div>
          </div>
        ))}
      </div>
    ),
  },
  {
    id: "meeting-moments",
    size: "medium",
    label: "Meeting moments",
    description:
      "Automatically finds and links the exact meeting segments where this feature was discussed",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="1" y="4" width="10" height="8" rx="1.5" stroke="#00D4AA" strokeWidth="1.5" />
        <path d="M11 7l4-2v6l-4-2V7z" stroke="#00D4AA" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    ),
    visual: (
      <div
        className="mt-4 rounded-lg p-3"
        style={{ background: "#0A0A0F", border: "1px solid rgba(255,255,255,0.05)" }}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] text-[#6B7280]">Sprint Planning - Nov 14</span>
          <span
            className="text-[10px] px-1.5 py-0.5 rounded"
            style={{ background: "rgba(0,212,170,0.1)", color: "#00D4AA" }}
          >
            14:23
          </span>
        </div>
        <div className="h-1 rounded-full mb-2" style={{ background: "rgba(255,255,255,0.06)" }}>
          <div
            className="h-full rounded-full"
            style={{
              width: "60%",
              background: "linear-gradient(90deg, rgba(0,212,170,0.3), #00D4AA)",
            }}
          />
        </div>
        <p className="text-[10px] text-[#6B7280] leading-relaxed">
          &ldquo;...and for ENG-421 we decided to go with Socket.io because...&rdquo;
        </p>
      </div>
    ),
  },
  {
    id: "decisions",
    size: "small",
    label: "Decision tracking",
    description:
      "Highlights decisions and their rationale across all sources",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M2 4h12M2 8h8M2 12h5"
          stroke="#00D4AA"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <circle cx="13" cy="12" r="2" stroke="#00D4AA" strokeWidth="1.5" />
        <path d="M12 12l.8.8L14.5 11" stroke="#00D4AA" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    visual: null,
  },
  {
    id: "fresh",
    size: "small",
    label: "Always fresh",
    description:
      "Context pages update in real-time as new information appears",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M14 8A6 6 0 1 1 8 2"
          stroke="#00D4AA"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <path
          d="M8 2l2 2-2 2"
          stroke="#00D4AA"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    visual: null,
  },
  {
    id: "privacy",
    size: "small",
    label: "Privacy-first",
    description: "Your data stays yours. SOC 2 compliant architecture.",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M8 2L3 4v4c0 3 2.3 5.3 5 6 2.7-.7 5-3 5-6V4L8 2z"
          stroke="#00D4AA"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path d="M6 8l1.5 1.5L10 6.5" stroke="#00D4AA" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    visual: null,
  },
];

export default function Features() {
  const { ref, inView } = useInView();

  return (
    <section
      id="features"
      className="relative py-24 px-6 overflow-hidden"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 50% at 20% 50%, rgba(0,212,170,0.04) 0%, transparent 60%)",
        }}
      />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Label */}
        <div
          className={`flex justify-center mb-4 transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          <span className="section-label">Features</span>
        </div>

        {/* Headline */}
        <h2
          className={`text-4xl md:text-5xl font-bold text-center text-white mb-4 tracking-tight transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          Everything an engineer needs to know,
          <br />
          in one place
        </h2>

        <p
          className={`text-center text-[#6B7280] mb-14 max-w-xl mx-auto transition-all duration-600 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "150ms" }}
        >
          ContextOS synthesizes information from all your tools so you never have to.
        </p>

        {/* Bento Grid */}
        <div
          className={`grid grid-cols-1 md:grid-cols-3 gap-4 transition-all duration-700 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
          style={{ transitionDelay: "250ms" }}
        >
          {/* Large card - spans 2 cols */}
          <div
            className="md:col-span-2 rounded-2xl p-6 card-hover relative overflow-hidden"
            style={{
              background: "#0F0F18",
              border: "1px solid rgba(255,255,255,0.07)",
            }}
          >
            <div
              className="absolute top-0 left-0 right-0 h-px"
              style={{
                background: "linear-gradient(90deg, transparent, rgba(0,212,170,0.5), transparent)",
              }}
            />
            <div className="flex items-start gap-3 mb-1">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: "rgba(0,212,170,0.08)", border: "1px solid rgba(0,212,170,0.15)" }}
              >
                {features[0].icon}
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">{features[0].label}</h3>
                <p className="text-xs text-[#6B7280] mt-0.5 leading-relaxed">
                  {features[0].description}
                </p>
              </div>
            </div>
            {features[0].visual}
          </div>

          {/* Medium cards */}
          {features.slice(1, 3).map((feature, i) => (
            <div
              key={feature.id}
              className={`rounded-2xl p-5 card-hover relative overflow-hidden ${
                i === 0 ? "" : "md:col-start-1"
              }`}
              style={{
                background: "#0F0F18",
                border: "1px solid rgba(255,255,255,0.07)",
              }}
            >
              <div
                className="absolute top-0 left-0 right-0 h-px"
                style={{
                  background:
                    "linear-gradient(90deg, transparent, rgba(0,212,170,0.3), transparent)",
                }}
              />
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center mb-3"
                style={{ background: "rgba(0,212,170,0.08)", border: "1px solid rgba(0,212,170,0.15)" }}
              >
                {feature.icon}
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">{feature.label}</h3>
              <p className="text-xs text-[#6B7280] leading-relaxed">{feature.description}</p>
              {feature.visual}
            </div>
          ))}

          {/* Small cards - 3 in a row */}
          {features.slice(3).map((feature) => (
            <div
              key={feature.id}
              className="rounded-2xl p-5 card-hover relative overflow-hidden"
              style={{
                background: "#0F0F18",
                border: "1px solid rgba(255,255,255,0.07)",
              }}
            >
              <div
                className="absolute left-0 top-4 bottom-4 w-px"
                style={{ background: "rgba(0,212,170,0.3)" }}
              />
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center mb-3"
                style={{ background: "rgba(0,212,170,0.08)", border: "1px solid rgba(0,212,170,0.15)" }}
              >
                {feature.icon}
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">{feature.label}</h3>
              <p className="text-xs text-[#6B7280] leading-relaxed">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
