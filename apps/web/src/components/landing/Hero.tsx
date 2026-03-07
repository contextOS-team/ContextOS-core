"use client";

import { useEffect, useRef, useState } from "react";
import { usePostHog } from "posthog-js/react";
import dynamic from "next/dynamic";

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
          borderRadius: "1rem",
        }}
      />
    ),
  }
);

export default function Hero() {
  const posthog = usePostHog();
  const [visible, setVisible] = useState(false);
  const [scrollY, setScrollY] = useState(0);
  const heroRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTimeout(() => setVisible(true), 100);
    const handleScroll = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const heroHeight = heroRef.current?.offsetHeight ?? 900;
  const progress = Math.min(scrollY / (heroHeight * 0.5), 1);
  const rotateX = 12 * (1 - progress);
  const scale = 0.88 + 0.12 * progress;

  return (
    <section
      ref={heroRef}
      className="relative min-h-screen flex flex-col items-center justify-center pt-24 pb-16 px-6 overflow-hidden"
    >
      {/* Background radial glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,212,170,0.08) 0%, transparent 60%)",
        }}
      />

      {/* Dot grid */}
      <div
        className="absolute inset-0 pointer-events-none opacity-40"
        style={{
          backgroundImage:
            "radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      />

      {/* Content */}
      <div className="relative z-10 max-w-4xl mx-auto text-center">
        {/* Badge */}
        <div
          className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs mb-8 transition-all duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
          style={{
            background: "rgba(0,212,170,0.08)",
            border: "1px solid rgba(0,212,170,0.2)",
            color: "#00D4AA",
            fontFamily: "monospace",
            transitionDelay: "0ms",
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full animate-pulse"
            style={{ background: "#00D4AA" }}
          />
          Now in early access
        </div>

        {/* Headline */}
        <h1
          className={`text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight text-white mb-6 leading-[1.05] transition-all duration-700 ${
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
          className={`text-lg md:text-xl text-[#9CA3AF] max-w-2xl mx-auto mb-10 leading-relaxed transition-all duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "200ms" }}
        >
          Engineers waste 2-6 hours per ticket hunting through Slack, Notion, and
          meeting notes. ContextOS auto-generates everything you need to know —
          before you write a single line.
        </p>

        {/* CTAs */}
        <div
          className={`flex flex-col sm:flex-row items-center justify-center gap-3 mb-16 transition-all duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "300ms" }}
        >
          <a
            href="#waitlist"
            className="btn-primary px-6 py-3 rounded-lg text-sm font-semibold"
            onClick={() => {
              try {
                posthog?.capture("cta_hero_click");
              } catch {
                /* silent */
              }
            }}
          >
            Get Early Access
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
          className={`transition-all duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          }`}
          style={{ transitionDelay: "450ms" }}
        >
          {/* Glow behind video */}
          <div
            className="relative mx-auto max-w-3xl"
            style={{ perspective: "1200px" }}
          >
            <div
              className="absolute -inset-8 pointer-events-none"
              style={{
                background:
                  "radial-gradient(ellipse at center, rgba(0,212,170,0.12) 0%, transparent 65%)",
                filter: "blur(20px)",
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
                className="rounded-2xl overflow-hidden"
                style={{
                  boxShadow:
                    "0 40px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.06), 0 0 40px rgba(0,212,170,0.08)",
                }}
              >
                <RemotionHeroPlayer />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
