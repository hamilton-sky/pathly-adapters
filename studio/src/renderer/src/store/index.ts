import { useUiStore } from './uiStore'
import { useProjectStore } from './projectStore'

export function useStore() {
  return { ...useUiStore(), ...useProjectStore() }
}
