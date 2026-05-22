"use client";

import { useInView } from "@/hooks/useInView";
import {
  LinearLogo,
  SlackLogo,
  GitHubLogo,
  NotionLogo,
  FathomLogo,
  TelegramLogo,
  JiraLogo,
  GitLabLogo,
} from "@/components/icons/brand-logos";
import type { ComponentType, SVGProps } from "react";

type Integration = {
  name: string;
  description: string;
  color: string;
  Logo: ComponentType<SVGProps<SVGSVGElement>>;
};

const integrations: Integration[] = [
  { name: "Linear", description: "Ticket context", color: "#5E6AD2", Logo: LinearLogo },
  { name: "Slack", description: "Decision threads", color: "#4A154B", Logo: SlackLogo },
  { name: "GitHub", description: "PR context", color: "#1e1e1e", Logo: GitHubLogo },
  { name: "Notion", description: "Docs and rationale", color: "#2a2a2a", Logo: NotionLogo },
  { name: "Telegram", description: "Group decisions", color: "#2AABEE", Logo: TelegramLogo },
  { name: "Jira", description: "Issue context", color: "#0052CC", Logo: JiraLogo },
  { name: "GitLab", description: "MR context", color: "#FC6D26", Logo: GitLabLogo },
  { name: "Fathom", description: "Meeting evidence", color: "#1a3a4a", Logo: FathomLogo },
];

export default function Integrations() {
  const { ref, inView } = useInView();

  return (
    <section
      id="integrations"
      className="relative overflow-hidden px-6 py-16"
      ref={ref as React.RefObject<HTMLElement>}
    >
      <div className="max-w-5xl mx-auto relative z-10">
        <div
          className={`mb-4 transition-[opacity,transform] duration-[600ms] ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
          }`}
        >
          <span className="section-label">Sources</span>
        </div>

        <h2
          className={`mb-4 max-w-2xl text-3xl font-semibold tracking-normal text-white transition-[opacity,transform] duration-[600ms] md:text-4xl ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "100ms" }}
        >
          Connect the places where decisions already happen.
        </h2>

        <p
          className={`mb-8 max-w-2xl text-sm leading-6 text-[#9CA3AF] transition-[opacity,transform] duration-[600ms] md:text-base ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
          }`}
          style={{ transitionDelay: "150ms" }}
        >
          ContextOS reads the source tools your team already uses, then keeps
          the evidence attached to the ticket, PR, doc, or onboarding trail it
          explains.
        </p>

        <div
          className={`flex flex-wrap gap-3 transition-[opacity,transform] duration-700 ${
            inView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
          }`}
          style={{ transitionDelay: "250ms" }}
        >
          {integrations.map((integration, i) => (
            <div
              key={integration.name}
              className="flex items-center gap-3 rounded-full border border-white/[0.08] bg-white/[0.025] px-3 py-2"
              style={{
                transitionDelay: `${i * 50}ms`,
              }}
            >
              <div
                className="flex h-8 w-8 items-center justify-center rounded-full text-white"
                style={{ background: integration.color }}
              >
                {integration.name === "Slack" ? (
                  <integration.Logo width={15} height={15} color="currentColor" />
                ) : (
                  <integration.Logo width={15} height={15} fill="currentColor" />
                )}
              </div>

              <div>
                <div className="text-sm font-medium text-white">
                  {integration.name}
                </div>
                <div className="text-xs text-[#6B7280]">
                  {integration.description}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
