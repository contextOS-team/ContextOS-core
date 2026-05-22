export default function Footer() {
  const links = {
    product: [
      { label: "Features", href: "#features" },
      { label: "How It Works", href: "#how-it-works" },
      { label: "Integrations", href: "#integrations" },
    ],
    company: [
      { label: "Twitter / X", href: "#" },
      { label: "GitHub", href: "#" },
    ],
  };

  return (
    <footer
      className="relative py-16 px-6"
      style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
    >
      <div className="max-w-6xl mx-auto">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-10 mb-12">
          {/* Brand */}
          <div className="md:col-span-2">
            <div className="flex items-center gap-2 mb-4">
              <div
                className="w-7 h-7 rounded-md flex items-center justify-center"
                style={{
                  background: "rgba(var(--color-teal-rgb),0.15)",
                  border: "1px solid rgba(var(--color-teal-rgb),0.3)",
                }}
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
              <span className="text-[15px] font-semibold tracking-tight text-white">ContextOS</span>
            </div>
            <p className="text-sm text-[#4B5563] leading-relaxed max-w-xs">
              Source-backed decision memory for engineering and product teams.
            </p>
            <p className="text-xs text-[#3D4450] mt-4">
              Built with love in KZ
            </p>
          </div>

          {/* Product */}
          <div>
            <div className="text-xs font-mono uppercase tracking-widest text-[#3D4450] mb-4">
              Product
            </div>
            <ul className="space-y-2.5">
              {links.product.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-[#4B5563] hover:text-[#9CA3AF] transition-colors duration-200"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>

          {/* Company */}
          <div>
            <div className="text-xs font-mono uppercase tracking-widest text-[#3D4450] mb-4">
              Company
            </div>
            <ul className="space-y-2.5">
              {links.company.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.href}
                    className="text-sm text-[#4B5563] hover:text-[#9CA3AF] transition-colors duration-200"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Bottom row */}
        <div
          className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-8"
          style={{ borderTop: "1px solid rgba(255,255,255,0.04)" }}
        >
          <p className="text-xs text-[#3D4450]">&copy; 2026 ContextOS. All rights reserved.</p>
          <div className="flex items-center gap-4">
            {["Privacy", "Terms", "Security"].map((item) => (
              <a
                key={item}
                href="#"
                className="text-xs text-[#3D4450] hover:text-[#6B7280] transition-colors"
              >
                {item}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
