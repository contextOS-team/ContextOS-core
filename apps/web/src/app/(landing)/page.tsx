import { Nav, Hero, TrustBar, ProblemSection, HowItWorks, Features, Integrations, CTASection, Footer } from '@/components/landing'

export default function LandingPage() {
  return (
    <main style={{ background: '#0A0A0F', minHeight: '100vh' }}>
      <Nav />
      <Hero />
      <TrustBar />
      <ProblemSection />
      <HowItWorks />
      <Features />
      <Integrations />
      <CTASection />
      <Footer />
    </main>
  )
}
