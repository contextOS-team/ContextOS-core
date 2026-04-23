import { ImageResponse } from 'next/og'

export const runtime = 'edge'
export const size = { width: 180, height: 180 }
export const contentType = 'image/png'

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0A0A0F',
        }}
      >
        <div
          style={{
            width: 132,
            height: 132,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(0,212,170,0.15)',
            border: '2px solid rgba(0,212,170,0.3)',
            borderRadius: 28,
          }}
        >
          <svg width="72" height="72" viewBox="0 0 14 14" fill="none">
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
      </div>
    ),
    { ...size }
  )
}
