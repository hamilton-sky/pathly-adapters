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
}

export const darkTheme: Theme = {
  bgBase: '#1e1e2e',
  bgMantle: '#181825',
  bgSurface0: '#313244',
  bgSurface1: '#45475a',
  textPrimary: '#cdd6f4',
  textSecondary: '#a6adc8',
  textMuted: '#6c7086',
  accent: '#cba6f7',
  blue: '#89b4fa',
  green: '#a6e3a1',
  red: '#f38ba8',
  yellow: '#f9e2af',
}

export const lightTheme: Theme = {
  bgBase: '#eff1f5',
  bgMantle: '#e6e9ef',
  bgSurface0: '#ccd0da',
  bgSurface1: '#bcc0cc',
  textPrimary: '#4c4f69',
  textSecondary: '#6c6f85',
  textMuted: '#9ca0b0',
  accent: '#8839ef',
  blue: '#1e66f5',
  green: '#40a02b',
  red: '#d20f39',
  yellow: '#df8e1d',
}
