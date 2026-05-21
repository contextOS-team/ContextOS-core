"use client";

import { useState, useEffect } from "react";
import { usePostHog } from "posthog-js/react";
import { BOOKING_CTA_LABEL, BOOKING_SECTION_HREF } from "./booking";

export default function Nav() {
  const posthog = usePostHog();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const links = [
    { label: "Features", href: "#features" },
    { label: "How It Works", href: "#how-it-works" },
    { label: "Integrations", href: "#integrations" },
  ];

  const captureBookCallClick = () => {
    try {
      posthog?.capture("cta_nav_book_call_click");
    } catch {
      /* silent */
    }
  };

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-50 transition-[background-color,border-color] duration-300"
      style={{
        background: scrolled
          ? "rgba(10,10,15,0.9)"
          : "rgba(10,10,15,0.0)",
        backdropFilter: scrolled ? "blur(16px)" : "none",
        borderBottom: scrolled
          ? "1px solid rgba(255,255,255,0.06)"
          : "1px solid transparent",
      }}
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <a href="#" className="flex items-center gap-2 group">
            <div
              className="w-7 h-7 rounded-md flex items-center justify-center"
              style={{ background: "rgba(var(--color-teal-rgb),0.15)", border: "1px solid rgba(var(--color-teal-rgb),0.3)" }}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path
                  d="M2 7C2 4.24 4.24 2 7 2C8.38 2 9.63 2.56 10.54 3.46"
                  stroke="var(--color-teal)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <path
                  d="M12 7C12 9.76 9.76 12 7 12C5.62 12 4.37 11.44 3.46 10.54"
                  stroke="var(--color-teal)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <circle cx="7" cy="7" r="1.5" fill="var(--color-teal)" />
              </svg>
            </div>
            <span
              className="text-[15px] font-semibold tracking-tight text-white group-hover:text-[var(--color-teal)] transition-colors"
            >
              ContextOS
            </span>
          </a>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-7">
            {links.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-sm text-[#9CA3AF] hover:text-white transition-colors duration-200"
              >
                {link.label}
              </a>
            ))}
          </div>

          {/* CTA */}
          <div className="hidden md:flex items-center gap-3">
            <a
              href={BOOKING_SECTION_HREF}
              className="btn-primary text-sm font-medium px-4 py-2 rounded-lg"
              onClick={captureBookCallClick}
            >
              {BOOKING_CTA_LABEL}
            </a>
          </div>

          {/* Mobile hamburger */}
          <button
            className="md:hidden p-2 text-[#9CA3AF] hover:text-white transition-colors"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              {menuOpen ? (
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                />
              ) : (
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z"
                />
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div
          className="md:hidden"
          style={{
            background: "rgba(10,10,15,0.97)",
            borderBottom: "1px solid rgba(255,255,255,0.06)",
          }}
        >
          <div className="px-6 py-4 flex flex-col gap-3">
            {links.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-sm text-[#9CA3AF] hover:text-white transition-colors py-1"
                onClick={() => setMenuOpen(false)}
              >
                {link.label}
              </a>
            ))}
            <a
              href={BOOKING_SECTION_HREF}
              className="text-sm font-medium px-4 py-2 rounded-lg text-center mt-2"
              style={{ background: "var(--color-teal)", color: "#0A0A0F" }}
              onClick={() => {
                captureBookCallClick();
                setMenuOpen(false);
              }}
            >
              {BOOKING_CTA_LABEL}
            </a>
          </div>
        </div>
      )}
    </nav>
  );
}
