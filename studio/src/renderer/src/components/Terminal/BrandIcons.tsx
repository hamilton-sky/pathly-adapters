/* Compact runtime marks used in terminal tabs, cards, and launchers. */

export function FileExplorerIcon({ size = 14 }: { size?: number }): JSX.Element {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ flexShrink: 0 }}>
      {/* back panel */}
      <path d="M2 8.5C2 7.67 2.67 7 3.5 7H9.4L11.1 9H20.5C21.33 9 22 9.67 22 10.5V18.5C22 19.33 21.33 20 20.5 20H3.5C2.67 20 2 19.33 2 18.5V8.5Z" fill="#E6A817"/>
      {/* front face */}
      <path d="M2 12H22V18.5C22 19.33 21.33 20 20.5 20H3.5C2.67 20 2 19.33 2 18.5V12Z" fill="#FFCA28"/>
    </svg>
  )
}

export function WindowsTerminalIcon({ size = 14 }: { size?: number }): JSX.Element {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ flexShrink: 0 }}>
      <rect x="1.5" y="3" width="21" height="18" rx="3.5" fill="#0C0C0C"/>
      {/* chevron prompt */}
      <path d="M6 8.5L10.5 12L6 15.5" stroke="#13A10E" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
      {/* underscore cursor */}
      <path d="M13 15.5H18" stroke="#13A10E" strokeWidth="1.7" strokeLinecap="round"/>
    </svg>
  )
}

export function GitBashIcon({ size = 14 }: { size?: number }): JSX.Element {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ flexShrink: 0 }}>
      {/* Rounded square background */}
      <rect x="1.5" y="1.5" width="21" height="21" rx="4.5" fill="#1D1F21"/>
      {/* Orange diamond — the Git logo mark */}
      <path d="M12 3.5L20.5 12L12 20.5L3.5 12Z" fill="#F05133"/>
      {/* White branch: top node → stem → two child nodes */}
      <circle cx="12" cy="8" r="1.6" fill="white"/>
      <line x1="12" y1="9.6" x2="12" y2="12" stroke="white" strokeWidth="1.4" strokeLinecap="round"/>
      <line x1="12" y1="12" x2="9.2" y2="14.5" stroke="white" strokeWidth="1.4" strokeLinecap="round"/>
      <line x1="12" y1="12" x2="14.8" y2="14.5" stroke="white" strokeWidth="1.4" strokeLinecap="round"/>
      <circle cx="9.2" cy="16" r="1.6" fill="white"/>
      <circle cx="14.8" cy="16" r="1.6" fill="white"/>
    </svg>
  )
}

export function WslIcon({ size = 14 }: { size?: number }): JSX.Element {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ flexShrink: 0 }}>
      {/* Body */}
      <ellipse cx="12" cy="15" rx="6.5" ry="7" fill="#1A1A2E"/>
      {/* White belly */}
      <ellipse cx="12" cy="15.5" rx="3.8" ry="5" fill="#F5F5F5"/>
      {/* Head */}
      <circle cx="12" cy="7.2" r="4.2" fill="#1A1A2E"/>
      {/* White face */}
      <ellipse cx="12" cy="7.2" rx="2.4" ry="2.6" fill="#F5F5F5"/>
      {/* Eyes */}
      <circle cx="10.8" cy="6.4" r="0.7" fill="#1A1A2E"/>
      <circle cx="13.2" cy="6.4" r="0.7" fill="#1A1A2E"/>
      {/* Beak */}
      <path d="M11.2 8 L12.8 8 L12 9.1Z" fill="#F57C00"/>
      {/* Feet */}
      <path d="M9.5 21 Q8 21 8.5 19.5 L10 19.5 Q10.5 21 9.5 21Z" fill="#F57C00"/>
      <path d="M14.5 21 Q16 21 15.5 19.5 L14 19.5 Q13.5 21 14.5 21Z" fill="#F57C00"/>
    </svg>
  )
}

export function PyCharmIcon({ size = 14 }: { size?: number }): JSX.Element {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" aria-hidden="true" style={{ flexShrink: 0 }}>
      <defs>
        <linearGradient id="pcGrad__pc" x1="4" y1="3" x2="20" y2="16" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#FCF84A"/>
          <stop offset="50%" stopColor="#21D789"/>
          <stop offset="100%" stopColor="#07C3F2"/>
        </linearGradient>
      </defs>
      <rect x="1.5" y="1.5" width="21" height="21" rx="4.5" fill="#1A1A1A"/>
      {/* P — vertical stroke + rounded bump */}
      <rect x="5" y="5" width="2" height="10" rx="1" fill="url(#pcGrad__pc)"/>
      <path d="M7 5 Q11.5 5 11.5 8 Q11.5 11 7 11Z" fill="url(#pcGrad__pc)"/>
      {/* C — open arc */}
      <path d="M19 7.5 Q16 4.5 13 7.5 Q11 9.5 11 12 Q11 14.5 13 16.5 Q16 19.5 19 16.5"
        stroke="url(#pcGrad__pc)" strokeWidth="2.2" strokeLinecap="round" fill="none"/>
      {/* JetBrains bottom bar */}
      <rect x="5" y="17.5" width="6" height="2" rx="1" fill="white"/>
    </svg>
  )
}

export function ShellIcon({ size = 14 }: { size?: number }): JSX.Element {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      <rect x="2.5" y="4" width="19" height="16" rx="4" fill="#1F6FEB" />
      <path d="m7 9 3 3-3 3" stroke="#F8FAFC" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12.5 15h4.5" stroke="#F8FAFC" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

export function ClaudeIcon({ size = 14 }: { size?: number }): JSX.Element {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      <rect x="2.5" y="2.5" width="19" height="19" rx="5" fill="#D97757" />
      <path
        d="M13.85 6h-3.7L5.4 18h2.75l.9-2.35h5.9l.9 2.35h2.75L13.85 6Zm-3.95 7.35L12 8.1l2.1 5.25H9.9Z"
        fill="#FFF7ED"
      />
    </svg>
  )
}

export function CodexIcon({ size = 14 }: { size?: number }): JSX.Element {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      style={{ flexShrink: 0 }}
    >
      <rect x="2.5" y="2.5" width="19" height="19" rx="5" fill="#111827" />
      <g fill="none" stroke="#E5E7EB" strokeWidth="1.8" strokeLinecap="round">
        <path d="M12 5.2c2.5 0 3.8 1.6 3.8 3.4 0 .9-.3 1.7-.9 2.4" />
        <path d="M18.1 8.8c1.2 2.1.4 4-1.2 4.9-.8.5-1.7.6-2.6.4" />
        <path d="M17.1 15.9c-1.2 2.1-3.3 2.4-4.9 1.5-.8-.4-1.4-1.1-1.7-2" />
        <path d="M12 18.8c-2.5 0-3.8-1.6-3.8-3.4 0-.9.3-1.7.9-2.4" />
        <path d="M5.9 15.2c-1.2-2.1-.4-4 1.2-4.9.8-.5 1.7-.6 2.6-.4" />
        <path d="M6.9 8.1c1.2-2.1 3.3-2.4 4.9-1.5.8.4 1.4 1.1 1.7 2" />
      </g>
      <circle cx="12" cy="12" r="1.6" fill="#10B981" />
    </svg>
  )
}
