/* Simplified brand mark SVGs for Claude (Anthropic) and Codex (OpenAI) */

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
      {/* Anthropic "A" mark — two thick diagonal strokes meeting at apex */}
      <path
        d="M13.85 3.5h-3.7L3 20.5h3.9l1.55-4.2h7.1l1.55 4.2H21L13.85 3.5zm-3.6 9.8 1.75-4.9 1.75 4.9H10.25z"
        fill="#D97757"
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
      {/* OpenAI-style 6-point asterisk / bloom mark */}
      <g fill="#e2e4f0" opacity="0.9">
        <rect x="11" y="2"  width="2" height="8"  rx="1" />
        <rect x="11" y="14" width="2" height="8"  rx="1" />
        <rect x="2"  y="11" width="8" height="2"  rx="1" transform="rotate(0 2 11)" />
        <rect x="14" y="11" width="8" height="2"  rx="1" />
        <rect x="4.22" y="4.22" width="2" height="8" rx="1" transform="rotate(-45 4.22 4.22)" />
        <rect x="13.56" y="13.56" width="2" height="8" rx="1" transform="rotate(-45 13.56 13.56)" />
        <rect x="17.78" y="4.22" width="2" height="8" rx="1" transform="rotate(45 17.78 4.22)" />
        <rect x="8.44"  y="13.56" width="2" height="8" rx="1" transform="rotate(45 8.44 13.56)" />
      </g>
    </svg>
  )
}
