"use client";

import { useEffect, useRef, useState } from "react";
import { usePostHog } from "posthog-js/react";

function MockContextPage() {
  return (
    <div
      className="rounded-xl overflow-hidden w-full"
      style={{
        background: "#0F0F18",
        border: "1px solid rgba(255,255,255,0.08)",
        fontFamily: "monospace",
      }}
    >
      {/* Browser chrome */}
      <div
        className="flex items-center gap-2 px-4 py-3"
        style={{
          background: "#141420",
          borderBottom: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full" style={{ background: "#FF5F57" }} />
          <div className="w-3 h-3 rounded-full" style={{ background: "#FFBD2E" }} />
          <div className="w-3 h-3 rounded-full" style={{ background: "#28CA41" }} />
        </div>
        <div
          className="flex-1 mx-4 rounded-md px-3 py-1 text-xs text-[#6B7280]"
          style={{ background: "#0A0A0F" }}
        >
          app.contextos.dev/tickets/ENG-421
        </div>
      </div>

      {/* Content */}
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span
                className="text-xs px-2 py-0.5 rounded font-mono"
                style={{
                  background: "rgba(0,212,170,0.1)",
                  color: "#00D4AA",
                  border: "1px solid rgba(0,212,170,0.2)",
                }}
              >
                ENG-421
              </span>
              <span className="text-xs text-[#6B7280]">In Progress</span>
            </div>
            <h3 className="text-sm font-semibold text-white">
              Implement real-time sync for shared workspaces
            </h3>
          </div>
          <div
            className="text-xs px-2 py-1 rounded-md flex items-center gap-1"
            style={{
              background: "rgba(0,212,170,0.1)",
              color: "#00D4AA",
              border: "1px solid rgba(0,212,170,0.2)",
            }}
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
              <circle cx="5" cy="5" r="2" />
            </svg>
            Auto-generated
          </div>
        </div>

        {/* Sections */}
        <div className="space-y-3">
          {/* Background */}
          <div
            className="rounded-lg p-3"
            style={{ background: "#141420", border: "1px solid rgba(255,255,255,0.05)" }}
          >
            <div className="text-xs font-mono text-[#00D4AA] mb-2 uppercase tracking-wider">
              Background
            </div>
            <p className="text-xs text-[#9CA3AF] leading-relaxed">
              Discussed in #engineering on Nov 12. Decision was made to use WebSockets
              over polling. See Notion doc: &ldquo;Real-time Architecture v2&rdquo;
            </p>
          </div>

          {/* Sources grid */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { icon: "S", label: "4 Slack threads", color: "#4A154B" },
              { icon: "N", label: "2 Notion docs", color: "#1e1e1e" },
              { icon: "M", label: "1 Meeting clip", color: "#1a3a5c" },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-lg p-2 flex items-center gap-2"
                style={{
                  background: "#0A0A0F",
                  border: "1px solid rgba(255,255,255,0.05)",
                }}
              >
                <div
                  className="w-5 h-5 rounded text-xs flex items-center justify-center font-bold text-white"
                  style={{ background: s.color }}
                >
                  {s.icon}
                </div>
                <span className="text-[10px] text-[#6B7280]">{s.label}</span>
              </div>
            ))}
          </div>

          {/* Key decisions */}
          <div
            className="rounded-lg p-3"
            style={{ background: "#141420", border: "1px solid rgba(255,255,255,0.05)" }}
          >
            <div className="text-xs font-mono text-[#00D4AA] mb-2 uppercase tracking-wider">
              Key Decisions
            </div>
            <div className="space-y-1.5">
              {[
                "Use Socket.io v4 — decided Nov 10",
                "Redis adapter for multi-instance scaling",
                "Fallback to long polling for legacy clients",
              ].map((d) => (
                <div key={d} className="flex items-start gap-2">
                  <div
                    className="w-1.5 h-1.5 rounded-full mt-1 flex-shrink-0"
                    style={{ background: "#00D4AA" }}
                  />
                  <span className="text-xs text-[#9CA3AF]">{d}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

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

        {/* Product screenshot in perspective */}
        <div
          className={`transition-all duration-700 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"
          }`}
          style={{ transitionDelay: "450ms" }}
        >
          {/* Glow behind screenshot */}
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
                <MockContextPage />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
