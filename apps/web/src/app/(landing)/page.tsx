import { Nav, Hero, DecisionGraphSection, UseCasesSection, Integrations, FAQSection, CTASection, Footer } from '@/components/landing'

export default function LandingPage() {
  return (
    <main style={{ background: '#0A0A0F', minHeight: '100vh' }}>
      <Nav />
      <Hero />
      <DecisionGraphSection />
      <UseCasesSection />
      <Integrations />
      <FAQSection />
      <CTASection />
      <Footer />
    </main>
  )
}
