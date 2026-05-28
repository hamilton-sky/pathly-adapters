/* Compact runtime marks used in terminal tabs, cards, and launchers. */

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
