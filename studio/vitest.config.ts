import { defineConfig } from 'vitest/config'
export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/renderer/src/test-setup.ts'],
    // Report-only coverage (v8/c8). No enforced thresholds yet — raising the
    // floor is an explicit project policy decision, not a starter default.
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'html'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['**/*.test.{ts,tsx}', '**/*.d.ts', 'src/renderer/src/test-setup.ts'],
    },
  },
})
