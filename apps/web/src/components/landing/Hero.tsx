"use client";

import { useEffect, useState } from "react";
import { usePostHog } from "posthog-js/react";
import { BOOKING_SECTION_HREF } from "./booking";
import { DecisionReceiptVisual } from "./DecisionReceiptVisual";
import { LANDING_HERO } from "./landing-copy";

export default function Hero() {
  const posthog = usePostHog();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(true), 100);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden px-6 pb-12 pt-24">
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(var(--color-teal-rgb),0.08) 0%, transparent 60%)",
        }}
      />

      <div
        className="absolute inset-0 pointer-events-none opacity-50"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(255,255,255,0.06) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      <div className="relative z-10 mx-auto flex w-full max-w-6xl flex-col items-center text-center">
        <div
          className={`mb-7 inline-flex items-center gap-2 rounded-full px-3 py-1.5 font-mono text-xs transition-[opacity,transform] duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
          style={{
            background: "rgba(var(--color-teal-rgb),0.08)",
            border: "1px solid rgba(var(--color-teal-rgb),0.2)",
            color: "var(--color-teal)",
            transitionDelay: "0ms",
          }}
        >
          <span
            className="h-1.5 w-1.5 rounded-full animate-pulse"
            style={{ background: "var(--color-teal)" }}
          />
          {LANDING_HERO.badge}
        </div>

        <h1
          className={`mb-6 max-w-4xl text-5xl font-semibold leading-[1.05] tracking-normal text-white transition-[opacity,transform] duration-700 md:text-6xl lg:text-7xl ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          {LANDING_HERO.h1}
        </h1>

        <p
          className={`mx-auto mb-8 max-w-3xl text-lg leading-relaxed text-[#9CA3AF] transition-[opacity,transform] duration-700 md:text-xl ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "200ms" }}
        >
          {LANDING_HERO.subheadline}
        </p>

        <div
          className={`mb-10 flex flex-col items-center gap-4 transition-[opacity,transform] duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "300ms" }}
        >
          <p className="max-w-3xl font-mono text-xs leading-5 text-[#6B7280] md:text-sm">
            {LANDING_HERO.categoryProofLine}
          </p>
          <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href={BOOKING_SECTION_HREF}
              className="btn-primary min-h-10 rounded-lg px-6 py-3 text-sm font-semibold"
              onClick={() => {
                try {
                  posthog?.capture("cta_hero_book_call_click");
                } catch {
                  /* silent */
                }
              }}
            >
              {LANDING_HERO.primaryCta}
            </a>
            <a
              href="#decision-trail"
              className="btn-ghost min-h-10 rounded-lg px-6 py-3 text-sm font-semibold"
              onClick={() => {
                try {
                  posthog?.capture("cta_how_it_works_click");
                } catch {
                  /* silent */
                }
              }}
            >
              {LANDING_HERO.secondaryCta}
            </a>
          </div>
        </div>

        <div
          id="decision-trail"
          className={`w-full scroll-mt-24 transition-[opacity,transform] duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          }`}
          style={{ transitionDelay: "450ms" }}
        >
          <DecisionReceiptVisual />
        </div>
      </div>
    </section>
  );
}
