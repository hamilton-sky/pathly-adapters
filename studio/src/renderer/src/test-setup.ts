import { vi } from 'vitest'

// Any store wrapped in zustand's `persist` writes through `localStorage` on EVERY
// setState. When the test environment doesn't expose one, persist's storage handle is
// undefined and the write throws "Cannot read properties of undefined (reading
// 'setItem')" — which failed all 7 commandCenterStore tests on a plain `setState`,
// nothing to do with the behavior under test. Guarded so a real localStorage (jsdom or
// browser) is always preferred; this only fills a genuine gap.
if (!globalThis.localStorage) {
  const store = new Map<string, string>()
  const shim: Storage = {
    get length() { return store.size },
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => { store.set(k, String(v)) },
    removeItem: (k: string) => { store.delete(k) },
    clear: () => { store.clear() },
  }
  Object.defineProperty(globalThis, 'localStorage', { value: shim, writable: true })
}

Object.defineProperty(window, 'pathly', {
  value: {
    fs: {
      read: vi.fn().mockResolvedValue(null),
      write: vi.fn().mockResolvedValue(undefined),
      list: vi.fn().mockResolvedValue([]),
      listDirs: vi.fn().mockResolvedValue([]),
      pickFolder: vi.fn().mockResolvedValue(null),
    },
    shell: {
      publish: vi.fn().mockResolvedValue(null),
      onOutput: vi.fn().mockReturnValue(() => {}),
      openWindow: vi.fn().mockResolvedValue(undefined),
    },
    fsm: {
      ping: vi.fn().mockResolvedValue(false),
    },
    watch: {
      start: vi.fn().mockResolvedValue(undefined),
      onEvent: vi.fn().mockReturnValue(() => {}),
    },
  },
  writable: true,
})
