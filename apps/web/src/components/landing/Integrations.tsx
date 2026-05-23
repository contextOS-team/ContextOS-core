"use client";

import type { ComponentType, CSSProperties, RefObject, SVGProps } from "react";
import { useInView } from "@/hooks/useInView";
import {
  ConfluenceLogo,
  FathomLogo,
  FigmaLogo,
  GranolaLogo,
  GitHubLogo,
  GitLabLogo,
  GoogleDocsLogo,
  JiraLogo,
  LinearLogo,
  LoomLogo,
  NotionLogo,
  SlackLogo,
  TelegramLogo,
} from "@/components/icons/brand-logos";

type Integration = {
  name: string;
  Logo: ComponentType<SVGProps<SVGSVGElement>>;
  rotate: number;
};

const connectedSources: Integration[] = [
  { name: "Slack", Logo: SlackLogo, rotate: -2 },
  { name: "Linear", Logo: LinearLogo, rotate: 3 },
  { name: "GitHub", Logo: GitHubLogo, rotate: -6 },
  { name: "GitLab", Logo: GitLabLogo, rotate: 5 },
  { name: "Notion", Logo: NotionLogo, rotate: -3 },
  { name: "Fathom", Logo: FathomLogo, rotate: 4 },
  { name: "Jira", Logo: JiraLogo, rotate: -4 },
  { name: "Telegram", Logo: TelegramLogo, rotate: 2 },
];

const requestedSources: Integration[] = [
  { name: "Google Docs", Logo: GoogleDocsLogo, rotate: -4 },
  { name: "Confluence", Logo: ConfluenceLogo, rotate: 5 },
  { name: "Loom", Logo: LoomLogo, rotate: -2 },
  { name: "Granola", Logo: GranolaLogo, rotate: 2 },
  { name: "Figma", Logo: FigmaLogo, rotate: 4 },
];

const sourceFacts = [
  {
    value: "8",
    label: "sources connected",
    body: "Chats, tickets, PRs, docs, and meetings stay in their own tools. ContextOS connects the evidence into one decision record.",
  },
  {
    value: "1",
    label: "verified decision",
    body: "Each decision record keeps the rationale, people, affected systems, and original source line together.",
  },
] as const;

const rowClassName =
  "-mx-6 flex snap-x items-center gap-2 overflow-x-auto px-6 pb-5 [scrollbar-width:none] md:-mx-2 md:flex-wrap md:overflow-visible md:px-0 md:pb-0 md:pr-0 md:[scrollbar-width:auto] [&::-webkit-scrollbar]:hidden";

const SourceTile = ({
  source,
  tone = "color",
}: {
  source: Integration;
  tone?: "color" | "mono";
}) => (
  <div
    className="group relative flex h-14 w-14 shrink-0 snap-start items-center justify-center rounded-xl border border-white/[0.08] bg-[#0F1218] text-white shadow-[0_18px_45px_rgba(0,0,0,0.32)] ring-1 ring-white/[0.04] transition-transform duration-200 rotate-[var(--source-rotate)] hover:-translate-y-1 hover:rotate-0 hover:border-[rgba(var(--color-teal-rgb),0.35)] hover:shadow-[0_18px_50px_rgba(73,214,181,0.12)] sm:h-16 sm:w-16 md:h-20 md:w-20"
    style={{ "--source-rotate": `${source.rotate}deg` } as CSSProperties}
    aria-label={source.name}
    title={source.name}
  >
    <span className="absolute inset-2 rounded-lg bg-[radial-gradient(circle_at_50%_35%,rgba(var(--color-teal-rgb),0.10),transparent_58%)] opacity-0 transition-opacity duration-200 group-hover:opacity-100" />
    <source.Logo
      width={36}
      height={36}
      color={tone === "mono" ? "currentColor" : undefined}
      fill="currentColor"
      className="relative h-7 w-7 text-white sm:h-8 sm:w-8 md:h-9 md:w-9"
    />
  </div>
);

export default function Integrations() {
  const { ref, inView } = useInView();

  return (
    <section
      id="integrations"
      className="relative isolate scroll-mt-24 overflow-hidden border-y border-white/[0.06] bg-[#08090D] px-6 py-16 text-white md:py-24"
      ref={ref as RefObject<HTMLElement>}
    >
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_18%,rgba(var(--color-teal-rgb),0.13),transparent_34%),linear-gradient(180deg,rgba(255,255,255,0.035),transparent_28%,rgba(255,255,255,0.025))]" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,rgba(var(--color-teal-rgb),0.42),transparent)]" />
      <div className="relative z-10 mx-auto max-w-6xl">
        <div
          className={`mb-10 flex items-center gap-4 font-mono text-xs uppercase tracking-[0.18em] text-[var(--color-teal)] transition-[opacity,transform] duration-[600ms] md:text-sm ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          <span className="h-px w-12 bg-[rgba(var(--color-teal-rgb),0.55)]" />
          <span>Source coverage</span>
        </div>

        <div
          className={`mb-12 max-w-3xl transition-[opacity,transform] duration-[600ms] ${
            inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
          }`}
          style={{ transitionDelay: "80ms" }}
        >
          <h2 className="text-3xl font-semibold tracking-normal text-white md:text-4xl">
            Keep your tools. Connect the decisions inside them.
          </h2>
        </div>

        <div className="grid gap-8 border-b border-white/[0.08] pb-14 md:grid-cols-2 md:pb-16">
          {sourceFacts.map((fact, index) => (
            <div
              key={fact.label}
              className={`transition-[opacity,transform] duration-[600ms] ${
                inView ? "translate-y-0 opacity-100" : "translate-y-6 opacity-0"
              }`}
              style={{ transitionDelay: `${100 + index * 90}ms` }}
            >
              <p className="text-5xl font-semibold tracking-normal text-white md:text-6xl">
                {fact.value}
              </p>
              <p className="mt-3 text-lg font-medium text-white md:text-xl">
                {fact.label}
              </p>
              <p className="mt-4 max-w-md text-base leading-7 text-[#AEB6C2]">
                {fact.body}
              </p>
            </div>
          ))}
        </div>

        <div
          className={`pt-16 transition-[opacity,transform] duration-700 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
          style={{ transitionDelay: "250ms" }}
        >
          <div className="mb-9 flex items-center gap-4 font-mono text-xs uppercase tracking-[0.18em] text-[#6B7280] md:text-sm">
            <span className="h-px w-12 bg-white/20" />
            <span>Connected now</span>
          </div>
          <div className={rowClassName} aria-label="Connected source logos">
            {connectedSources.map((source) => (
              <SourceTile key={source.name} source={source} />
            ))}
          </div>

          <div className="mt-16 flex items-center gap-4 font-mono text-xs uppercase tracking-[0.18em] text-[#6B7280] md:text-sm">
            <span className="h-px w-12 bg-white/20" />
            <span>Queued next</span>
          </div>
          <div
            className={`${rowClassName} mt-9`}
            aria-label="Requested source logos"
          >
            {requestedSources.map((source) => (
              <SourceTile key={source.name} source={source} tone="mono" />
            ))}
          </div>

          <a
            href="#booking"
            className="mt-8 inline-flex rotate-[-1.5deg] rounded-xl border border-[rgba(var(--color-teal-rgb),0.28)] bg-[rgba(var(--color-teal-rgb),0.10)] px-6 py-4 text-sm font-semibold text-[var(--color-teal)] shadow-[0_18px_50px_rgba(0,0,0,0.28)] transition-transform hover:-translate-y-1 hover:rotate-0 hover:bg-[rgba(var(--color-teal-rgb),0.16)] md:mt-10"
          >
            Want a source connected? Show us the workflow
          </a>
        </div>
      </div>
    </section>
  );
}
