"use client";

import { useEffect, useRef } from "react";
import Cal from "@calcom/embed-react";
import { usePostHog } from "posthog-js/react";
import { useInView } from "@/hooks/useInView";
import { BOOKING_SECTION_ID, CAL_BOOKING_LAYOUT, CAL_BOOKING_LINK } from "./booking";
import { LANDING_CTA } from "./landing-copy";

export default function CTASection() {
  const { ref, inView } = useInView();
  const posthog = usePostHog();
  const viewCapturedRef = useRef(false);

  useEffect(() => {
    if (!inView || viewCapturedRef.current) return;
    viewCapturedRef.current = true;

    try {
      posthog?.capture("booking_section_viewed");
    } catch {
      // Silent fail -- analytics should never block UX
    }
  }, [inView, posthog]);

  return (
    <section
      id={BOOKING_SECTION_ID}
      className="relative overflow-hidden px-6 py-20"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div className="relative z-10 mx-auto max-w-5xl">
        <div
          className={`mb-8 transition-[opacity,transform] duration-700 ${
            inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
          }`}
        >
          <span className="section-label">Book a walkthrough</span>
          <h2 className="mt-4 max-w-2xl text-3xl font-semibold tracking-normal text-white md:text-4xl">
            See your decision graph from your own workspace.
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-[#9CA3AF] md:text-base">
            {LANDING_CTA.bookingSectionCopy}
          </p>
        </div>

        <div
          className={`cal-booking-shell text-left transition-[opacity,transform] duration-700 ${
            inView ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
          }`}
          style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.10)",
          }}
        >
          <div className="cal-booking-frame">
            <Cal
              calLink={CAL_BOOKING_LINK}
              config={{
                layout: CAL_BOOKING_LAYOUT,
                theme: "dark",
              }}
              style={{
                width: "100%",
                height: "100%",
                overflow: "scroll",
              }}
            />
          </div>
        </div>

        <p className="mt-5 font-mono text-xs text-[#3D4450]">
          Powered by Cal.com - no redirect required
        </p>
      </div>
    </section>
  );
}
