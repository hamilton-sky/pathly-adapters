import { useStore } from './store'
import { themes } from './theme'

export function useTheme() {
  const theme = useStore((s) => s.theme)
  return themes[theme] ?? themes.dark
}
