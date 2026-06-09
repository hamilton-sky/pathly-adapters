import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type NotifCategory = 'db_crud' | 'runner_state' | 'phase_changes' | 'events_log' | 'agent_done'
export type ToastPosition = 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left'
export type ToastStyle = 'default' | 'card' | 'minimal' | 'banner'

export interface CategoryPrefs {
  enabled: boolean
  color: string
}

export const DEFAULT_CATEGORIES: Record<NotifCategory, CategoryPrefs> = {
  db_crud:        { enabled: true,  color: '#4ade80' },
  runner_state:   { enabled: true,  color: '#60a5fa' },
  phase_changes:  { enabled: true,  color: '#c084fc' },
  events_log:     { enabled: false, color: '#94a3b8' },
  agent_done:     { enabled: true,  color: '#fb923c' },
}

interface NotificationState {
  position: ToastPosition
  style: ToastStyle
  categories: Record<NotifCategory, CategoryPrefs>
  setPosition: (pos: ToastPosition) => void
  setStyle: (style: ToastStyle) => void
  setCategoryEnabled: (cat: NotifCategory, enabled: boolean) => void
  setCategoryColor: (cat: NotifCategory, color: string) => void
}

export const useNotificationStore = create<NotificationState>()(
  persist(
    (set) => ({
      position: 'bottom-right',
      style: 'default',
      categories: { ...DEFAULT_CATEGORIES },
      setPosition: (position) => set({ position }),
      setStyle: (style) => set({ style }),
      setCategoryEnabled: (cat, enabled) =>
        set((s) => ({ categories: { ...s.categories, [cat]: { ...s.categories[cat], enabled } } })),
      setCategoryColor: (cat, color) =>
        set((s) => ({ categories: { ...s.categories, [cat]: { ...s.categories[cat], color } } })),
    }),
    { name: 'pathly-studio-notifications' }
  )
)
