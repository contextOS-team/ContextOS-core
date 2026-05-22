import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { LANDING_FORBIDDEN_PHRASES } from '../landing-copy'

const landingSourceFiles = [
  'Nav.tsx',
  'Hero.tsx',
  'DecisionReceiptVisual.tsx',
  'ProblemSection.tsx',
  'HowItWorks.tsx',
  'Features.tsx',
  'ProductDemo.tsx',
  'Integrations.tsx',
  'TrustBar.tsx',
  'CTASection.tsx',
  'Footer.tsx',
  'booking.ts',
]

const explicitlyForbidden = [
  'SOC 2 compliant architecture',
  '2-6 hours',
  '2 minutes',
  'AI synthesis complete',
  'Start coding immediately',
  'Stop gathering context',
  'auto-generates everything you need to know',
  'AI-native OS',
  'company brain',
]

describe('landing claim guardrails', () => {
  it('keeps unsupported launch claims out of visible landing source', () => {
    const sourceRoot = join(process.cwd(), 'src/components/landing')
    const files = landingSourceFiles.map((file) => ({
      file,
      source: readFileSync(join(sourceRoot, file), 'utf8'),
    }))

    const phrases = new Set([
      ...LANDING_FORBIDDEN_PHRASES,
      ...explicitlyForbidden,
    ])

    for (const phrase of phrases) {
      for (const { file, source } of files) {
        expect(source, `${phrase} should not appear in ${file}`).not.toContain(phrase)
      }
    }
  })
})
