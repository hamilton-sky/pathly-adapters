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
  runtime: string
  fontFamilyBase: string
  fontFamilyMono: string
  fontSizeBase: string
  fontSizeSm: string
  fontSizeLg: string
  focusRing: string
  border: string
  borderSubtle: string
  transitionBase: string
}

export const darkTheme: Theme = {
  bgBase: '#111827',
  bgMantle: '#0B0F1A',
  bgSurface0: '#1E2433',
  bgSurface1: '#283044',
  textPrimary: '#E2E8F0',
  textSecondary: '#94A3B8',
  textMuted: '#64748B',
  accent: '#38BDF8',   // Pathly sky blue
  blue: '#60A5FA',     // informational blue (EventLog labels)
  green: '#34D399',    // emerald
  red: '#f87171',
  yellow: '#FCD34D',
  runtime: '#2DD4BF',  // teal — live FSM state
  fontFamilyBase: "'Geist', 'Inter', system-ui, sans-serif",
  fontFamilyMono: "'Geist Mono', 'JetBrains Mono', 'Fira Code', monospace",
  fontSizeBase: '14px',
  fontSizeSm: '12px',
  fontSizeLg: '16px',
  focusRing: '2px solid #38BDF8',
  border: '1px solid #283044',
  borderSubtle: '1px solid #1E2433',
  transitionBase: '150ms ease-out',
}

export const lightTheme: Theme = {
  bgBase: '#F8FAFC',
  bgMantle: '#F0F9FF',
  bgSurface0: '#E2E8F0',
  bgSurface1: '#CBD5E1',
  textPrimary: '#0F172A',
  textSecondary: '#334155',
  textMuted: '#64748B',
  accent: '#0369A1',   // sky-700
  blue: '#1D4ED8',     // blue-700 (EventLog labels)
  green: '#047857',    // emerald-700
  red: '#dc2626',
  yellow: '#B45309',   // amber-700 (yellow needs dark shade on white)
  runtime: '#0F766E',  // teal-700 — live FSM state
  fontFamilyBase: "'Geist', 'Inter', system-ui, sans-serif",
  fontFamilyMono: "'Geist Mono', 'JetBrains Mono', 'Fira Code', monospace",
  fontSizeBase: '14px',
  fontSizeSm: '12px',
  fontSizeLg: '16px',
  focusRing: '2px solid #0369A1',
  border: '1px solid #CBD5E1',
  borderSubtle: '1px solid #E2E8F0',
  transitionBase: '150ms ease-out',
}
