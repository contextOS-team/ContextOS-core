"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { usePostHog } from "posthog-js/react";
import dynamic from "next/dynamic";
import { BOOKING_CTA_LABEL, BOOKING_SECTION_HREF } from "./booking";

const RemotionHeroPlayer = dynamic(
  () =>
    import("./RemotionPlayer").then((m) => ({
      default: m.RemotionHeroPlayer,
    })),
  {
    ssr: false,
    loading: () => (
      <div
        style={{
          width: "100%",
          aspectRatio: "16/9",
          backgroundColor: "#0A0A0F",
          borderRadius: "0 0 1rem 1rem",
        }}
      />
    ),
  }
);

/** Scene boundaries in frames (must match remotion/constants.ts) */
const SCENE_FRAMES = [0, 90, 195, 315]; // dashboard, sources, context, end

export default function Hero() {
  const posthog = usePostHog();
  const [visible, setVisible] = useState(false);
  const [scrollY, setScrollY] = useState(0);
  const [activeStep, setActiveStep] = useState(0);
  const heroRef = useRef<HTMLDivElement>(null);

  const onFrameUpdate = useCallback((frame: number) => {
    const next =
      frame < SCENE_FRAMES[1]
        ? 0
        : frame < SCENE_FRAMES[2]
          ? 1
          : 2;
    setActiveStep((prev) => (prev === next ? prev : next));
  }, []);

  useEffect(() => {
    setTimeout(() => setVisible(true), 100);
    let rafId = 0;
    const handleScroll = () => {
      if (rafId) return;
      rafId = requestAnimationFrame(() => {
        setScrollY(window.scrollY);
        rafId = 0;
      });
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", handleScroll);
      cancelAnimationFrame(rafId);
    };
  }, []);

  const heroHeight = heroRef.current?.offsetHeight ?? 900;
  const progress = Math.min(scrollY / (heroHeight * 0.5), 1);
  const rotateX = 6 * (1 - progress);
  const scale = 0.94 + 0.06 * progress;

  return (
    <section
      ref={heroRef}
      className="relative min-h-screen flex flex-col items-center justify-center pt-20 pb-12 px-6 overflow-hidden"
    >
      {/* Background radial glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(var(--color-teal-rgb),0.08) 0%, transparent 60%)",
        }}
      />

      {/* Subtle dot grid */}
      <div
        className="absolute inset-0 pointer-events-none opacity-50"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(255,255,255,0.06) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />

      {/* Content */}
      <div className="relative z-10 max-w-4xl mx-auto text-center">
        {/* Badge */}
        <div
          className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs mb-8 transition-[opacity,transform] duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
          style={{
            background: "rgba(var(--color-teal-rgb),0.08)",
            border: "1px solid rgba(var(--color-teal-rgb),0.2)",
            color: "var(--color-teal)",
            fontFamily: "monospace",
            transitionDelay: "0ms",
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ background: "var(--color-teal)" }}
          />
          Now in early access
        </div>

        {/* Headline */}
        <h1
          className={`text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight text-white mb-6 leading-[1.05] transition-[opacity,transform] duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          Stop gathering context.
          <br />
          <span
            className="teal-gradient-text"
          >
            Start shipping code.
          </span>
        </h1>

        {/* Subheadline */}
        <p
          className={`text-lg md:text-xl text-[#9CA3AF] max-w-2xl mx-auto mb-10 leading-relaxed transition-[opacity,transform] duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "200ms" }}
        >
          Engineers waste hours hunting through Slack, Jira, Telegram, and
          meeting notes. ContextOS connects your tools, tracks decisions, and
          maps how your team works — automatically.
        </p>

        {/* CTAs */}
        <div
          className={`flex flex-col sm:flex-row items-center justify-center gap-3 mb-10 transition-[opacity,transform] duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "300ms" }}
        >
          <a
            href={BOOKING_SECTION_HREF}
            className="btn-primary px-6 py-3 rounded-lg text-sm font-semibold"
            onClick={() => {
              try {
                posthog?.capture("cta_hero_book_call_click");
              } catch {
                /* silent */
              }
            }}
          >
            {BOOKING_CTA_LABEL}
          </a>
          <a
            href="#how-it-works"
            className="btn-ghost px-6 py-3 rounded-lg text-sm font-medium"
            onClick={() => {
              try {
                posthog?.capture("cta_how_it_works_click");
              } catch {
                /* silent */
              }
            }}
          >
            See How It Works
          </a>
        </div>

        {/* Demo video in perspective */}
        <div
          className={`transition-[opacity,transform] duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          }`}
          style={{ transitionDelay: "450ms" }}
        >
          {/* Glow behind video */}
          <div
            className="relative mx-auto max-w-5xl"
            style={{ perspective: "1200px" }}
          >
            <div
              className="absolute -inset-8 pointer-events-none"
              style={{
                background:
                  "radial-gradient(ellipse at center, rgba(var(--color-teal-rgb),0.22) 0%, transparent 65%)",
                filter: "blur(30px)",
              }}
            />
            <div
              className="relative"
              style={{
                transform: `rotateX(${rotateX}deg) scale(${scale})`,
                transformOrigin: "50% 0%",
                transition: "transform 0.1s linear",
              }}
            >
              <div
                className="overflow-hidden rounded-2xl"
                style={{
                  boxShadow:
                    "0 40px 80px rgba(0,0,0,0.6), 0 0 60px rgba(var(--color-teal-rgb),0.12)",
                  border: "1px solid rgba(255,255,255,0.10)",
                }}
              >
                {/* Window titlebar */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "10px 14px",
                    background: "rgba(255,255,255,0.04)",
                    borderBottom: "1px solid rgba(255,255,255,0.08)",
                  }}
                >
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      background: "#FF5F57",
                    }}
                  />
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      background: "#FEBC2E",
                    }}
                  />
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: 5,
                      background: "#28C840",
                    }}
                  />
                  <span
                    style={{
                      flex: 1,
                      textAlign: "center",
                      fontSize: 12,
                      color: "rgba(255,255,255,0.3)",
                      fontFamily: "system-ui, sans-serif",
                    }}
                  >
                    ContextOS
                  </span>
                  {/* Spacer to balance the dots */}
                  <span style={{ width: 48 }} />
                </div>
                <RemotionHeroPlayer onFrameUpdate={onFrameUpdate} />
              </div>
            </div>
          </div>
          {/* Scene step indicators — synced with animation */}
          <div
            className="flex items-center justify-center gap-8 mt-6"
            style={{ fontSize: 14, fontFamily: "system-ui, sans-serif" }}
          >
            {[
              { num: "1", label: "Pick a ticket" },
              { num: "2", label: "Sources found" },
              { num: "3", label: "Context ready" },
            ].map((step, i) => {
              const isActive = activeStep === i;
              return (
                <span key={i} className="flex items-center gap-3">
                  {i > 0 && (
                    <span
                      style={{
                        color: "rgba(255,255,255,0.15)",
                        marginRight: 4,
                      }}
                    >
                      /
                    </span>
                  )}
                  <span
                    className="flex items-center gap-2"
                    style={{
                      color: isActive ? "var(--color-teal)" : "#6B7280",
                      fontWeight: isActive ? 600 : 400,
                      transition: "color 0.3s, font-weight 0.3s",
                    }}
                  >
                    <span style={{ fontWeight: 600 }}>{step.num}.</span>
                    {step.label}
                  </span>
                </span>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
