import {
  LinearLogo,
  SlackLogo,
  GitHubLogo,
  NotionLogo,
  FathomLogo,
} from "@/components/icons/brand-logos";

const logos = [
  { name: "Linear", Logo: LinearLogo },
  { name: "Slack", Logo: SlackLogo },
  { name: "GitHub", Logo: GitHubLogo },
  { name: "Notion", Logo: NotionLogo },
  { name: "Fathom", Logo: FathomLogo },
];

export default function TrustBar() {
  return (
    <section
      className="relative py-10 px-6"
      style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
    >
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-col items-center gap-5">
          <p className="text-xs text-[#4B5563] uppercase tracking-widest font-mono">
            Integrates with
          </p>
          <div className="flex flex-wrap items-center justify-center gap-8 md:gap-12">
            {logos.map((logo) => (
              <div
                key={logo.name}
                className="flex items-center gap-2 text-[#3D4450] hover:text-[#6B7280] transition-colors duration-200 cursor-default"
              >
                <logo.Logo width={20} height={20} />
                <span className="text-sm font-medium">{logo.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
