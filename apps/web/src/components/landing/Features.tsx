"use client";

import { useInView } from "@/hooks/useInView";

const features = [
  {
    label: "Source-backed decisions",
    description:
      "ContextOS detects decisions in Slack, Telegram, meetings, docs, and code review, then keeps the original source links attached.",
    detail: "decision, rationale, people, source links",
  },
  {
    label: "Decision graph",
    description:
      "See how decisions connect to systems, tickets, PRs, docs, teammates, and follow-up work across the company knowledge graph.",
    detail: "people, systems, tickets, PRs",
  },
  {
    label: "Context pages",
    description:
      "Open ticket context, PR context, docs context, or onboarding context with the missing why already attached.",
    detail: "tickets, PRs, docs, onboarding",
  },
  {
    label: "Source links",
    description:
      "Every decision record points back to concrete evidence so a teammate can verify the Slack thread, meeting note, PR, issue, or doc.",
    detail: "Slack, Fathom, GitHub, Linear, Notion",
  },
  {
    label: "Verification state",
    description:
      "Decision records make confidence explicit with verified and needs-review states instead of hiding uncertainty behind generic AI output.",
    detail: "Verified / Needs review",
  },
  {
    label: "Next: action layer",
    description:
      "Next: close the loop with task creation, doc drafts, owner confirmation, and PR context comments.",
    detail: "roadmap",
  },
] as const;

export default function Features() {
  const { ref, inView } = useInView();

  return (
    <section
      id="features"
      className="relative overflow-hidden px-6 py-24"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 50% at 20% 50%, rgba(var(--color-teal-rgb),0.04) 0%, transparent 60%)",
        }}
      />

      <div className="relative z-10 mx-auto max-w-6xl">
        <div
          className={`mb-4 flex justify-center transition-[opacity,transform] duration-[600ms] ${
            inView ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
          }`}
        >
          <span className="section-label">Features</span>
        </div>

        <h2
          className={`mb-4 text-center text-4xl font-bold tracking-tight text-white transition-[opacity,transform] duration-[600ms] md:text-5xl ${
            inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          Current MVP: decision memory your team can inspect.
        </h2>

        <p
          className={`mx-auto mb-14 max-w-2xl text-center text-[#6B7280] transition-[opacity,transform] duration-[600ms] ${
            inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
          }`}
          style={{ transitionDelay: "150ms" }}
        >
          Source-backed by default. Keep trust claims narrow until security docs
          are published.
        </p>

        <div
          className={`grid grid-cols-1 gap-4 transition-[opacity,transform] duration-700 md:grid-cols-3 ${
            inView ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
          }`}
          style={{ transitionDelay: "250ms" }}
        >
          {features.map((feature, index) => (
            <article
              key={feature.label}
              className={`card-hover relative overflow-hidden rounded-xl p-5 ${
                index === 0 ? "md:col-span-2" : ""
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
                    "linear-gradient(90deg, transparent, rgba(var(--color-teal-rgb),0.35), transparent)",
                }}
              />
              <div className="mb-4 flex items-start justify-between gap-4">
                <h3 className="text-base font-semibold text-white">{feature.label}</h3>
                <span className="rounded-full border border-[rgba(var(--color-teal-rgb),0.20)] bg-[rgba(var(--color-teal-rgb),0.08)] px-2.5 py-1 font-mono text-[10px] text-[var(--color-teal)]">
                  {feature.detail}
                </span>
              </div>
              <p className="text-sm leading-6 text-[#6B7280]">{feature.description}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
