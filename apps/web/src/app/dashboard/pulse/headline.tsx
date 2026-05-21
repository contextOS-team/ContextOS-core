'use client'

import { computeHeadline } from './headline-rules'
import type { Delta } from './types'

interface HeadlineProps {
  delta: Delta
  lastVisitedAt: Date | null
}

export function Headline({ delta, lastVisitedAt }: HeadlineProps) {
  const { headline } = computeHeadline(delta, lastVisitedAt)

  return (
    <section className="max-w-2xl">
      <h1
        className="text-[30px] font-medium leading-[1.18] md:text-[34px]"
        style={{
          color: 'var(--foreground)',
          fontFamily: 'var(--font-geist-sans)',
          fontFeatureSettings: '"kern" 1, "liga" 1',
          letterSpacing: '-0.018em',
          textWrap: 'balance',
        }}
      >
        {headline}
      </h1>
    </section>
  )
}
