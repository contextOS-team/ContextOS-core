"use client";

import { useInView } from "@/hooks/useInView";
import {
  GitHubLogo,
  GitLabLogo,
  JiraLogo,
  LinearLogo,
  NotionLogo,
  SlackLogo,
  TelegramLogo,
} from "@/components/icons/brand-logos";

const sourceTools = [
  { name: "Slack", Logo: SlackLogo },
  { name: "GitHub", Logo: GitHubLogo },
  { name: "GitLab", Logo: GitLabLogo },
  { name: "Jira", Logo: JiraLogo },
  { name: "Linear", Logo: LinearLogo },
  { name: "Notion", Logo: NotionLogo },
  { name: "Telegram", Logo: TelegramLogo },
];

const steps = [
  {
    number: "01",
    title: "Connect your sources",
    description:
      "Bring Slack, meetings, GitHub/GitLab, Jira/Linear, Notion, and Telegram into one workspace-level source map.",
    visual: (
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {sourceTools.map((tool) => (
          <div
            key={tool.name}
            className="flex items-center gap-2 rounded-lg px-3 py-2"
            style={{
              background: "rgba(var(--color-teal-rgb),0.04)",
              border: "1px solid rgba(var(--color-teal-rgb),0.1)",
            }}
          >
            <tool.Logo width={14} height={14} color="currentColor" fill="currentColor" />
            <span className="text-xs text-[#9CA3AF]">{tool.name}</span>
          </div>
        ))}
      </div>
    ),
  },
  {
    number: "02",
    title: "ContextOS detects decisions",
    description:
      "The system identifies what was decided, who was involved, why it was decided, and the source links behind each claim.",
    visual: (
      <div className="space-y-2">
        {[
          "Decision: keep source ingestion workspace-scoped",
          "Why: tenancy prevents cross-workspace leakage",
          "Sources: Slack thread, Fathom meeting, GitHub PR",
        ].map((line) => (
          <div
            key={line}
            className="rounded-lg px-3 py-2 font-mono text-xs text-[#B8C0CA]"
            style={{
              background: "rgba(255,255,255,0.025)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            {line}
          </div>
        ))}
      </div>
    ),
  },
  {
    number: "03",
    title: "Use the decision graph where work happens",
    description:
      "Decision graph context follows onboarding, docs, tickets, and PRs so teammates see the source-backed why without opening every tool.",
    visual: (
      <div className="grid gap-2">
        {["Onboarding", "Docs", "Tickets", "PRs"].map((surface) => (
          <div
            key={surface}
            className="flex items-center justify-between rounded-lg px-3 py-2 text-xs"
            style={{
              background: "#0A0A0F",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <span className="text-[#D7DCE2]">{surface}</span>
            <span className="font-mono text-[var(--color-teal)]">decision memory</span>
          </div>
        ))}
      </div>
    ),
  },
];

export default function HowItWorks() {
  const { ref, inView } = useInView();

  return (
    <section
      id="how-it-works"
      className="relative overflow-hidden px-6 py-24"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 80% 40% at 50% 50%, rgba(var(--color-teal-rgb),0.03) 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10 mx-auto max-w-5xl">
        <div className="mb-16 max-w-2xl">
          <div
            className={`mb-4 transition-[opacity,transform] duration-[600ms] ${
              inView ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
            }`}
          >
            <span className="section-label">How It Works</span>
          </div>

          <h2
            className={`text-4xl font-bold tracking-tight text-white transition-[opacity,transform] duration-[600ms] md:text-5xl ${
              inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
            }`}
            style={{ transitionDelay: "100ms" }}
          >
            Turn scattered source history into a company knowledge graph.
          </h2>
        </div>

        <div className="space-y-5">
          {steps.map((step, i) => (
            <div
              key={step.number}
              className={`grid gap-5 rounded-xl p-5 transition-[opacity,transform] duration-700 md:grid-cols-[0.82fr_1fr] md:p-6 ${
                inView ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
              }`}
              style={{
                transitionDelay: `${200 + i * 130}ms`,
                background: "#0F0F18",
                border: "1px solid rgba(255,255,255,0.07)",
              }}
            >
              <div>
                <p className="mb-3 font-mono text-xs font-semibold text-[var(--color-teal)]">
                  {step.number}
                </p>
                <h3 className="mb-2 text-xl font-semibold text-white">{step.title}</h3>
                <p className="text-sm leading-6 text-[#6B7280]">{step.description}</p>
              </div>
              <div>{step.visual}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
