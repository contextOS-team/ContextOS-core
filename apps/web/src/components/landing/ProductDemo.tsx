"use client";

import type { RefObject } from "react";
import { useInView } from "@/hooks/useInView";

const decisionStages = [
  {
    number: "01",
    eyebrow: "Source excerpt",
    title: "Slack / #eng-mobile",
    body: "Polling leaves mobile behind after deploys.",
    meta: "Karri - 4 min ago",
    detail: "#eng-mobile",
    kind: "source",
  },
  {
    number: "02",
    eyebrow: "Cited answer",
    title: "Sub-500ms mobile sync",
    body: "We chose WebSockets because mobile sync needed sub-500ms updates during incident triage.",
    meta: "Sources [1] Slack [2] PR #418",
    detail: "answer keeps rationale attached",
    kind: "answer",
  },
  {
    number: "03",
    eyebrow: "Attached to work",
    title: "Decision travels with the work",
    body: "The same decision opens from ENG-421 and PR #418, so reviewers inherit the why.",
    meta: "ENG-421",
    detail: "PR #418",
    kind: "work",
  },
] as const;

export default function ProductDemo() {
  const { ref, inView } = useInView();

  return (
    <section
      id="demo"
      className="relative overflow-hidden px-6 pb-20 pt-6 md:pb-24 md:pt-12"
      ref={ref as RefObject<HTMLElement>}
    >
      <div className="relative z-10 mx-auto max-w-6xl" id="decision-record">
        <div className="mb-8 flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div className="max-w-3xl">
            <div
              className={`mb-4 transition-[opacity,transform] duration-[600ms] ${
                inView ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
              }`}
            >
              <span className="section-label">Decision record</span>
            </div>

            <h2
              className={`text-3xl font-semibold tracking-normal text-white transition-[opacity,transform] duration-[600ms] md:text-5xl ${
                inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
              }`}
              style={{ transitionDelay: "100ms" }}
            >
              One decision, carried through the work.
            </h2>
          </div>

          <div
            className={`max-w-sm border-l border-white/[0.08] pl-5 transition-[opacity,transform] duration-[600ms] ${
              inView ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
            }`}
            style={{ transitionDelay: "150ms" }}
          >
            <p className="font-mono text-xs uppercase tracking-[0.14em] text-[#6B7280]">
              Live record
            </p>
            <p className="mt-2 text-sm leading-6 text-[#AEB6C2]">
              Source, answer, ticket, and PR stay connected.
            </p>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          {decisionStages.map((card, index) => (
            <article
              key={card.title}
              className={`flex min-h-[265px] flex-col rounded-xl border border-white/[0.08] bg-[#0D0E14] p-4 transition-[opacity,transform] duration-700 md:p-5 ${
                inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
              }`}
              style={{ transitionDelay: `${180 + index * 90}ms` }}
            >
              <div className="mb-4 flex items-center justify-between gap-4">
                <span className="font-mono text-sm text-[#49D6B5]">
                  {card.number}
                </span>
                <span className="rounded-full border border-white/[0.08] px-3 py-1 font-mono text-[11px] uppercase tracking-[0.12em] text-[#AEB6C2]">
                  {card.eyebrow}
                </span>
              </div>

              <h3 className="mb-2 text-lg font-semibold text-white">
                {card.title}
              </h3>
              <p className="mb-5 text-sm leading-6 text-[#AEB6C2]">
                {card.body}
              </p>

              <div className="mt-auto rounded-lg border border-white/[0.07] bg-[#05060A] p-3">
                {card.kind === "source" ? (
                  <div>
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <span className="font-mono text-[11px] uppercase tracking-[0.13em] text-[#6B7280]">
                        Source line
                      </span>
                      <span className="rounded-full bg-[#36C5F0]/10 px-2 py-1 font-mono text-[11px] text-[#8DDFF6]">
                        {card.detail}
                      </span>
                    </div>
                    <p className="text-sm font-medium leading-5 text-white">
                      {card.body}
                    </p>
                    <p className="mt-3 font-mono text-[11px] text-[#6B7280]">
                      {card.meta}
                    </p>
                  </div>
                ) : null}

                {card.kind === "answer" ? (
                  <div>
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <span className="font-mono text-[11px] uppercase tracking-[0.13em] text-[#49D6B5]">
                        Answer
                      </span>
                      <span className="rounded-full border border-[#49D6B5]/20 px-2 py-1 font-mono text-[11px] text-[#49D6B5]">
                        cited
                      </span>
                    </div>
                    <p className="text-sm leading-5 text-white">
                      WebSockets stay because incident triage needs live mobile state. Polling made deploys feel stale.
                    </p>
                    <p className="mt-3 font-mono text-[11px] text-[#AEB6C2]">
                      {card.meta}
                    </p>
                  </div>
                ) : null}

                {card.kind === "work" ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between rounded-md border border-white/[0.06] bg-white/[0.035] px-3 py-2">
                      <span className="font-mono text-xs text-[#49D6B5]">
                        {card.meta}
                      </span>
                      <span className="text-xs text-[#AEB6C2]">In review</span>
                    </div>
                    <div className="flex items-center justify-between rounded-md border border-white/[0.06] bg-white/[0.035] px-3 py-2">
                      <span className="font-mono text-xs text-[#AEB6C2]">
                        {card.detail}
                      </span>
                      <span className="text-xs text-[#AEB6C2]">Decision linked</span>
                    </div>
                  </div>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
