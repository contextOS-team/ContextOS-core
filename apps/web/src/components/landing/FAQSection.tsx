const faqs = [
  {
    question: "Will this replace Slack, Linear, Jira, or GitHub?",
    answer:
      "No. ContextOS sits behind those tools and preserves the why that gets scattered across them. Teams keep their existing workflow.",
  },
  {
    question: "What makes a decision verified?",
    answer:
      "A decision is verified when the record points back to original source material, involved people, rationale, and the systems it affects.",
  },
  {
    question: "Does this need perfect docs to work?",
    answer:
      "No. The point is to recover decisions from messy operational traces: threads, PRs, meetings, tickets, and architecture notes.",
  },
  {
    question: "Who is this for first?",
    answer:
      "Engineering and product teams where context loss slows reviews, enterprise work, incident follow-up, or onboarding.",
  },
] as const;

export default function FAQSection() {
  return (
    <section id="faq" className="px-6 py-16 md:py-20">
      <div className="mx-auto grid max-w-6xl gap-8 md:grid-cols-[0.75fr_1fr]">
        <div>
          <span className="section-label">FAQ</span>
          <h2 className="mt-4 max-w-lg text-3xl font-semibold tracking-normal text-white md:text-4xl">
            Keep your tools. Recover the decisions inside them.
          </h2>
        </div>

        <div className="divide-y divide-white/[0.08] border-y border-white/[0.08]">
          {faqs.map((faq) => (
            <details key={faq.question} className="group py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-5 text-left text-base font-medium text-white">
                {faq.question}
                <span className="text-xl font-light text-[#6B7280] transition-transform group-open:rotate-45">
                  +
                </span>
              </summary>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[#9CA3AF]">
                {faq.answer}
              </p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}
