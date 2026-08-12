import { create } from 'zustand'
import type { NotifCategory } from './notificationStore'
import { useNotificationStore } from './notificationStore'

type ToastVariant = 'info' | 'success' | 'error'

interface Toast {
  id: string
  message: string
  variant: ToastVariant
  category?: NotifCategory
  accentColor?: string
}

export interface PushOpts {
  category?: NotifCategory
  duration?: number
}

interface ToastState {
  toasts: Toast[]
  push: (message: string, variant?: ToastVariant, opts?: PushOpts) => void
  remove: (id: string) => void
}

let counter = 0

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (message, variant = 'info', opts) => {
    const cat = opts?.category
    if (cat) {
      const prefs = useNotificationStore.getState().categories[cat]
      if (prefs && !prefs.enabled) return
    }
    const accentColor = cat ? useNotificationStore.getState().categories[cat]?.color : undefined
    const id = String(++counter)
    const duration = opts?.duration ?? 4000
    set((s) => ({ toasts: [...s.toasts, { id, message, variant, category: cat, accentColor }] }))
    setTimeout(() => useToastStore.getState().remove(id), duration)
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))
