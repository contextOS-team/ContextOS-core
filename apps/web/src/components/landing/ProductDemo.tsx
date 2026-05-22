"use client";

import type { RefObject } from "react";
import { useInView } from "@/hooks/useInView";

const sourcePills = [
  "Slack thread",
  "Fathom meeting",
  "GitHub PR #418",
  "Linear ENG-421",
  "Notion architecture doc",
] as const;

const evidenceRows = [
  ["Decision", "Keep ingestion workspace-scoped"],
  ["Why", "Tenant-aware source collection keeps Slack, meeting, PR, and ticket evidence inside the right workspace."],
  ["People", "Daulet, Alex, Sara"],
  ["Systems", "Sync engine, decision graph, onboarding"],
] as const;

const demoCards = [
  {
    number: "02",
    title: "Ticket context",
    eyebrow: "Linear ENG-421",
    body:
      "The ticket opens with the missing why, linked sources, affected systems, and the implementation prompt your teammate needs.",
    rows: ["Decision memory attached", "Source-backed decisions", "Owner and affected systems"],
  },
  {
    number: "03",
    title: "PR context",
    eyebrow: "GitHub PR #418",
    body:
      "The same company knowledge graph follows the PR, so reviewers can verify rationale without searching Slack or meeting notes.",
    rows: ["Original source links", "Related ticket context", "Review-ready PR context"],
  },
] as const;

export default function ProductDemo() {
  const { ref, inView } = useInView();

  return (
    <section
      id="demo"
      className="relative overflow-hidden px-6 py-20"
      ref={ref as RefObject<HTMLElement>}
    >
      <div className="relative z-10 mx-auto max-w-6xl" id="decision-trail">
        <div className="mb-10 max-w-3xl">
          <div
            className={`mb-4 transition-[opacity,transform] duration-[600ms] ${
              inView ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
            }`}
          >
            <span className="section-label">Product demo</span>
          </div>

          <h2
            className={`mb-4 text-3xl font-semibold tracking-normal text-white transition-[opacity,transform] duration-[600ms] md:text-5xl ${
              inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
            }`}
            style={{ transitionDelay: "100ms" }}
          >
            Ask why a ticket exists. Get the decision trail.
          </h2>

          <p
            className={`max-w-2xl text-sm leading-6 text-[#9CA3AF] transition-[opacity,transform] duration-[600ms] md:text-base ${
              inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
            }`}
            style={{ transitionDelay: "150ms" }}
          >
            ContextOS turns engineering knowledge management into inspectable
            product context: decision memory, source-backed decisions, ticket
            context, PR context, and a company knowledge graph your team can
            verify.
          </p>
        </div>

        <div
          className={`rounded-2xl border border-white/[0.08] bg-[#0F0F18] transition-[opacity,transform] duration-700 ${
            inView ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
          }`}
          style={{ transitionDelay: "250ms" }}
        >
          <div className="flex items-center justify-between border-b border-white/[0.07] px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-[#373747]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[#373747]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[#49D6B5]" />
            </div>
            <p className="font-mono text-xs text-[#6B7280]">
              ContextOS / sample workspace
            </p>
          </div>

          <div className="grid gap-0 lg:grid-cols-[1fr_340px]">
            <div className="space-y-5 p-5 md:p-7">
              <div className="flex items-center gap-3">
                <span className="font-mono text-sm text-[#49D6B5]">01</span>
                <h3 className="text-lg font-semibold text-white">
                  Ask a decision question
                </h3>
              </div>

              <div className="rounded-xl border border-white/[0.08] bg-[#0A0A0F] p-4">
                <p className="mb-2 font-mono text-xs uppercase tracking-[0.14em] text-[#6B7280]">
                  Question
                </p>
                <p className="text-base text-white">
                  Why are we keeping source ingestion workspace-scoped?
                </p>
              </div>

              <div className="rounded-xl border border-[#49D6B5]/20 bg-[#49D6B5]/[0.04] p-4">
                <p className="mb-3 font-mono text-xs uppercase tracking-[0.14em] text-[#49D6B5]">
                  Answer
                </p>
                <p className="mb-4 text-sm leading-6 text-[#D7DCE2]">
                  The decision came from ENG-421, PR #418, and a Fathom meeting:
                  keep ingestion workspace-scoped so source evidence never
                  crosses tenant boundaries.
                </p>
                <div className="flex flex-wrap gap-2">
                  {sourcePills.map((source) => (
                    <span
                      key={source}
                      className="rounded-full border border-white/[0.09] bg-white/[0.04] px-3 py-1.5 font-mono text-xs text-[#B8C0CA]"
                    >
                      {source}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <aside className="border-t border-white/[0.07] p-5 lg:border-l lg:border-t-0 md:p-7">
              <p className="mb-4 font-mono text-xs uppercase tracking-[0.14em] text-[#6B7280]">
                Decision receipt
              </p>
              <div className="space-y-4">
                {evidenceRows.map(([label, value]) => (
                  <div key={label}>
                    <p className="mb-1 font-mono text-[11px] uppercase tracking-[0.14em] text-[#6B7280]">
                      {label}
                    </p>
                    <p className="text-sm leading-6 text-[#D7DCE2]">{value}</p>
                  </div>
                ))}
              </div>
            </aside>
          </div>
        </div>

        <div className="mt-5 grid gap-5 md:grid-cols-2">
          {demoCards.map((card, index) => (
            <article
              key={card.title}
              className={`rounded-2xl border border-white/[0.08] bg-[#0F0F18] p-5 transition-[opacity,transform] duration-700 md:p-6 ${
                inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
              }`}
              style={{ transitionDelay: `${350 + index * 100}ms` }}
            >
              <div className="mb-5 flex items-center justify-between gap-4">
                <span className="font-mono text-sm text-[#49D6B5]">
                  {card.number}
                </span>
                <span className="rounded-full border border-white/[0.08] px-3 py-1 font-mono text-xs text-[#6B7280]">
                  {card.eyebrow}
                </span>
              </div>

              <h3 className="mb-3 text-xl font-semibold text-white">
                {card.title}
              </h3>
              <p className="mb-5 text-sm leading-6 text-[#9CA3AF]">
                {card.body}
              </p>

              <div className="space-y-2">
                {card.rows.map((row) => (
                  <div
                    key={row}
                    className="rounded-lg border border-white/[0.06] bg-[#0A0A0F] px-3 py-2 font-mono text-xs text-[#D7DCE2]"
                  >
                    {row}
                  </div>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
