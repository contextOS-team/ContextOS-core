"use client";

import { usePostHog } from "posthog-js/react";
import { BOOKING_SECTION_HREF } from "./booking";
import { LANDING_HERO } from "./landing-copy";

function HeroTitle() {
  return (
    <>
      Know{" "}
      <span className="teal-glow-text relative inline-block text-[var(--color-teal)] after:absolute after:-bottom-1 after:left-0 after:h-[2px] after:w-full after:rounded-full after:bg-[linear-gradient(90deg,transparent,rgba(var(--color-teal-rgb),0.58),transparent)] after:content-['']">
        why
      </span>{" "}
      your company works the way it does.
    </>
  );
}

function HeroSubheadlineBlock() {
  return (
    <div className="mx-auto mb-7 max-w-3xl text-lg leading-relaxed text-[#AEB6C2] transition-[opacity,transform] duration-700 md:text-xl">
      <p>{LANDING_HERO.subheadline}</p>
    </div>
  );
}

function HeroAmbientBackground() {
  return (
    <div
      aria-hidden="true"
      data-testid="hero-native-background"
      className="pointer-events-none absolute inset-0 overflow-hidden bg-[#07090D]"
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,rgba(64,224,208,0.10),transparent_35%),radial-gradient(circle_at_50%_60%,rgba(64,224,208,0.04),transparent_45%),linear-gradient(180deg,rgba(255,255,255,0.035)_0%,rgba(255,255,255,0)_38%,rgba(0,209,156,0.025)_100%)]" />
      <div className="absolute inset-0 opacity-[0.13] [background-image:linear-gradient(rgba(255,255,255,0.10)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:72px_72px] [mask-image:linear-gradient(to_bottom,black_0%,black_45%,transparent_100%)]" />
      <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-white/[0.05]" />
      <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-[#07090D] to-transparent" />
    </div>
  );
}

export default function Hero() {
  const posthog = usePostHog();
  const visible = true;

  return (
    <section className="relative isolate overflow-hidden px-6 pb-10 pt-24 md:pb-12 md:pt-28">
      <HeroAmbientBackground />

      <div className="relative z-10 mx-auto flex w-full max-w-5xl flex-col items-center text-center">
        <h1
          className={`mb-6 max-w-5xl text-5xl font-semibold leading-[1.05] tracking-normal text-white transition-[opacity,transform] duration-700 md:text-6xl lg:text-[72px] ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          <HeroTitle />
        </h1>

        <div
          className={`${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "200ms" }}
        >
          <HeroSubheadlineBlock />
        </div>

        <div
          className={`flex flex-col items-center transition-[opacity,transform] duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "300ms" }}
        >
          <div className="flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href={BOOKING_SECTION_HREF}
              className="btn-primary min-h-10 rounded-lg px-6 py-3 text-sm font-semibold"
              onClick={() => {
                try {
                  posthog?.capture("cta_hero_book_walkthrough_click");
                } catch {
                  /* silent */
                }
              }}
            >
              {LANDING_HERO.primaryCta}
            </a>
            <a
              href="#demo"
              className="btn-ghost min-h-10 rounded-lg px-6 py-3 text-sm font-semibold"
              onClick={() => {
                try {
                  posthog?.capture("cta_hero_view_example_record_click");
                } catch {
                  /* silent */
                }
              }}
            >
              {LANDING_HERO.secondaryCta}
            </a>
          </div>
          <p className="mt-4 font-mono text-xs text-[#697482]">
            {LANDING_HERO.microcopy}
          </p>
        </div>
      </div>
    </section>
  );
}
