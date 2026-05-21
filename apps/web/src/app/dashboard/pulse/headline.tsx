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
    <section className="max-w-3xl pt-2">
      <h1
        className="text-[26px] font-semibold leading-tight md:text-[30px]"
        style={{
          color: 'var(--foreground)',
          fontFamily: 'var(--font-geist-sans)',
          fontFeatureSettings: '"kern" 1, "liga" 1',
          textWrap: 'balance',
        }}
      >
        {headline}
      </h1>
    </section>
  )
}
