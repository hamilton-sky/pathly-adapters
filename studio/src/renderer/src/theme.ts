export interface Theme {
  bgBase: string
  bgMantle: string
  bgSurface0: string
  bgSurface1: string
  textPrimary: string
  textSecondary: string
  textMuted: string
  accent: string
  blue: string
  green: string
  red: string
  yellow: string
  fontFamilyBase: string
  fontSizeBase: string
  fontSizeSm: string
  fontSizeLg: string
  focusRing: string
  border: string
  borderSubtle: string
  transitionBase: string
}

export const darkTheme: Theme = {
  bgBase: '#13131f',
  bgMantle: '#0f0f1a',
  bgSurface0: '#252538',
  bgSurface1: '#343452',
  textPrimary: '#e2e4f0',
  textSecondary: '#9b9ec8',
  textMuted: '#5a5d8a',
  accent: '#A78BFA',   // Pathly violet
  blue: '#60AAFF',     // Codex blue
  green: '#4ade80',
  red: '#f87171',
  yellow: '#fbbf24',
  fontFamilyBase: "'Inter', system-ui, sans-serif",
  fontSizeBase: '14px',
  fontSizeSm: '12px',
  fontSizeLg: '16px',
  focusRing: '2px solid var(--accent)',
  border: '1px solid #343452',
  borderSubtle: '1px solid #252538',
  transitionBase: '150ms ease-out',
}

export const lightTheme: Theme = {
  bgBase: '#f5f5ff',
  bgMantle: '#eeeef8',
  bgSurface0: '#ddddf0',
  bgSurface1: '#c8c8e0',
  textPrimary: '#1e1e3a',
  textSecondary: '#4a4a7a',
  textMuted: '#8888aa',
  accent: '#7C3AED',   // Pathly violet
  blue: '#0070E0',     // Codex blue
  green: '#16a34a',
  red: '#dc2626',
  yellow: '#d97706',
  fontFamilyBase: "'Inter', system-ui, sans-serif",
  fontSizeBase: '14px',
  fontSizeSm: '12px',
  fontSizeLg: '16px',
  focusRing: '2px solid var(--accent)',
  border: '1px solid #c8c8e0',
  borderSubtle: '1px solid #ddddf0',
  transitionBase: '150ms ease-out',
}
