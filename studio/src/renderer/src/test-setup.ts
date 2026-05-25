import { vi } from 'vitest'

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
