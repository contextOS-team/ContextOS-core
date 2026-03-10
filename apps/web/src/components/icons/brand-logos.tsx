import type { SVGProps } from 'react'

type LogoProps = SVGProps<SVGSVGElement>

/**
 * Linear logo mark -- the fan/circular segmented shape.
 * Official path from linear.app/brand.
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
      viewBox="0 0 100 100"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <path
        d="M1.22541 61.5228c-.2225-.9485.90748-1.5459 1.59638-.857L39.3342 97.1782c.6889.6889.0915 1.8189-.857 1.5964C20.0515 94.4522 5.54779 79.9485 1.22541 61.5228ZM.00189135 46.8891c-.01764375.2833.08887215.5599.28957165.7606L52.3503 99.7085c.2007.2007.4773.3075.7606.2896 2.3692-.1476 4.6938-.46 6.9624-.9259.7645-.157 1.0301-1.0963.4782-1.6481L2.57595 39.4485c-.55186-.5519-1.49117-.2863-1.648174.4782-.465915 2.2686-.77832 4.5932-.92588465 6.9624ZM4.21093 29.7054c-.16649.3738-.08169.8106.20765 1.1l64.77602 64.776c.2894.2894.7262.3742 1.1.2077 1.7861-.7956 3.5171-1.6927 5.1855-2.684.5521-.328.6373-1.0867.1832-1.5407L8.43566 24.3367c-.45409-.4541-1.21271-.3689-1.54074.1832-.99132 1.6684-1.88843 3.3994-2.68399 5.1855ZM12.6587 18.074c-.3701-.3701-.393-.9637-.0443-1.3541C21.7795 6.45931 35.1114 0 49.9519 0 77.5927 0 100 22.4073 100 50.0481c0 14.8405-6.4593 28.1724-16.7199 37.3375-.3903.3487-.984.3258-1.3542-.0443L12.6587 18.074Z"
        fill="currentColor"
      />
    </svg>
  )
}

/**
 * Slack logo mark -- the official 4-color hash mark.
 * Path data from gilbarbara/logos collection.
 * When color prop is provided, renders monochrome. Otherwise uses brand colors.
 */
export function SlackLogo({
  width = 20,
  height = 20,
  color,
  ...props
}: LogoProps & { color?: string }) {
  const c1 = color || "#E01E5A";
  const c2 = color || "#36C5F0";
  const c3 = color || "#2EB67D";
  const c4 = color || "#ECB22E";
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 256 256"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <path
        d="M53.841 161.321c0 14.832-11.987 26.819-26.819 26.819S.203 176.153.203 161.321c0-14.832 11.987-26.819 26.82-26.819h26.818v26.819zm13.41 0c0-14.832 11.987-26.819 26.819-26.819s26.819 11.987 26.819 26.82v67.047c0 14.831-11.987 26.818-26.82 26.818-14.83 0-26.818-11.987-26.818-26.818v-67.048z"
        fill={c1}
      />
      <path
        d="M94.07 53.638c-14.832 0-26.82-11.987-26.82-26.819C67.25 11.987 79.239 0 94.07 0s26.819 11.987 26.819 26.819v26.82H94.07zm0 13.613c14.832 0 26.819 11.987 26.819 26.819s-11.987 26.819-26.82 26.819H26.82C11.987 120.889 0 108.902 0 94.07c0-14.832 11.987-26.82 26.819-26.82h67.25z"
        fill={c2}
      />
      <path
        d="M201.549 94.07c0-14.832 11.988-26.82 26.82-26.82 14.83 0 26.818 11.988 26.818 26.82s-11.987 26.819-26.819 26.819h-26.819V94.07zm-13.41 0c0 14.831-11.987 26.819-26.819 26.819s-26.819-11.988-26.819-26.82V26.82C134.501 11.987 146.489 0 161.32 0c14.832 0 26.82 11.987 26.82 26.819v67.25z"
        fill={c3}
      />
      <path
        d="M161.321 201.549c14.831 0 26.819 11.988 26.819 26.82 0 14.83-11.988 26.818-26.82 26.818-14.83 0-26.818-11.987-26.818-26.819v-26.819h26.819zm0-13.41c-14.832 0-26.82-11.987-26.82-26.819s11.988-26.819 26.82-26.819h67.25c14.832 0 26.82 11.988 26.82 26.82 0 14.83-11.988 26.818-26.82 26.818h-67.25z"
        fill={c4}
      />
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
 * Fathom AI meeting assistant logo mark.
 * Stylized "F" made of two diagonal bars and a vertical bar.
 * Default fill: currentColor (parent-controlled).
 */
export function FathomLogo({
  width = 20,
  height = 20,
  ...props
}: LogoProps) {
  const fill = props.fill || "currentColor";
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 150 150"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <path
        d="M113.08,85.46L26.9,38.39c-7.96-4.64-10.61-13.92-5.96-21.88,4.64-7.29,14.58-9.94,22.54-5.96l86.18,47.07c7.96,4.64,10.61,13.92,5.97,21.88-3.98,7.96-14.58,10.61-22.54,5.97h0Z"
        fill={fill}
      />
      <path
        d="M73.31,113.96l-45.74-25.19c-7.96-4.64-10.61-13.92-5.97-21.88,4.64-7.29,14.58-9.94,22.54-5.96l45.74,25.19c7.95,4.64,10.6,13.92,5.96,21.88-4.64,7.29-14.58,9.94-22.54,5.96h0Z"
        fill={fill}
      />
      <path
        d="M19.34,124.73v-49.06c0-9.28,7.29-16.57,16.57-16.57s16.57,7.29,16.57,16.57v49.06c0,9.28-7.29,16.57-16.57,16.57s-16.57-7.29-16.57-16.57h0Z"
        fill={fill}
        opacity="0.5"
      />
    </svg>
  )
}

/**
 * Confluence logo mark.
 * Default fill: currentColor (parent-controlled).
 */
export function ConfluenceLogo({
  width = 20,
  height = 20,
  ...props
}: LogoProps) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 256 246"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <path
        d="M8.11 190.2c-2.88 4.79-6.16 10.58-8.11 14.17a7.24 7.24 0 0 0 2.88 9.58l51.5 31.06a7.24 7.24 0 0 0 9.97-2.49c1.56-2.88 3.98-7.28 6.77-12.46 19.72-36.52 39.64-32.14 76.36-14.97l50.91 23.93a7.24 7.24 0 0 0 9.58-3.57l22.75-50.12a7.24 7.24 0 0 0-3.57-9.38c-13.38-6.16-40.34-18.63-60.46-27.81-67.07-30.77-115.76-27.49-158.58 41.96V190.2z"
        fill="currentColor"
        opacity="0.7"
      />
      <path
        d="M247.89 56.59c2.88-4.79 6.16-10.58 8.11-14.17a7.24 7.24 0 0 0-2.88-9.58L201.62 1.78a7.24 7.24 0 0 0-9.97 2.49c-1.56 2.88-3.98 7.28-6.77 12.46-19.72 36.52-39.64 32.14-76.36 14.97L57.61 7.77a7.24 7.24 0 0 0-9.58 3.57L25.28 61.46a7.24 7.24 0 0 0 3.57 9.38c13.38 6.16 40.34 18.63 60.46 27.81 67.07 30.77 115.76 27.49 158.58-42.06z"
        fill="currentColor"
      />
    </svg>
  )
}

/**
 * Google Docs logo mark.
 * Default fill: currentColor (parent-controlled).
 */
export function GoogleDocsLogo({
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
        d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z"
        fill="currentColor"
        opacity="0.15"
        stroke="currentColor"
        strokeWidth="1.5"
      />
      <polyline points="14 2 14 8 20 8" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <line x1="8" y1="13" x2="16" y2="13" stroke="currentColor" strokeWidth="1.5" />
      <line x1="8" y1="17" x2="13" y2="17" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  )
}

/**
 * Figma logo mark.
 * Default fill: currentColor (parent-controlled).
 */
export function FigmaLogo({
  width = 20,
  height = 20,
  ...props
}: LogoProps) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 38 57"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <path
        d="M19 28.5a9.5 9.5 0 1 1 19 0 9.5 9.5 0 0 1-19 0z"
        fill="currentColor"
      />
      <path
        d="M0 47.5A9.5 9.5 0 0 1 9.5 38H19v9.5a9.5 9.5 0 1 1-19 0z"
        fill="currentColor"
        opacity="0.6"
      />
      <path
        d="M19 0v19h9.5a9.5 9.5 0 1 0 0-19H19z"
        fill="currentColor"
        opacity="0.8"
      />
      <path
        d="M0 9.5A9.5 9.5 0 0 0 9.5 19H19V0H9.5A9.5 9.5 0 0 0 0 9.5z"
        fill="currentColor"
        opacity="0.5"
      />
      <path
        d="M0 28.5A9.5 9.5 0 0 0 9.5 38H19V19H9.5A9.5 9.5 0 0 0 0 28.5z"
        fill="currentColor"
        opacity="0.7"
      />
    </svg>
  )
}

/**
 * Loom logo mark.
 * Default fill: currentColor (parent-controlled).
 */
export function LoomLogo({
  width = 20,
  height = 20,
  ...props
}: LogoProps) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M31.25 14.75H22.1a7.98 7.98 0 0 0-2.26-3.84l4.58-7.93a.75.75 0 0 0-.27-1.02l-2.17-1.25a.75.75 0 0 0-1.02.27l-4.58 7.93A7.96 7.96 0 0 0 14.75.75v2.5a.75.75 0 0 0 .75.75h1a5.5 5.5 0 1 1 0 11h-1a.75.75 0 0 0-.75.75v1a.75.75 0 0 0 .75.75 5.5 5.5 0 1 1-5.5 5.5.75.75 0 0 0-.75-.75h-1a.75.75 0 0 0-.75.75v2.5h2.5a.75.75 0 0 0 .75-.75 8 8 0 0 0 3.62 1.63l-4.58 7.93a.75.75 0 0 0 .27 1.02l2.17 1.25a.75.75 0 0 0 1.02-.27L17.25 22.1a7.98 7.98 0 0 0 3.84-2.26l7.93 4.58a.75.75 0 0 0 1.02-.27l1.25-2.17a.75.75 0 0 0-.27-1.02L23.09 16.38a7.97 7.97 0 0 0 0-1.26l7.93-4.58a.75.75 0 0 0 .27-1.02l-1.25-2.17a.75.75 0 0 0-1.02-.27l-7.93 4.58A7.97 7.97 0 0 0 17.25.75h-2.5v2.5"
        fill="currentColor"
      />
      <circle cx="16" cy="16" r="3" fill="currentColor" />
    </svg>
  )
}

/**
 * Jira logo mark -- the angular/diamond shape.
 * Official Jira blue gradient from #0052CC to #2684FF.
 * Default size ~20x20 matching other logos.
 */
export function JiraLogo({
  width = 20,
  height = 20,
  ...props
}: LogoProps) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 256 256"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <defs>
        <linearGradient id="jira-grad-1" x1="98.031%" y1="0.161%" x2="58.888%" y2="40.766%">
          <stop offset="18%" stopColor="#0052CC" stopOpacity="0" />
          <stop offset="100%" stopColor="#2684FF" />
        </linearGradient>
        <linearGradient id="jira-grad-2" x1="100.665%" y1="0.455%" x2="55.402%" y2="44.727%">
          <stop offset="18%" stopColor="#0052CC" stopOpacity="0" />
          <stop offset="100%" stopColor="#2684FF" />
        </linearGradient>
      </defs>
      <path
        d="M244.658 0H121.707a55.502 55.502 0 0 0 55.502 55.502h22.649V77.37c.02 30.625 24.841 55.447 55.5 55.502V10.993C255.358 4.923 250.228 0 244.658 0Z"
        fill="#2684FF"
      />
      <path
        d="M183.822 61.262H60.872c.019 30.625 24.84 55.447 55.501 55.502h22.649v21.868c.02 30.597 24.798 55.408 55.396 55.501V72.255c0-6.075-5.13-10.993-10.596-10.993Z"
        fill="url(#jira-grad-1)"
      />
      <path
        d="M122.943 122.524H0c0 30.653 24.86 55.502 55.502 55.502h22.72v21.868c.02 30.597 24.798 55.408 55.396 55.502V133.518c0-6.076-5.13-10.994-10.675-10.994Z"
        fill="url(#jira-grad-2)"
      />
    </svg>
  )
}

/**
 * Notion logo mark -- the "N" letterform.
 * Official SVG from notion.so brand assets.
 * Default fill: currentColor (parent-controlled).
 */
export function NotionLogo({
  width = 20,
  height = 20,
  ...props
}: LogoProps) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 122.88 128.1"
      fill="none"
      aria-hidden="true"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M21.19,22.46c4,3.23,5.48,3,13,2.49l70.53-4.24c1.5,0,.25-1.49-.25-1.74L92.72,10.5a14.08,14.08,0,0,0-11-3.23l-68.29,5c-2.49.24-3,1.49-2,2.49l9.73,7.72ZM25.42,38.9v74.21c0,4,2,5.48,6.48,5.23l77.52-4.48c4.49-.25,5-3,5-6.23V33.91c0-3.23-1.25-5-4-4.73l-81,4.73c-3,.25-4,1.75-4,5Zm76.53,4c.49,2.24,0,4.48-2.25,4.73L96,48.36v54.79c-3.24,1.74-6.23,2.73-8.72,2.73-4,0-5-1.24-8-5L54.83,62.55V99.66l7.73,1.74s0,4.48-6.23,4.48l-17.2,1c-.5-1,0-3.48,1.75-4l4.48-1.25V52.59l-6.23-.5a4.66,4.66,0,0,1,4.24-5.73l18.44-1.24L87.24,84V49.6l-6.48-.74a4.21,4.21,0,0,1,4-5l17.21-1ZM7.72,5.52l71-5.23C87.49-.46,89.73.05,95.21,4L117.89,20c3.74,2.74,5,3.48,5,6.47v87.42c0,5.47-2,8.71-9,9.21l-82.5,5c-5.24.25-7.73-.5-10.47-4L4.24,102.4c-3-4-4.24-7-4.24-10.46V14.24C0,9.76,2,6,7.72,5.52Z"
        fill="currentColor"
      />
    </svg>
  )
}
