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
        <span className="text-[var(--color-teal)]">ENG-421</span>
        <span className="text-[#4B5563]">&#183;</span>
        <span className="text-[#6B7280]">Unified Context</span>
        <div className="ml-auto flex gap-1">
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: `rgba(var(--color-teal-rgb),${0.4 - i * 0.1})` }}
            />
          ))}
        </div>
      </div>

      {/* Timeline */}
      <div className="p-3 space-y-2">
        {[
          { source: "Slack", time: "Nov 12", text: "Decided on WebSockets approach", color: "#4A154B" },
          { source: "GitHub", time: "Nov 13", text: "RFC merged, 4 approvals", color: "#1e1e1e" },
          { source: "Notion", time: "Nov 10", text: "Architecture decision recorded", color: "#2a2a2a" },
          { source: "Meet", time: "Nov 14", text: "Sprint planning clip — 14:23", color: "#1a3a5c" },
          { source: "Linear", time: "Nov 15", text: "Ticket assigned to you", color: "#5E6AD2" },
        ].map((item, i) => (
          <div key={i} className="flex items-start gap-2">
            <div className="flex flex-col items-center">
              <div
                className="w-4 h-4 rounded flex items-center justify-center text-white font-bold flex-shrink-0"
                style={{ background: item.color, fontSize: "7px" }}
              >
                {item.source[0]}
              </div>
              {i < 4 && (
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

function GraphMockup() {
  return (
    <div className="mt-4 relative" style={{ height: 120 }}>
      <svg width="100%" height="100%" viewBox="0 0 240 120" fill="none" aria-hidden="true">
        {/* Edges */}
        <line x1="120" y1="30" x2="50" y2="80" stroke="rgba(var(--color-teal-rgb),0.2)" strokeWidth="1" />
        <line x1="120" y1="30" x2="190" y2="80" stroke="rgba(var(--color-teal-rgb),0.2)" strokeWidth="1" />
        <line x1="120" y1="30" x2="120" y2="100" stroke="rgba(var(--color-teal-rgb),0.15)" strokeWidth="1" />
        <line x1="50" y1="80" x2="120" y2="100" stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
        <line x1="190" y1="80" x2="120" y2="100" stroke="rgba(255,255,255,0.06)" strokeWidth="1" />

        {/* Decision node (diamond) */}
        <g transform="translate(120, 30)">
          <rect x="-10" y="-10" width="20" height="20" rx="3" transform="rotate(45)" fill="rgba(var(--color-teal-rgb),0.15)" stroke="var(--color-teal)" strokeWidth="1" />
          <text x="18" y="4" fill="#9CA3AF" fontSize="8" fontFamily="monospace">Decision</text>
        </g>

        {/* Person node */}
        <g transform="translate(50, 80)">
          <circle r="10" fill="rgba(var(--color-teal-rgb),0.08)" stroke="rgba(var(--color-teal-rgb),0.3)" strokeWidth="1" />
          <text x="0" y="3" fill="var(--color-teal)" fontSize="8" textAnchor="middle" fontFamily="monospace">A</text>
          <text x="16" y="3" fill="#6B7280" fontSize="8" fontFamily="monospace">Alex</text>
        </g>

        {/* Person node */}
        <g transform="translate(190, 80)">
          <circle r="10" fill="rgba(var(--color-teal-rgb),0.08)" stroke="rgba(var(--color-teal-rgb),0.3)" strokeWidth="1" />
          <text x="0" y="3" fill="var(--color-teal)" fontSize="8" textAnchor="middle" fontFamily="monospace">S</text>
          <text x="-28" y="3" fill="#6B7280" fontSize="8" textAnchor="end" fontFamily="monospace">Sara</text>
        </g>

        {/* Ticket node */}
        <g transform="translate(120, 100)">
          <rect x="-20" y="-8" width="40" height="16" rx="3" fill="rgba(94,106,210,0.15)" stroke="#5E6AD2" strokeWidth="1" />
          <text x="0" y="3" fill="#9CA3AF" fontSize="7" textAnchor="middle" fontFamily="monospace">ENG-421</text>
        </g>
      </svg>
    </div>
  );
}

function DecisionMockup() {
  return (
    <div
      className="mt-4 rounded-lg p-3"
      style={{ background: "#0A0A0F", border: "1px solid rgba(255,255,255,0.05)" }}
    >
      <div className="flex items-center gap-2 mb-2">
        <div
          className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0"
          style={{ background: "rgba(var(--color-teal-rgb),0.15)", border: "1px solid rgba(var(--color-teal-rgb),0.3)" }}
        >
          <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
            <path d="M2 4l1.5 1.5L6 3" stroke="var(--color-teal)" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <span className="text-[10px] text-[#9CA3AF]">Use WebSockets for real-time sync</span>
      </div>
      <div className="flex items-center gap-3 ml-6">
        <div className="flex -space-x-1.5">
          {["A", "S"].map((initial) => (
            <div
              key={initial}
              className="w-4 h-4 rounded-full flex items-center justify-center text-[7px] font-bold"
              style={{ background: "rgba(var(--color-teal-rgb),0.12)", border: "1px solid #0A0A0F", color: "var(--color-teal)" }}
            >
              {initial}
            </div>
          ))}
        </div>
        <span className="text-[9px] text-[#4B5563]">Slack &middot; 2d ago</span>
        <span
          className="text-[8px] px-1.5 py-0.5 rounded ml-auto"
          style={{ background: "rgba(94,106,210,0.12)", color: "#5E6AD2" }}
        >
          ENG-421
        </span>
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
      "Pulls from Slack, Telegram, Jira, Notion, and meeting transcripts into a unified timeline",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M2 8h12M8 2v12" stroke="var(--color-teal)" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="8" cy="8" r="2" fill="var(--color-teal)" fillOpacity="0.3" />
      </svg>
    ),
    visual: <LargeCardMockup />,
  },
  {
    id: "knowledge-graph",
    size: "medium",
    label: "Knowledge graph",
    description:
      "See how people, decisions, tickets, and conversations connect across your team",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <circle cx="4" cy="4" r="2" stroke="var(--color-teal)" strokeWidth="1.5" />
        <circle cx="12" cy="4" r="2" stroke="var(--color-teal)" strokeWidth="1.5" />
        <circle cx="8" cy="13" r="2" stroke="var(--color-teal)" strokeWidth="1.5" />
        <path d="M6 4h4M5 5.5l2 5.5M11 5.5l-2 5.5" stroke="var(--color-teal)" strokeWidth="1" strokeLinecap="round" opacity="0.5" />
      </svg>
    ),
    visual: <GraphMockup />,
  },
  {
    id: "decisions",
    size: "medium",
    label: "Decision tracking",
    description:
      "Surfaces decisions from Slack and Telegram, links them to the people and tickets they affect",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M2 4h12M2 8h8M2 12h5"
          stroke="var(--color-teal)"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
        <circle cx="13" cy="12" r="2" stroke="var(--color-teal)" strokeWidth="1.5" />
        <path d="M12 12l.8.8L14.5 11" stroke="var(--color-teal)" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    visual: <DecisionMockup />,
  },
  {
    id: "activity",
    size: "small",
    label: "Activity feed",
    description:
      "Real-time stream of events across all your integrations",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M2 8h2l2-4 4 8 2-4h2"
          stroke="var(--color-teal)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    ),
    visual: null,
  },
  {
    id: "digests",
    size: "small",
    label: "Smart digests",
    description:
      "AI-generated daily summaries of decisions, actions, and topics from team chats",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="2" width="12" height="12" rx="2" stroke="var(--color-teal)" strokeWidth="1.5" />
        <path d="M5 6h6M5 8.5h4M5 11h2" stroke="var(--color-teal)" strokeWidth="1.2" strokeLinecap="round" />
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
          stroke="var(--color-teal)"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />
        <path d="M6 8l1.5 1.5L10 6.5" stroke="var(--color-teal)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
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
            "radial-gradient(ellipse 70% 50% at 20% 50%, rgba(var(--color-teal-rgb),0.04) 0%, transparent 60%)",
        }}
      />

      <div className="max-w-6xl mx-auto relative z-10">
        {/* Label */}
        <div
          className={`flex justify-center mb-4 transition-[opacity,transform] duration-[600ms] ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          <span className="section-label">Features</span>
        </div>

        {/* Headline */}
        <h2
          className={`text-4xl md:text-5xl font-bold text-center text-white mb-4 tracking-tight transition-[opacity,transform] duration-[600ms] ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          Everything an engineer needs to know,
          <br />
          in one place
        </h2>

        <p
          className={`text-center text-[#6B7280] mb-14 max-w-xl mx-auto transition-[opacity,transform] duration-[600ms] ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "150ms" }}
        >
          ContextOS synthesizes information from all your tools so you never have to.
        </p>

        {/* Bento Grid */}
        <div
          className={`grid grid-cols-1 md:grid-cols-3 gap-4 transition-[opacity,transform] duration-700 ${
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
                background: "linear-gradient(90deg, transparent, rgba(var(--color-teal-rgb),0.5), transparent)",
              }}
            />
            <div className="flex items-start gap-3 mb-1">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: "rgba(var(--color-teal-rgb),0.08)", border: "1px solid rgba(var(--color-teal-rgb),0.15)" }}
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
                    "linear-gradient(90deg, transparent, rgba(var(--color-teal-rgb),0.3), transparent)",
                }}
              />
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center mb-3"
                style={{ background: "rgba(var(--color-teal-rgb),0.08)", border: "1px solid rgba(var(--color-teal-rgb),0.15)" }}
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
                style={{ background: "rgba(var(--color-teal-rgb),0.3)" }}
              />
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center mb-3"
                style={{ background: "rgba(var(--color-teal-rgb),0.08)", border: "1px solid rgba(var(--color-teal-rgb),0.15)" }}
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
