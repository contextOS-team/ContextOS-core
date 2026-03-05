import { ImageResponse } from 'next/og'

export const runtime = 'edge'
export const alt = 'ContextOS - AI-generated context for engineering tickets'
export const size = { width: 1200, height: 630 }
export const contentType = 'image/png'

export default async function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0A0A0F',
          fontFamily: 'sans-serif',
        }}
      >
        {/* Subtle gradient glow */}
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: 'flex',
            background:
              'radial-gradient(ellipse 60% 50% at 50% 40%, rgba(0,212,170,0.08) 0%, transparent 70%)',
          }}
        />

        {/* Logo mark */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 80,
            height: 80,
            borderRadius: 16,
            background: 'rgba(0,212,170,0.12)',
            border: '2px solid rgba(0,212,170,0.25)',
            marginBottom: 32,
          }}
        >
          <svg width="40" height="40" viewBox="0 0 14 14" fill="none">
            <path
              d="M2 7C2 4.24 4.24 2 7 2C8.38 2 9.63 2.56 10.54 3.46"
              stroke="#00D4AA"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <path
              d="M12 7C12 9.76 9.76 12 7 12C5.62 12 4.37 11.44 3.46 10.54"
              stroke="#00D4AA"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
            <circle cx="7" cy="7" r="1.5" fill="#00D4AA" />
          </svg>
        </div>

        {/* Title */}
        <div
          style={{
            display: 'flex',
            fontSize: 56,
            fontWeight: 700,
            color: '#FFFFFF',
            letterSpacing: '-0.02em',
            marginBottom: 16,
          }}
        >
          ContextOS
        </div>

        {/* Tagline */}
        <div
          style={{
            display: 'flex',
            fontSize: 24,
            color: 'rgba(255,255,255,0.5)',
            maxWidth: 600,
            textAlign: 'center',
            lineHeight: 1.4,
          }}
        >
          AI-generated context for every engineering ticket
        </div>

        {/* Integration pills */}
        <div
          style={{
            display: 'flex',
            gap: 12,
            marginTop: 40,
          }}
        >
          {['Linear', 'Slack', 'GitHub', 'Notion'].map((name) => (
            <div
              key={name}
              style={{
                display: 'flex',
                padding: '8px 20px',
                borderRadius: 20,
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: 'rgba(255,255,255,0.5)',
                fontSize: 16,
              }}
            >
              {name}
            </div>
          ))}
        </div>

        {/* URL */}
        <div
          style={{
            position: 'absolute',
            bottom: 32,
            display: 'flex',
            fontSize: 16,
            color: 'rgba(0,212,170,0.6)',
          }}
        >
          contextos.pro
        </div>
      </div>
    ),
    { ...size }
  )
}
