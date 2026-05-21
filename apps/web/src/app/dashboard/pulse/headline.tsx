'use client'

import { computeHeadline } from './headline-rules'
import type { Delta, WorkspaceFreshness } from './types'

interface HeadlineProps {
  delta: Delta
  lastVisitedAt: Date | null
  freshness?: WorkspaceFreshness | null
}

export function Headline({ delta, lastVisitedAt, freshness }: HeadlineProps) {
  const { headline, subtext } = computeHeadline(
    delta,
    lastVisitedAt,
    new Date(),
    freshness ?? undefined
  )

  return (
    <section className="max-w-3xl pt-1">
      <h1 className="pulse-headline text-[26px] font-semibold leading-tight md:text-[30px]">
        {headline}
      </h1>
      {subtext && (
        <p className="pulse-headline-subtext mt-2 max-w-2xl text-sm leading-6">
          {subtext}
        </p>
      )}
    </section>
  )
}
