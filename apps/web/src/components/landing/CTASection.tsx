"use client";

import { useEffect, useRef } from "react";
import Cal from "@calcom/embed-react";
import { usePostHog } from "posthog-js/react";
import { useInView } from "@/hooks/useInView";
import { BOOKING_SECTION_ID, CAL_BOOKING_LAYOUT, CAL_BOOKING_LINK } from "./booking";

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
      className="relative py-24 px-6 overflow-hidden"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div className="max-w-5xl mx-auto relative z-10">
        {/* Card with gradient border */}
        <div
          className={`relative rounded-3xl p-px transition-[opacity,transform] duration-700 ${
            inView ? "opacity-100 scale-100" : "opacity-0 scale-95"
          }`}
          style={{
            background: "linear-gradient(135deg, rgba(var(--color-teal-rgb),0.4), rgba(var(--color-teal-rgb),0.1), rgba(var(--color-teal-rgb),0.05), rgba(var(--color-teal-rgb),0.2))",
          }}
        >
          <div
            className="relative rounded-3xl p-10 md:p-14 overflow-hidden"
            style={{ background: "#0D0D17" }}
          >
            {/* Background glow */}
            <div
              className="absolute inset-0 pointer-events-none"
              style={{
                background:
                  "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(var(--color-teal-rgb),0.08) 0%, transparent 60%)",
              }}
            />

            {/* Dot grid */}
            <div
              className="absolute inset-0 pointer-events-none opacity-30"
              style={{
                backgroundImage:
                  "radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)",
                backgroundSize: "24px 24px",
              }}
            />

            <div className="relative z-10 text-center">
              {/* Badge */}
              <div
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs mb-8"
                style={{
                  background: "rgba(var(--color-teal-rgb),0.08)",
                  border: "1px solid rgba(var(--color-teal-rgb),0.2)",
                  color: "var(--color-teal)",
                  fontFamily: "monospace",
                }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full animate-pulse"
                  style={{ background: "var(--color-teal)" }}
                />
                Book a call
              </div>

              <h2 className="text-3xl md:text-4xl font-bold text-white mb-4 tracking-tight">
                Book a call to see{" "}
                <span className="teal-gradient-text">ContextOS in action.</span>
              </h2>

              <p className="text-[#9CA3AF] mb-10 text-sm leading-relaxed max-w-2xl mx-auto">
                Pick a time that works for you. The booking flow stays on this
                page, so you can schedule without leaving ContextOS.
              </p>

              <div
                className="cal-booking-shell text-left"
                style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.10)",
                  boxShadow:
                    "0 24px 70px rgba(0,0,0,0.42), 0 0 50px rgba(var(--color-teal-rgb),0.08)",
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

              <p className="text-xs text-[#3D4450] mt-5 font-mono">
                Powered by Cal.com - no redirect required
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
