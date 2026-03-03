"use client";

import { useState } from "react";
import { useInView } from "@/hooks/useInView";

export default function CTASection() {
  const { ref, inView } = useInView();
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email) {
      setSubmitted(true);
    }
  };

  return (
    <section
      id="waitlist"
      className="relative py-24 px-6 overflow-hidden"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div className="max-w-2xl mx-auto relative z-10">
        {/* Card with gradient border */}
        <div
          className={`relative rounded-3xl p-px transition-all duration-700 ${
            inView ? "opacity-100 scale-100" : "opacity-0 scale-95"
          }`}
          style={{
            background: "linear-gradient(135deg, rgba(0,212,170,0.4), rgba(0,212,170,0.1), rgba(0,212,170,0.05), rgba(0,212,170,0.2))",
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
                  "radial-gradient(ellipse 80% 60% at 50% 0%, rgba(0,212,170,0.08) 0%, transparent 60%)",
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
                  background: "rgba(0,212,170,0.08)",
                  border: "1px solid rgba(0,212,170,0.2)",
                  color: "#00D4AA",
                  fontFamily: "monospace",
                }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full animate-pulse"
                  style={{ background: "#00D4AA" }}
                />
                Join the waitlist
              </div>

              <h2 className="text-3xl md:text-4xl font-bold text-white mb-4 tracking-tight">
                Ready to stop{" "}
                <span className="teal-gradient-text">context-switching?</span>
              </h2>

              <p className="text-[#6B7280] mb-10 text-sm leading-relaxed">
                Join the waitlist. Early access is free for teams under 10 engineers.
              </p>

              {!submitted ? (
                <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
                  <input
                    type="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="flex-1 px-4 py-3 rounded-xl text-sm text-white placeholder:text-[#4B5563] outline-none transition-all duration-200"
                    style={{
                      background: "rgba(255,255,255,0.05)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                    onFocus={(e) => {
                      (e.currentTarget as HTMLElement).style.borderColor =
                        "rgba(0,212,170,0.4)";
                      (e.currentTarget as HTMLElement).style.boxShadow =
                        "0 0 0 3px rgba(0,212,170,0.08)";
                    }}
                    onBlur={(e) => {
                      (e.currentTarget as HTMLElement).style.borderColor =
                        "rgba(255,255,255,0.1)";
                      (e.currentTarget as HTMLElement).style.boxShadow = "none";
                    }}
                  />
                  <button
                    type="submit"
                    className="px-5 py-3 rounded-xl text-sm font-semibold transition-all duration-200 whitespace-nowrap"
                    style={{
                      background: "#00D4AA",
                      color: "#0A0A0F",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.boxShadow =
                        "0 0 25px rgba(0,212,170,0.5)";
                      (e.currentTarget as HTMLElement).style.background = "#33DCBB";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.boxShadow = "none";
                      (e.currentTarget as HTMLElement).style.background = "#00D4AA";
                    }}
                  >
                    Get Early Access
                  </button>
                </form>
              ) : (
                <div
                  className="flex items-center justify-center gap-3 py-3 px-6 rounded-xl max-w-md mx-auto"
                  style={{
                    background: "rgba(0,212,170,0.08)",
                    border: "1px solid rgba(0,212,170,0.2)",
                  }}
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path
                      d="M3 8l3.5 3.5 6.5-7"
                      stroke="#00D4AA"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <span className="text-sm text-[#00D4AA]">
                    You&apos;re on the list! We&apos;ll be in touch soon.
                  </span>
                </div>
              )}

              <p className="text-xs text-[#3D4450] mt-5 font-mono">
                No credit card required - Set up in 5 minutes - Cancel anytime
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
