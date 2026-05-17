import { useStore } from './store'
import { darkTheme, lightTheme } from './theme'

export function useTheme() {
  const theme = useStore((s) => s.theme)
  return theme === 'dark' ? darkTheme : lightTheme
}
