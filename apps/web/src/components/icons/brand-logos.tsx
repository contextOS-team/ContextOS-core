import type { SVGProps } from 'react'

type LogoProps = SVGProps<SVGSVGElement>

/**
 * Linear logo mark -- the interlocking shapes.
 * Default fill: currentColor (parent-controlled).
 */
export function LinearLogo({
  width = 20,
  height = 20,
  ...props
}: LogoProps) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <path
        d="M2.654 13.697a.37.37 0 0 1-.084-.437 10.948 10.948 0 0 1 2.17-3.423c3.913-3.913 10.257-3.913 14.17 0a10.948 10.948 0 0 1 2.17 3.423.37.37 0 0 1-.084.437l-8.56 8.56a.37.37 0 0 1-.437.084A10.948 10.948 0 0 1 8.576 20.17c-3.913-3.913-3.913-10.258 0-14.17a10.948 10.948 0 0 1 3.423-2.17.37.37 0 0 1 .437.084l8.56 8.56a.37.37 0 0 1 .084.437 10.948 10.948 0 0 1-2.17 3.423"
        fill="currentColor"
      />
    </svg>
  )
}

/**
 * Slack logo mark -- the 4-color hash mark.
 * Uses official Slack brand colors.
 */
export function SlackLogo({
  width = 20,
  height = 20,
  ...props
}: LogoProps) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      {/* Blue (top-right vertical) */}
      <path
        d="M14.5 2a1.5 1.5 0 1 0 0 3H16v1.5a1.5 1.5 0 1 0 3 0v-3A1.5 1.5 0 0 0 17.5 2h-3Z"
        fill="#36C5F0"
      />
      {/* Green (bottom-right horizontal) */}
      <path
        d="M22 14.5a1.5 1.5 0 1 0-3 0V16h-1.5a1.5 1.5 0 1 0 0 3h3a1.5 1.5 0 0 0 1.5-1.5v-3Z"
        fill="#2EB67D"
      />
      {/* Yellow (bottom-left vertical) */}
      <path
        d="M9.5 22a1.5 1.5 0 1 0 0-3H8v-1.5a1.5 1.5 0 1 0-3 0v3A1.5 1.5 0 0 0 6.5 22h3Z"
        fill="#ECB22E"
      />
      {/* Magenta (top-left horizontal) */}
      <path
        d="M2 9.5a1.5 1.5 0 1 0 3 0V8h1.5a1.5 1.5 0 1 0 0-3h-3A1.5 1.5 0 0 0 2 6.5v3Z"
        fill="#E01E5A"
      />
      {/* Center cross */}
      <path d="M8 14.5A1.5 1.5 0 0 1 9.5 13H11v-1.5A1.5 1.5 0 0 1 14.003 11H13v1.5a1.5 1.5 0 0 1-1.5 1.5H10v1.5A1.5 1.5 0 0 1 8 14.5Z" fill="#ECB22E" />
      <path d="M13 8a1.5 1.5 0 0 1 1.5-1.5A1.5 1.5 0 0 1 16 8v1.5a1.5 1.5 0 0 1-1.5 1.5H13V8Z" fill="#36C5F0" />
      <path d="M16 14.5a1.5 1.5 0 0 1 1.5-1.5A1.5 1.5 0 0 1 19 14.5V16h-1.5a1.5 1.5 0 0 1-1.5-1.5Z" fill="#2EB67D" />
      <path d="M8 9.5A1.5 1.5 0 0 1 9.5 8H11v2.5a1.5 1.5 0 0 1-1.5 1.5H8V9.5Z" fill="#E01E5A" />
    </svg>
  )
}

/**
 * GitHub Invertocat logo mark.
 * Default fill: currentColor (parent-controlled).
 */
export function GitHubLogo({
  width = 20,
  height = 20,
  ...props
}: LogoProps) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.166 6.839 9.489.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.463-1.11-1.463-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0 1 12 6.836a9.59 9.59 0 0 1 2.504.337c1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.163 22 16.418 22 12c0-5.523-4.477-10-10-10Z"
        fill="currentColor"
      />
    </svg>
  )
}

/**
 * Fathom "F" lettermark logo.
 * Uses a clean geometric F in Fathom's purple tone.
 */
export function FathomLogo({
  width = 20,
  height = 20,
  ...props
}: LogoProps) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <rect x="3" y="3" width="18" height="18" rx="4" fill="#7C3AED" />
      <path
        d="M8 7h8v2.4h-5.2v2h4.4v2.4h-4.4V17H8V7Z"
        fill="white"
      />
    </svg>
  )
}
