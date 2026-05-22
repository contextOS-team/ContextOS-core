"use client";

import { useInView } from "@/hooks/useInView";
import {
  GitHubLogo,
  JiraLogo,
  LinearLogo,
  NotionLogo,
  SlackLogo,
  TelegramLogo,
} from "@/components/icons/brand-logos";

function MeetingIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
      <rect x="2" y="3" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="9" cy="9" r="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M13 6L16 4V14L13 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const tools = [
  { label: "Slack", icon: <SlackLogo width={18} height={18} color="currentColor" /> },
  { label: "GitHub", icon: <GitHubLogo width={18} height={18} /> },
  { label: "Linear", icon: <LinearLogo width={18} height={18} /> },
  { label: "Jira", icon: <JiraLogo width={18} height={18} fill="currentColor" /> },
  { label: "Notion", icon: <NotionLogo width={18} height={18} /> },
  { label: "Telegram", icon: <TelegramLogo width={18} height={18} fill="currentColor" /> },
  { label: "Meetings", icon: <MeetingIcon /> },
];

const questions = [
  "Why was this built this way?",
  "Who decided it?",
  "What alternatives were rejected?",
  "Is it still true?",
  "Where is the source?",
];

function ToolPill({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <div
      className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-[#9CA3AF]"
      style={{
        border: "1px solid rgba(255,255,255,0.08)",
        background: "rgba(255,255,255,0.03)",
      }}
    >
      <span className="text-[#9CA3AF]">{icon}</span>
      {label}
    </div>
  );
}

export default function ProblemSection() {
  const { ref, inView } = useInView();

  return (
    <section
      id="problem"
      className="relative overflow-hidden px-6 py-24"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 30% 50%, rgba(var(--color-teal-rgb),0.04) 0%, transparent 60%)",
        }}
      />

      <div className="relative z-10 mx-auto max-w-6xl">
        <div className="grid grid-cols-1 items-start gap-12 lg:grid-cols-12 lg:gap-16">
          <div className="lg:sticky lg:top-32 lg:col-span-4">
            <div
              className={`transition-[opacity,transform] duration-[600ms] ${
                inView ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
              }`}
            >
              <span className="section-label">The Problem</span>
            </div>

            <h2
              className={`mt-4 mb-6 text-4xl font-bold tracking-tight text-white transition-[opacity,transform] duration-[600ms] md:text-5xl ${
                inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
              }`}
              style={{ transitionDelay: "100ms" }}
            >
              Decisions disappear before the work reaches a ticket.
            </h2>

            <p
              className={`leading-relaxed text-[#6B7280] transition-[opacity,transform] duration-[600ms] ${
                inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
              }`}
              style={{ transitionDelay: "150ms" }}
            >
              Engineering knowledge management breaks when the rationale lives in
              Slack, meetings, PR reviews, docs, and planning tools but the ticket
              only carries the final request.
            </p>
          </div>

          <div
            className={`flex flex-col gap-5 transition-[opacity,transform] duration-700 lg:col-span-8 ${
              inView ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
            }`}
            style={{ transitionDelay: "250ms" }}
          >
            <div
              className="rounded-xl p-6"
              style={{
                border: "1px solid rgba(255,255,255,0.08)",
                background: "#0F0F18",
                boxShadow: "0 24px 70px rgba(0,0,0,0.32)",
              }}
            >
              <div className="mb-5 flex flex-wrap gap-2">
                {tools.map((tool) => (
                  <ToolPill key={tool.label} icon={tool.icon} label={tool.label} />
                ))}
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {questions.map((question) => (
                  <div
                    key={question}
                    className="rounded-lg px-4 py-3"
                    style={{
                      border: "1px solid rgba(255,255,255,0.07)",
                      background: "rgba(255,255,255,0.025)",
                    }}
                  >
                    <p className="font-mono text-xs text-[#9CA3AF]">{question}</p>
                  </div>
                ))}
              </div>
            </div>

            <div
              className="rounded-xl p-6"
              style={{
                border: "1px solid rgba(var(--color-teal-rgb),0.16)",
                background: "rgba(var(--color-teal-rgb),0.035)",
                boxShadow: "inset 0 0 80px rgba(var(--color-teal-rgb),0.035)",
              }}
            >
              <div className="mb-4 flex items-center justify-between gap-4">
                <h3 className="text-lg font-semibold text-white">
                  With ContextOS
                </h3>
                <span className="rounded-full border border-[rgba(var(--color-teal-rgb),0.25)] bg-[rgba(var(--color-teal-rgb),0.08)] px-3 py-1 font-mono text-xs text-[var(--color-teal)]">
                  Source-backed decisions
                </span>
              </div>
              <p className="text-sm leading-6 text-[#9CA3AF]">
                Every decision keeps the missing why: original source links,
                people involved, affected systems, related ticket context, and PR
                context that travels with the work.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
