import { ImageResponse } from 'next/og'
import { LANDING_SEO } from '@/components/landing/landing-copy'

export const runtime = 'edge'
export const alt = LANDING_SEO.title
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

export default async function LandingOGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          background: '#0A0A0F',
          color: '#FFFFFF',
          fontFamily: 'sans-serif',
          padding: '72px',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 16,
            marginBottom: 56,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 58,
              height: 58,
              borderRadius: 14,
              background: 'rgba(73,214,181,0.14)',
              border: '2px solid rgba(73,214,181,0.3)',
            }}
          >
            <svg width="28" height="28" viewBox="0 0 14 14" fill="none">
              <path
                d="M2 7C2 4.24 4.24 2 7 2C8.38 2 9.63 2.56 10.54 3.46"
                stroke="#49D6B5"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <path
                d="M12 7C12 9.76 9.76 12 7 12C5.62 12 4.37 11.44 3.46 10.54"
                stroke="#49D6B5"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <circle cx="7" cy="7" r="1.5" fill="#49D6B5" />
            </svg>
          </div>
          <div style={{ display: 'flex', fontSize: 28, fontWeight: 700 }}>
            ContextOS
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            maxWidth: 900,
            fontSize: 62,
            fontWeight: 700,
            lineHeight: 1.05,
            marginBottom: 28,
          }}
        >
          Know why your company works the way it does.
        </div>

        <div
          style={{
            display: 'flex',
            maxWidth: 840,
            fontSize: 25,
            lineHeight: 1.45,
            color: 'rgba(255,255,255,0.68)',
          }}
        >
          Source-backed decision memory for engineering teams, with evidence
          from Slack, meetings, PRs, docs, and tickets.
        </div>

        <div
          style={{
            display: 'flex',
            gap: 12,
            marginTop: 52,
          }}
        >
          {['Decision receipt', 'Ticket context', 'PR context'].map((name) => (
            <div
              key={name}
              style={{
                display: 'flex',
                padding: '10px 20px',
                borderRadius: 24,
                background: 'rgba(255,255,255,0.055)',
                border: '1px solid rgba(255,255,255,0.10)',
                color: 'rgba(255,255,255,0.72)',
                fontSize: 17,
              }}
            >
              {name}
            </div>
          ))}
        </div>

        <div
          style={{
            position: 'absolute',
            bottom: 34,
            left: 72,
            display: 'flex',
            fontSize: 17,
            color: 'rgba(73,214,181,0.72)',
          }}
        >
          contextos.pro
        </div>
      </div>
    ),
    { ...size }
  )
}
