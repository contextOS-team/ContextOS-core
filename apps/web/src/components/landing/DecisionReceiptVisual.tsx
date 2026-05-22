const people = ["Daulet", "Alex", "Sara"] as const;

const sourceChips = [
  "Slack thread - 14 messages",
  "Fathom meeting - 32 min",
  "GitHub PR #418",
  "Linear ENG-421",
  "Architecture doc",
] as const;

const affectedSystems = ["Sync engine", "Decision graph", "Onboarding"] as const;

const relatedWork = ["ENG-421", "PR #418", "Architecture doc"] as const;

const graphNodes = [
  { label: "Decision", x: 132, y: 44, kind: "decision" },
  { label: "Slack thread", x: 54, y: 106, kind: "source" },
  { label: "PR #418", x: 218, y: 104, kind: "source" },
  { label: "ENG-421", x: 86, y: 170, kind: "ticket" },
  { label: "Sync engine", x: 204, y: 172, kind: "system" },
] as const;

function ReceiptSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <h3 className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6B7280]">
        {title}
      </h3>
      {children}
    </section>
  );
}

function GraphPreview() {
  return (
    <div
      className="relative overflow-hidden rounded-xl border border-white/[0.07] bg-[#0A0A0F] p-3"
      aria-label="Decision graph preview"
    >
      <svg
        className="h-[218px] w-full"
        viewBox="0 0 272 218"
        fill="none"
        role="img"
        aria-labelledby="decision-graph-title"
      >
        <title id="decision-graph-title">
          Decision graph preview connecting a decision to sources, work, and systems.
        </title>
        <path
          d="M132 56 L54 96 M132 56 L218 94 M54 118 L86 158 M218 116 L204 160 M132 58 L204 158 M132 58 L86 158"
          stroke="rgba(73,214,181,0.28)"
          strokeWidth="1.4"
          strokeLinecap="round"
        />
        {graphNodes.map((node) => {
          const isDecision = node.kind === "decision";
          return (
            <g key={node.label} transform={`translate(${node.x} ${node.y})`}>
              {isDecision ? (
                <rect
                  x="-16"
                  y="-16"
                  width="32"
                  height="32"
                  rx="8"
                  fill="rgba(73,214,181,0.16)"
                  stroke="#49D6B5"
                  strokeWidth="1.2"
                  transform="rotate(45)"
                />
              ) : (
                <rect
                  x="-42"
                  y="-15"
                  width="84"
                  height="30"
                  rx="10"
                  fill={
                    node.kind === "system"
                      ? "rgba(73,214,181,0.11)"
                      : "rgba(255,255,255,0.045)"
                  }
                  stroke={
                    node.kind === "system"
                      ? "rgba(73,214,181,0.36)"
                      : "rgba(255,255,255,0.10)"
                  }
                  strokeWidth="1"
                />
              )}
              <text
                y={isDecision ? 5 : 4}
                textAnchor="middle"
                fill={isDecision ? "#49D6B5" : "#D7DCE2"}
                fontFamily="var(--font-mono), JetBrains Mono, monospace"
                fontSize={isDecision ? 10 : 9}
                fontWeight="600"
              >
                {node.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function DecisionReceiptVisual() {
  return (
    <div className="relative mx-auto w-full max-w-5xl">
      <div
        className="absolute -inset-8 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(var(--color-teal-rgb),0.16) 0%, transparent 68%)",
          filter: "blur(28px)",
        }}
      />
      <div className="relative grid gap-4 rounded-xl border border-white/[0.09] bg-[#0F0F18] p-4 shadow-[0_32px_80px_rgba(0,0,0,0.45)] md:grid-cols-[1.12fr_0.88fr] md:p-5">
        <article className="space-y-5 rounded-xl border border-white/[0.07] bg-[#0A0A0F] p-4 md:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] pb-4">
            <div>
              <p className="font-mono text-xs font-semibold text-[#49D6B5]">
                Decision Receipt
              </p>
              <p className="mt-1 text-xs text-[#6B7280]">
                Source-backed trail from a fictional workspace
              </p>
            </div>
            <span className="inline-flex items-center gap-2 rounded-full border border-[#49D6B5]/30 bg-[#49D6B5]/10 px-3 py-1 font-mono text-xs font-semibold text-[#49D6B5]">
              <span className="h-1.5 w-1.5 rounded-full bg-[#49D6B5]" />
              Verified
            </span>
          </div>

          <div>
            <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#6B7280]">
              Decision
            </p>
            <h2 className="mt-2 text-2xl font-semibold leading-tight text-white md:text-3xl">
              Use workspace-scoped source ingestion
            </h2>
          </div>

          <ReceiptSection title="Why">
            <p className="text-sm leading-6 text-[#B8C0CA]">
              The team kept finding duplicate context across shared tools. The
              Slack thread, Fathom meeting, and PR review agreed that every
              source should resolve through workspace tenancy before it reaches
              the decision graph.
            </p>
          </ReceiptSection>

          <div className="grid gap-4 sm:grid-cols-2">
            <ReceiptSection title="People involved">
              <div className="flex flex-wrap gap-2">
                {people.map((person) => (
                  <span
                    key={person}
                    className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-[#D7DCE2]"
                  >
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#49D6B5]/12 font-mono text-[10px] font-semibold text-[#49D6B5]">
                      {person[0]}
                    </span>
                    {person}
                  </span>
                ))}
              </div>
            </ReceiptSection>

            <ReceiptSection title="Affected systems">
              <div className="flex flex-wrap gap-2">
                {affectedSystems.map((system) => (
                  <span
                    key={system}
                    className="rounded-full border border-[#49D6B5]/18 bg-[#49D6B5]/8 px-3 py-1.5 font-mono text-xs text-[#B8F1E4]"
                  >
                    {system}
                  </span>
                ))}
              </div>
            </ReceiptSection>
          </div>

          <ReceiptSection title="Original sources">
            <div className="flex flex-wrap gap-2">
              {sourceChips.map((source) => (
                <span
                  key={source}
                  className="inline-flex cursor-default items-center gap-2 rounded-full border border-white/[0.10] bg-white/[0.055] px-3 py-1.5 font-mono text-xs text-[#D7DCE2] shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]"
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-[#49D6B5]" />
                  {source}
                </span>
              ))}
            </div>
          </ReceiptSection>

          <ReceiptSection title="Related work">
            <div className="flex flex-wrap gap-2">
              {relatedWork.map((item) => (
                <span
                  key={item}
                  className="rounded-lg border border-white/[0.08] bg-[#141420] px-3 py-2 font-mono text-xs text-[#9CA3AF]"
                >
                  {item}
                </span>
              ))}
            </div>
          </ReceiptSection>
        </article>

        <aside className="space-y-3 rounded-xl border border-white/[0.07] bg-[#0A0A0F] p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-mono text-xs font-semibold text-white">
                Decision graph
              </p>
              <p className="mt-1 text-xs text-[#6B7280]">
                Five connected proof nodes
              </p>
            </div>
            <span className="rounded-full border border-[#49D6B5]/25 bg-[#49D6B5]/10 px-2.5 py-1 font-mono text-[10px] font-semibold text-[#49D6B5]">
              5 nodes
            </span>
          </div>
          <GraphPreview />
        </aside>
      </div>
    </div>
  );
}
