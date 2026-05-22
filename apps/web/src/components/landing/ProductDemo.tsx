"use client";

import { useInView } from "@/hooks/useInView";
import { DecisionReceiptVisual } from "./DecisionReceiptVisual";

const trailFields = [
  ["Decision", "Use workspace-scoped source ingestion"],
  ["Why", "The team chose tenant-aware source collection so Slack, meeting, and PR evidence never crosses workspace boundaries."],
  ["Original sources", "Slack thread, Fathom meeting, GitHub PR #418, Linear ENG-421, Architecture doc"],
  ["People involved", "Daulet, Alex, Sara"],
  ["Affected systems", "Sync engine, Decision graph, Onboarding"],
  ["Related work", "ENG-421, PR #418, Architecture doc"],
  ["Verification state", "Verified"],
] as const;

export default function ProductDemo() {
  const { ref, inView } = useInView();

  return (
    <section
      id="sample-decision-trail"
      className="relative overflow-hidden px-6 py-24"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 50%, rgba(var(--color-teal-rgb),0.05) 0%, transparent 60%)",
        }}
      />

      <div className="relative z-10 mx-auto max-w-6xl">
        <div className="mx-auto mb-12 max-w-3xl text-center">
          <div
            className={`mb-4 transition-[opacity,transform] duration-[600ms] ${
              inView ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
            }`}
          >
            <span className="section-label">Sample Trail</span>
          </div>

          <h2
            className={`mb-4 text-4xl font-bold tracking-tight text-white transition-[opacity,transform] duration-[600ms] md:text-5xl ${
              inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
            }`}
            style={{ transitionDelay: "100ms" }}
          >
            Every decision comes with receipts.
          </h2>

          <p
            className={`text-sm leading-6 text-[#9CA3AF] transition-[opacity,transform] duration-[600ms] md:text-base ${
              inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
            }`}
            style={{ transitionDelay: "150ms" }}
          >
            A source-backed decision receipt is crawlable React text, not a video
            placeholder. It gives search engines and teammates the same product
            proof: decision memory, source-backed decisions, engineering knowledge
            management, company knowledge graph, ticket context, and PR context.
          </p>
        </div>

        <div
          className={`grid gap-6 transition-[opacity,transform] duration-700 lg:grid-cols-[0.8fr_1.2fr] ${
            inView ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
          }`}
          style={{ transitionDelay: "250ms" }}
        >
          <div
            className="rounded-xl p-5"
            style={{
              background: "#0F0F18",
              border: "1px solid rgba(255,255,255,0.07)",
            }}
          >
            <div className="space-y-3">
              {trailFields.map(([label, value]) => (
                <div
                  key={label}
                  className="rounded-lg px-4 py-3"
                  style={{
                    background: "rgba(255,255,255,0.025)",
                    border: "1px solid rgba(255,255,255,0.06)",
                  }}
                >
                  <p className="mb-1 font-mono text-[11px] uppercase tracking-[0.14em] text-[#6B7280]">
                    {label}
                  </p>
                  <p className="text-sm leading-6 text-[#D7DCE2]">{value}</p>
                </div>
              ))}
            </div>
          </div>

          <DecisionReceiptVisual />
        </div>
      </div>
    </section>
  );
}
