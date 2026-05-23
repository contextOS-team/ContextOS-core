import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const remotionRoot = join(process.cwd(), 'src/remotion')

describe('landing Remotion product demo reel', () => {
  it('uses a dedicated ContextOS product demo composition instead of abstract scene stacks', () => {
    const source = readFileSync(join(remotionRoot, 'HeroComposition.tsx'), 'utf8')

    expect(source).toContain('ContextOSProductDemoScene')
    expect(source).not.toContain('DecisionMoatScene')
    expect(source).not.toContain('DashboardScene')
    expect(source).not.toContain('SourcesScene')
    expect(source).not.toContain('ContextScene')
  })

  it('shows one focused cited-answer workflow instead of a feature tour', () => {
    const scenePath = join(remotionRoot, 'scenes/ContextOSProductDemoScene.tsx')

    expect(existsSync(scenePath)).toBe(true)

    const source = readFileSync(scenePath, 'utf8')

    expect(source).toContain('useCurrentFrame')
    expect(source).toContain('spring')
    expect(source).toContain('interpolate')
    expect(source).toContain('ANIMATION STORYBOARD')
    expect(source).toContain('Ask ContextOS')
    expect(source).toContain('Why did we choose WebSockets?')
    expect(source).toContain('Answer')
    expect(source).toContain('Resolving citations')
    expect(source).toContain('answerFocus')
    expect(source).toContain('mobile sync needed sub-500ms updates')
    expect(source).toContain('Citations')
    expect(source).toContain('Slack')
    expect(source).toContain('GitHub')
    expect(source).not.toContain('Ticket context')
    expect(source).not.toContain('PR review')
    expect(source).not.toContain('Onboarding')
    expect(source).not.toContain('247 decisions')
    expect(source).not.toContain('Sources synced')
    expect(source).not.toContain('ContextOS / demo workspace')
    expect(source).not.toContain('The moat')
    expect(source).not.toContain('Know why your company works the way it does.')
  })

  it('uses the product demo duration for the landing player', () => {
    const source = readFileSync(join(remotionRoot, 'constants.ts'), 'utf8')

    expect(source).toContain('CONTEXTOS_PRODUCT_DEMO_DURATION')
    expect(source).not.toContain('DECISION_MOAT_DURATION')
    expect(source).toMatch(/TOTAL_DURATION\s*=\s*CONTEXTOS_PRODUCT_DEMO_DURATION/)
  })
})
