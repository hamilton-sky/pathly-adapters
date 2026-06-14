import React from 'react'

/* Inline lucide-style icons (2px stroke, round caps) so the feature renders
   with no npm dependency. Swap for lucide-react in-app if you prefer. */

interface IconProps {
  size?: number
}

function svgProps(size: number) {
  return {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }
}

/** Stacked cards — the master/detail "Cards" view. */
export function CardsIcon({ size = 16 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <rect x="3" y="4" width="18" height="7" rx="1.5" />
      <rect x="3" y="13" width="18" height="7" rx="1.5" />
    </svg>
  )
}

/** Three rows — the compact "List" (triage) view. */
export function ListIcon({ size = 16 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="18" x2="20" y2="18" />
    </svg>
  )
}

/** Split panes — the file-level "Code diff" (VS Code-style) view. */
export function CodeDiffIcon({ size = 16 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <rect x="3" y="4" width="18" height="16" rx="1.5" />
      <line x1="12" y1="4" x2="12" y2="20" />
    </svg>
  )
}

/** Pencil — the editable result view. */
export function EditIcon({ size = 16 }: IconProps) {
  return (
    <svg {...svgProps(size)}>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
    </svg>
  )
}

/** Disclosure chevron — points right when closed, down when open. */
export function Chevron({ open, size = 14 }: IconProps & { open: boolean }) {
  return (
    <svg {...svgProps(size)}>
      <path d={open ? 'm6 9 6 6 6-6' : 'm9 18 6-6-6-6'} />
    </svg>
  )
}
