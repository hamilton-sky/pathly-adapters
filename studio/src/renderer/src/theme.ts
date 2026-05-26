export type ThemeName = 'dark' | 'light' | 'nord' | 'mocha' | 'solarized' | 'dracula' | 'rose-pine' | 'solarized-light' | 'latte' | 'paper' | 'rose-pine-dawn' | 'mint'

export const LIGHT_PALETTES = new Set<ThemeName>(['light', 'solarized-light', 'latte', 'paper', 'rose-pine-dawn', 'mint'])
export function isLightPalette(name: ThemeName): boolean { return LIGHT_PALETTES.has(name) }

export interface Theme {
  bgBase: string
  bgMantle: string
  bgSurface0: string
  bgSurface1: string
  bgTerminal: string   // log/terminal panel background
  textPrimary: string
  textSecondary: string
  textMuted: string
  accent: string
  blue: string
  green: string
  red: string
  yellow: string
  purple?: string
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

const fontBase = "'Geist', 'Inter', system-ui, sans-serif"
const fontMono = "'Geist Mono', 'JetBrains Mono', 'Fira Code', monospace"
const fontSizes = { base: '14px', sm: '12px', lg: '16px' }
const transition = '150ms ease-out'

export const darkTheme: Theme = {
  bgBase: '#111827',
  bgMantle: '#0B0F1A',
  bgSurface0: '#1E2433',
  bgSurface1: '#283044',
  bgTerminal: '#0d1117',
  textPrimary: '#E2E8F0',
  textSecondary: '#94A3B8',
  textMuted: '#64748B',
  accent: '#38BDF8',
  blue: '#60A5FA',
  green: '#34D399',
  red: '#f87171',
  yellow: '#FCD34D',
  runtime: '#2DD4BF',
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #38BDF8',
  border: '1px solid #283044',
  borderSubtle: '1px solid #1E2433',
  transitionBase: transition,
}

export const lightTheme: Theme = {
  bgBase: '#F8FAFC',
  bgMantle: '#F0F9FF',
  bgSurface0: '#E2E8F0',
  bgSurface1: '#CBD5E1',
  bgTerminal: '#edf2f7',
  textPrimary: '#0F172A',
  textSecondary: '#334155',
  textMuted: '#64748B',
  accent: '#0369A1',
  blue: '#1D4ED8',
  green: '#047857',
  red: '#dc2626',
  yellow: '#B45309',
  runtime: '#0F766E',
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #0369A1',
  border: '1px solid #CBD5E1',
  borderSubtle: '1px solid #E2E8F0',
  transitionBase: transition,
}

export const nordTheme: Theme = {
  bgBase: '#2e3440',
  bgMantle: '#242933',
  bgSurface0: '#3b4252',
  bgSurface1: '#434c5e',
  bgTerminal: '#1c2028',
  textPrimary: '#eceff4',
  textSecondary: '#d8dee9',
  textMuted: '#4c566a',
  accent: '#88c0d0',
  blue: '#81a1c1',
  green: '#a3be8c',
  red: '#bf616a',
  yellow: '#ebcb8b',
  runtime: '#8fbcbb',
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #88c0d0',
  border: '1px solid #434c5e',
  borderSubtle: '1px solid #3b4252',
  transitionBase: transition,
}

export const mochaTheme: Theme = {
  bgBase: '#1e1e2e',
  bgMantle: '#181825',
  bgSurface0: '#313244',
  bgSurface1: '#45475a',
  bgTerminal: '#11111b',
  textPrimary: '#cdd6f4',
  textSecondary: '#bac2de',
  textMuted: '#6c7086',
  accent: '#cba6f7',
  blue: '#89b4fa',
  green: '#a6e3a1',
  red: '#f38ba8',
  yellow: '#f9e2af',
  runtime: '#94e2d5',
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #cba6f7',
  border: '1px solid #45475a',
  borderSubtle: '1px solid #313244',
  transitionBase: transition,
}

export const solarizedTheme: Theme = {
  bgBase: '#002b36',
  bgMantle: '#00212b',
  bgSurface0: '#073642',
  bgSurface1: '#586e75',
  bgTerminal: '#001e26',
  textPrimary: '#fdf6e3',
  textSecondary: '#eee8d5',
  textMuted: '#657b83',
  accent: '#268bd2',
  blue: '#2aa198',   // cyan — distinct from accent
  green: '#859900',
  red: '#dc322f',
  yellow: '#b58900',
  runtime: '#6c71c4', // violet — distinct from cyan and blue
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #268bd2',
  border: '1px solid #586e75',
  borderSubtle: '1px solid #073642',
  transitionBase: transition,
}

export const draculaTheme: Theme = {
  bgBase: '#282a36',
  bgMantle: '#191a21',
  bgSurface0: '#44475a',
  bgSurface1: '#6272a4',
  bgTerminal: '#1a1b23',
  textPrimary: '#f8f8f2',
  textSecondary: '#b0b2c8', // lighter than textMuted #6272a4 — distinct hierarchy
  textMuted: '#6272a4',
  accent: '#bd93f9',
  blue: '#8be9fd',
  green: '#50fa7b',
  red: '#ff5555',
  yellow: '#f1fa8c',
  runtime: '#ffb86c',
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #bd93f9',
  border: '1px solid #44475a',
  borderSubtle: '1px solid #383a4a', // darker than border — visually subtle
  transitionBase: transition,
}

export const rosePineTheme: Theme = {
  bgBase: '#191724',
  bgMantle: '#12111a',
  bgSurface0: '#26233a',
  bgSurface1: '#403d52',
  bgTerminal: '#0d0c14',
  textPrimary: '#e0def4',
  textSecondary: '#c4c0d9',
  textMuted: '#6e6a86',
  accent: '#c4a7e7',
  blue: '#9ccfd8',
  green: '#56a37a',  // brighter pine-green — legible on dark bg
  red: '#eb6f92',
  yellow: '#f6c177',
  runtime: '#ebbcba', // rose — warm, distinct from foam blue
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #c4a7e7',
  border: '1px solid #403d52',
  borderSubtle: '1px solid #26233a',
  transitionBase: transition,
}

export const solarizedLightTheme: Theme = {
  bgBase: '#fdf6e3',
  bgMantle: '#eee8d5',
  bgSurface0: '#e0d9c5',
  bgSurface1: '#cbc4b0',
  bgTerminal: '#f5efdc',
  textPrimary: '#002b36',
  textSecondary: '#3a6270', // lighter than textPrimary — distinct hierarchy
  textMuted: '#93a1a1',
  accent: '#268bd2',
  blue: '#2aa198',   // cyan — distinct from accent
  green: '#859900',
  red: '#dc322f',
  yellow: '#b58900',
  runtime: '#6c71c4', // violet — distinct from cyan and blue
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #268bd2',
  border: '1px solid #cbc4b0',
  borderSubtle: '1px solid #e0d9c5',
  transitionBase: transition,
}

export const latteTheme: Theme = {
  bgBase: '#eff1f5',
  bgMantle: '#e6e9ef',
  bgSurface0: '#ccd0da',
  bgSurface1: '#bcc0cc',
  bgTerminal: '#dce0e8',
  textPrimary: '#4c4f69',
  textSecondary: '#5c5f77',
  textMuted: '#8c8fa1',
  accent: '#8839ef',
  blue: '#1e66f5',
  green: '#40a02b',
  red: '#d20f39',
  yellow: '#df8e1d',
  runtime: '#179299',
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #8839ef',
  border: '1px solid #bcc0cc',
  borderSubtle: '1px solid #ccd0da',
  transitionBase: transition,
}

export const paperTheme: Theme = {
  bgBase: '#ffffff',
  bgMantle: '#f9f9f7',
  bgSurface0: '#f0ede8',
  bgSurface1: '#e4e0da',
  bgTerminal: '#f5f2ec',
  textPrimary: '#1a1a1a',
  textSecondary: '#4a4a4a',
  textMuted: '#9a9a9a',
  accent: '#c75c2a',
  blue: '#2563eb',
  green: '#16a34a',
  red: '#dc2626',
  yellow: '#d97706',
  runtime: '#0891b2',
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #c75c2a',
  border: '1px solid #e4e0da',
  borderSubtle: '1px solid #f0ede8',
  transitionBase: transition,
}

export const rosePineDawnTheme: Theme = {
  bgBase: '#faf4ed',
  bgMantle: '#f4ede6',  // darker than bgBase — correct direction
  bgSurface0: '#ebe3d9',
  bgSurface1: '#dfd9ce',
  bgTerminal: '#f0e8d8',
  textPrimary: '#575279',
  textSecondary: '#6b6496',
  textMuted: '#9893a5',
  accent: '#b4637a',
  blue: '#56949f',
  green: '#286983',
  red: '#c0334a',    // deeper red — clearly alarming, distinct from accent
  yellow: '#ea9d34',
  runtime: '#907aa9', // plum — distinct from blue foam and accent rose
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #b4637a',
  border: '1px solid #e4dfda',
  borderSubtle: '1px solid #f2e9de',
  transitionBase: transition,
}

export const mintTheme: Theme = {
  bgBase: '#f0faf5',
  bgMantle: '#e8f5ef',
  bgSurface0: '#d4ede0',
  bgSurface1: '#bde0cc',
  bgTerminal: '#e0f2e9',
  textPrimary: '#1a3028',
  textSecondary: '#2d5040',
  textMuted: '#7aaa8e',
  accent: '#0891b2',  // teal/cyan — distinct from green
  blue: '#1a6fa0',
  green: '#0f7d52',
  red: '#c0392b',
  yellow: '#c07a00',
  runtime: '#6366a8', // muted indigo — distinct from teal accent and blue
  fontFamilyBase: fontBase,
  fontFamilyMono: fontMono,
  fontSizeBase: fontSizes.base,
  fontSizeSm: fontSizes.sm,
  fontSizeLg: fontSizes.lg,
  focusRing: '2px solid #0891b2', // matches new accent
  border: '1px solid #bde0cc',
  borderSubtle: '1px solid #d4ede0',
  transitionBase: transition,
}

export const themes: Record<ThemeName, Theme> = {
  dark: darkTheme,
  light: lightTheme,
  nord: nordTheme,
  mocha: mochaTheme,
  solarized: solarizedTheme,
  dracula: draculaTheme,
  'rose-pine': rosePineTheme,
  'solarized-light': solarizedLightTheme,
  latte: latteTheme,
  paper: paperTheme,
  'rose-pine-dawn': rosePineDawnTheme,
  mint: mintTheme,
}

export const paletteLabels: Record<ThemeName, string> = {
  dark: 'Pathly Dark',
  light: 'Pathly Light',
  nord: 'Nord',
  mocha: 'Mocha',
  solarized: 'Solarized',
  dracula: 'Dracula',
  'rose-pine': 'Rosé Pine',
  'solarized-light': 'Sol. Light',
  latte: 'Latte',
  paper: 'Paper',
  'rose-pine-dawn': 'Dawn',
  mint: 'Mint',
}
