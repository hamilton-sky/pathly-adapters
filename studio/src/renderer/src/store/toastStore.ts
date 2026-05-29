import { create } from 'zustand'

export type ToastVariant = 'info' | 'success' | 'error'

export interface Toast {
  id: string
  message: string
  variant: ToastVariant
}

interface ToastState {
  toasts: Toast[]
  push: (message: string, variant?: ToastVariant) => void
  remove: (id: string) => void
}

let counter = 0

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  push: (message, variant = 'info') => {
    const id = String(++counter)
    set((s) => ({ toasts: [...s.toasts, { id, message, variant }] }))
    setTimeout(() => useToastStore.getState().remove(id), 4000)
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}))
