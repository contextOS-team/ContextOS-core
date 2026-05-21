"use client";

import { useInView } from "@/hooks/useInView";

export default function ProductDemo() {
  const { ref, inView } = useInView();

  return (
    <section
      id="demo"
      className="relative py-24 px-6 overflow-hidden"
      ref={ref as React.RefObject<HTMLElement>}
    >
      {/* Background */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 50% at 50% 50%, rgba(var(--color-teal-rgb),0.05) 0%, transparent 60%)",
        }}
      />

      <div className="max-w-4xl mx-auto relative z-10">
        {/* Label */}
        <div
          className={`flex justify-center mb-4 transition-[opacity,transform] duration-[600ms] ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          <span className="section-label">See It In Action</span>
        </div>

        {/* Headline */}
        <h2
          className={`text-4xl md:text-5xl font-bold text-center text-white mb-4 tracking-tight transition-[opacity,transform] duration-[600ms] ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          Watch a context page build itself
        </h2>

        <p
          className={`text-center text-[#6B7280] mb-12 transition-[opacity,transform] duration-[600ms] ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "150ms" }}
        >
          Real context page generated from a Linear ticket in under 30 seconds
        </p>

        {/* Video frame */}
        <div
          className={`relative transition-[opacity,transform] duration-700 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
          style={{ transitionDelay: "250ms" }}
        >
          {/* Glow */}
          <div
            className="absolute -inset-8 pointer-events-none"
            style={{
              background:
                "radial-gradient(ellipse at center, rgba(var(--color-teal-rgb),0.1) 0%, transparent 65%)",
              filter: "blur(20px)",
            }}
          />

          {/* Browser mockup */}
          <div
            className="relative rounded-2xl overflow-hidden"
            style={{
              border: "1px solid rgba(255,255,255,0.08)",
              boxShadow:
                "0 40px 80px rgba(0,0,0,0.5), 0 0 40px rgba(var(--color-teal-rgb),0.06)",
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
                app.contextos.dev/demo
              </div>
            </div>

            {/* Video placeholder */}
            <div
              className="relative flex items-center justify-center"
              style={{ background: "#0A0A0F", aspectRatio: "16/9" }}
            >
              {/* Animated background */}
              <div
                className="absolute inset-0"
                style={{
                  backgroundImage:
                    "radial-gradient(circle, rgba(255,255,255,0.03) 1px, transparent 1px)",
                  backgroundSize: "24px 24px",
                }}
              />

              {/* Play button */}
              <div className="relative flex flex-col items-center gap-4 z-10">
                <button
                  className="btn-play w-16 h-16 rounded-full flex items-center justify-center"
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 20 20"
                    fill="var(--color-teal)"
                    style={{ marginLeft: "3px" }}
                  >
                    <path d="M4 3l14 7-14 7V3z" />
                  </svg>
                </button>
                <div className="text-center">
                  <p className="text-sm text-[#9CA3AF] font-medium">Demo video coming soon</p>
                  <p className="text-xs text-[#4B5563] mt-1">
                    Add your Screen Studio recording here
                  </p>
                </div>
              </div>

              {/* Decorative elements */}
              <div
                className="absolute bottom-4 left-4 right-4 flex items-center gap-2"
              >
                <div
                  className="h-1 rounded-full flex-1"
                  style={{ background: "rgba(255,255,255,0.05)" }}
                >
                  <div
                    className="h-full rounded-full w-1/3"
                    style={{ background: "rgba(var(--color-teal-rgb),0.4)" }}
                  />
                </div>
                <span className="text-[10px] text-[#4B5563] font-mono">0:28</span>
              </div>
            </div>
          </div>
        </div>

        {/* Caption */}
        <p
          className={`text-center text-xs text-[#4B5563] mt-4 font-mono transition-[opacity,transform] duration-[600ms] ${
            inView ? "opacity-100" : "opacity-0"
          }`}
          style={{ transitionDelay: "500ms" }}
        >
          Real context page generated from a Linear ticket in under 30 seconds
        </p>
      </div>
    </section>
  );
}
