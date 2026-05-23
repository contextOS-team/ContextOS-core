// @vitest-environment jsdom

import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RemotionHeroPlayer } from '../RemotionPlayer'

const playerMock = vi.hoisted(() => ({
  addEventListener: vi.fn(),
  getCurrentFrame: vi.fn(() => 12),
  isPlaying: vi.fn(() => false),
  play: vi.fn(),
  removeEventListener: vi.fn(),
}))

const playerState = vi.hoisted(() => ({
  refDelayMs: 0,
}))

vi.mock('@/remotion/HeroComposition', () => ({
  HeroComposition: () => null,
}))

vi.mock('@remotion/player', async () => {
  const React = await vi.importActual<typeof import('react')>('react')

  return {
    Player: ({
      component,
      lazyComponent,
      initialFrame,
      controls,
      numberOfSharedAudioTags,
      initiallyMuted,
      style,
      ref,
    }: {
      component?: unknown
      lazyComponent?: unknown
      initialFrame?: number
      controls?: boolean
      numberOfSharedAudioTags?: number
      initiallyMuted?: boolean
      ref?: React.Ref<unknown>
      style?: React.CSSProperties
    }) => {
      const [ready, setReady] = React.useState(playerState.refDelayMs === 0)

      React.useEffect(() => {
        if (ready) return

        const timer = window.setTimeout(() => setReady(true), playerState.refDelayMs)
        return () => window.clearTimeout(timer)
      }, [ready])

      React.useImperativeHandle(ref, () => (ready ? playerMock : null), [ready])

      return (
        <div
          data-testid="remotion-player"
          data-has-component={String(Boolean(component))}
          data-has-lazy-component={String(Boolean(lazyComponent))}
          data-initial-frame={initialFrame ?? ''}
          data-controls={String(Boolean(controls))}
          data-shared-audio-tags={numberOfSharedAudioTags ?? ''}
          data-initially-muted={String(Boolean(initiallyMuted))}
          data-aspect-ratio={style?.aspectRatio?.toString() ?? ''}
        />
      )
    },
  }
})

describe('RemotionHeroPlayer', () => {
  beforeEach(() => {
    playerMock.addEventListener.mockClear()
    playerMock.getCurrentFrame.mockClear()
    playerMock.isPlaying.mockClear()
    playerMock.play.mockClear()
    playerMock.removeEventListener.mockClear()
    playerState.refDelayMs = 0
  })

  it('renders the hero composition from a visible first frame', () => {
    render(<RemotionHeroPlayer />)

    const player = screen.getByTestId('remotion-player')
    expect(player.getAttribute('data-has-component')).toBe('true')
    expect(player.getAttribute('data-has-lazy-component')).toBe('false')
    expect(player.getAttribute('data-initial-frame')).toBe('132')
    expect(player.getAttribute('data-controls')).toBe('false')
    expect(player.getAttribute('data-shared-audio-tags')).toBe('0')
    expect(player.getAttribute('data-initially-muted')).toBe('true')
    expect(player.getAttribute('data-aspect-ratio')).toBe('1280 / 720')
  })

  it('starts playback after mounting so the demo animates in the landing page', async () => {
    render(<RemotionHeroPlayer />)

    await waitFor(() => {
      expect(playerMock.play).toHaveBeenCalled()
    })
  })

  it('keeps trying to start playback until the Remotion player ref is ready', async () => {
    playerState.refDelayMs = 50

    render(<RemotionHeroPlayer />)

    expect(playerMock.play).not.toHaveBeenCalled()

    await waitFor(() => {
      expect(playerMock.play).toHaveBeenCalled()
    })
  })
})
