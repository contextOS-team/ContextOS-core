'use client'

import { computeHeadline } from './headline-rules'
import type { Delta } from './types'

interface HeadlineProps {
  delta: Delta
  lastVisitedAt: Date | null
}

export function Headline({ delta, lastVisitedAt }: HeadlineProps) {
  const { headline, subtext } = computeHeadline(delta, lastVisitedAt)

  return (
    <section className="max-w-3xl">
      <h1
        className="font-serif text-5xl leading-[1.1]"
        style={{
          color: '#ece9e3',
          letterSpacing: '-0.025em',
          fontVariationSettings: '"opsz" 32, "wght" 400',
          fontFeatureSettings: '"kern" 1, "liga" 1',
          hangingPunctuation: 'last',
          textWrap: 'balance',
        }}
      >
        {headline}
      </h1>
      <p
        className="mt-6 text-sm"
        style={{
          color: '#a8a59f',
          fontFamily: 'var(--font-geist-sans)',
          fontFeatureSettings: '"tnum" 1',
        }}
      >
        {subtext}
      </p>
    </section>
  )
}
