"use client";

import type { ComponentType, RefObject, SVGProps } from "react";
import { GitBranch, MessageSquareWarning, UserRoundCheck } from "lucide-react";
import { useInView } from "@/hooks/useInView";

type UseCase = {
  title: string;
  prompt: string;
  body: string;
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
};

const useCases: UseCase[] = [
  {
    title: "Onboarding",
    prompt: "Why does this system work this way?",
    body: "New engineers see the original decision, source evidence, and people involved instead of asking around for context.",
    Icon: UserRoundCheck,
  },
  {
    title: "Architecture decisions",
    prompt: "Which PR, note, and review made this real?",
    body: "Technical choices are traced through the Slack thread, PR, ticket, meeting note, and architecture doc that shaped them.",
    Icon: GitBranch,
  },
  {
    title: "Customer escalations",
    prompt: "Why does this behavior exist for this customer?",
    body: "Teams answer with a cited internal record instead of asking five people to reconstruct the same context again.",
    Icon: MessageSquareWarning,
  },
] as const;

const comparison = [
  {
    label: "Today",
    title: "The team searches across tools by hand.",
    body: "Someone asks why a system works this way. People search Slack, ask around, open old PRs, and still get an incomplete story.",
  },
  {
    label: "With ContextOS",
    title: "A verified decision record connects the evidence.",
    body: "They open a verified decision record with the rationale, people, systems, and original sources connected.",
  },
] as const;

export default function UseCasesSection() {
  const { ref, inView } = useInView();

  return (
    <section
      id="use-cases"
      className="relative overflow-hidden px-6 py-14 md:py-[72px]"
      ref={ref as RefObject<HTMLElement>}
    >
      <div className="relative z-10 mx-auto max-w-6xl">
        <div className="grid gap-6 md:grid-cols-[0.8fr_1fr] md:items-end">
          <div
            className={`transition-[opacity,transform] duration-700 ${
              inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
            }`}
          >
            <span className="section-label">Use cases</span>
            <h2 className="mt-4 max-w-2xl text-3xl font-semibold tracking-normal text-white md:text-4xl">
              Recover the reasoning behind real work.
            </h2>
          </div>
          <p
            className={`max-w-xl text-sm leading-6 text-[#AEB6C2] transition-[opacity,transform] duration-700 md:justify-self-end md:text-base ${
              inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
            }`}
            style={{ transitionDelay: "120ms" }}
          >
            Use ContextOS when someone asks why a system, process, or customer behavior exists
            and nobody remembers the full context.
          </p>
        </div>

        <div className="mt-10 grid gap-3 md:grid-cols-2">
          {comparison.map((item, index) => (
            <article
              key={item.label}
              className={`rounded-xl border border-white/[0.08] bg-white/[0.025] p-5 transition-[opacity,transform,border-color] duration-700 ${
                item.label === "With ContextOS"
                  ? "border-[rgba(var(--color-teal-rgb),0.22)] bg-[rgba(var(--color-teal-rgb),0.045)]"
                  : ""
              } ${inView ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"}`}
              style={{ transitionDelay: `${160 + index * 90}ms` }}
            >
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[var(--color-teal)]">
                {item.label}
              </p>
              <h3 className="mt-3 text-base font-semibold text-white">
                {item.title}
              </h3>
              <p className="mt-3 text-sm leading-6 text-[#9CA3AF]">
                {item.body}
              </p>
            </article>
          ))}
        </div>

        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {useCases.map((useCase, index) => (
            <article
              key={useCase.title}
              className={`rounded-xl border border-white/[0.08] bg-white/[0.025] p-5 shadow-[0_20px_70px_rgba(0,0,0,0.24)] transition-[opacity,transform,border-color] duration-700 hover:-translate-y-1 hover:border-[rgba(var(--color-teal-rgb),0.26)] ${
                inView ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
              }`}
              style={{ transitionDelay: `${320 + index * 90}ms` }}
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[rgba(var(--color-teal-rgb),0.22)] bg-[rgba(var(--color-teal-rgb),0.08)] text-[var(--color-teal)]">
                <useCase.Icon aria-hidden="true" className="h-4 w-4" />
              </div>
              <h3 className="mt-5 text-base font-semibold text-white">
                {useCase.title}
              </h3>
              <p className="mt-3 font-mono text-[11px] leading-5 text-[var(--color-teal)]">
                {useCase.prompt}
              </p>
              <p className="mt-4 text-sm leading-6 text-[#9CA3AF]">
                {useCase.body}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
