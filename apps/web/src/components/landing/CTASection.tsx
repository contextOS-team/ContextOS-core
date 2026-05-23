"use client";

import { useEffect, useRef, useState } from "react";
import Cal from "@calcom/embed-react";
import { usePostHog } from "posthog-js/react";
import { useInView } from "@/hooks/useInView";
import { BOOKING_SECTION_ID, CAL_BOOKING_LAYOUT, CAL_BOOKING_LINK } from "./booking";
import { LANDING_CTA } from "./landing-copy";

export default function CTASection() {
  const { ref, inView } = useInView();
  const posthog = usePostHog();
  const viewCapturedRef = useRef(false);
  const [bookingOpen, setBookingOpen] = useState(false);

  useEffect(() => {
    if (!inView || viewCapturedRef.current) return;
    viewCapturedRef.current = true;

    try {
      posthog?.capture("booking_section_viewed");
    } catch {
      // Silent fail -- analytics should never block UX
    }
  }, [inView, posthog]);

  useEffect(() => {
    if (!bookingOpen) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setBookingOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [bookingOpen]);

  const openBooking = () => {
    setBookingOpen(true);

    try {
      posthog?.capture("booking_modal_opened");
    } catch {
      // Silent fail -- analytics should never block UX
    }
  };

  return (
    <section
      id={BOOKING_SECTION_ID}
      className="relative overflow-hidden px-6 py-16 md:py-20"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div className="relative z-10 mx-auto max-w-5xl">
        <div
          className={`rounded-2xl border border-white/[0.08] bg-white/[0.025] p-6 transition-[opacity,transform] duration-700 md:p-8 ${
            inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
          }`}
        >
          <span className="section-label">Book a walkthrough</span>
          <h2 className="mt-4 max-w-3xl text-3xl font-semibold tracking-normal text-white md:text-4xl">
            Bring one messy decision.
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-[#9CA3AF] md:text-base">
            {LANDING_CTA.bookingSectionCopy}
          </p>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center">
            <button
              type="button"
              className="btn-primary min-h-10 rounded-lg px-5 py-3 text-sm font-semibold"
              onClick={openBooking}
            >
              {LANDING_CTA.primary}
            </button>
            <a
              href="#demo"
              className="btn-ghost min-h-10 rounded-lg px-5 py-3 text-center text-sm font-semibold"
            >
              {LANDING_CTA.secondary}
            </a>
          </div>

          <p className="mt-5 font-mono text-xs text-[#4B5563]">
            15 minutes. Bring one messy decision.
          </p>
        </div>
      </div>

      {bookingOpen ? (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/70 px-4 py-6 backdrop-blur-md"
          onClick={() => setBookingOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="booking-modal-title"
            className="relative flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-white/[0.10] bg-[#080A0F] shadow-[0_40px_120px_rgba(0,0,0,0.65)]"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4 border-b border-white/[0.08] px-5 py-4">
              <div>
                <p className="font-mono text-xs uppercase text-[var(--color-teal)]">
                  Booking slots
                </p>
                <h3 id="booking-modal-title" className="mt-1 text-lg font-semibold text-white">
                  Book a call
                </h3>
              </div>
              <button
                type="button"
                className="rounded-lg border border-white/[0.08] px-3 py-2 text-sm text-[#AEB6C2] transition-colors hover:text-white"
                onClick={() => setBookingOpen(false)}
              >
                Close
              </button>
            </div>

            <div className="h-[72vh] min-h-[540px] bg-[#05060A]">
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
        </div>
      ) : null}
    </section>
  );
}
