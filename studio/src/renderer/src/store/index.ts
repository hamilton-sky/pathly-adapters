import { useUiStore } from './uiStore'
import { useProjectStore } from './projectStore'
import type { UiState } from './uiStore'
import type { ProjectState } from './projectStore'




type StoreState = UiState & ProjectState

export function useStore(): StoreState
export function useStore<T>(selector: (s: StoreState) => T): T
export function useStore<T>(selector?: (s: StoreState) => T): T | StoreState {
  const ui = useUiStore()
  const project = useProjectStore()
  const merged = { ...ui, ...project } as StoreState
  return selector ? selector(merged) : merged
}
