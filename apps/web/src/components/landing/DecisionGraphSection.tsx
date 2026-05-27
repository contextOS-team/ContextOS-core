"use client";

import type { RefObject } from "react";
import { useInView } from "@/hooks/useInView";
import { DecisionGraphDemo } from "./DecisionGraphDemo";

export default function DecisionGraphSection() {
  const { ref, inView } = useInView();

  return (
    <section
      id="demo"
      className="relative scroll-mt-28 overflow-hidden px-6 pb-16 pt-8 md:scroll-mt-32 md:pb-20 md:pt-14"
      ref={ref as RefObject<HTMLElement>}
    >
      <div className="relative z-10 mx-auto max-w-7xl">
        <div className="mb-8 grid gap-5 md:grid-cols-[0.88fr_0.6fr] md:items-end md:justify-between">
          <div
            className={`transition-[opacity,transform] duration-[600ms] ${
              inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
            }`}
          >
            <span className="section-label">Decision graph</span>
            <h2 className="mt-4 max-w-3xl text-3xl font-semibold tracking-normal text-white md:text-5xl">
              Watch scattered context become one verified decision.
            </h2>
          </div>

          <p
            className={`max-w-md text-sm leading-6 text-[#9CA3AF] transition-[opacity,transform] duration-[600ms] md:justify-self-end ${
              inView ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
            }`}
            style={{ transitionDelay: "100ms" }}
          >
            Slack, meetings, PRs, docs, and tickets stay separate. ContextOS
            shows the decision that connects them.
          </p>
        </div>

        <div
          className={`transition-[opacity,transform] duration-700 ${
            inView ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
          }`}
          style={{ transitionDelay: "180ms" }}
        >
          <DecisionGraphDemo />
        </div>
      </div>
    </section>
  );
}
