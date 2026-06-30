import { defineConfig, externalizeDepsPlugin } from 'electron-vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    resolve: {
      // Force one canonical module id for shared main-process modules. Without
      // this, importing a leaf like apiConfig as './apiConfig' (from index.ts)
      // vs '../apiConfig' (from ipc/*) made rollup mint two module instances on
      // Windows; the ipc copy's module-level state was never initialized.
      alias: {
        '@main': resolve(__dirname, 'src/main')
      }
    }
  },
  preload: {
    plugins: [externalizeDepsPlugin()],
    build: {
      lib: {
        entry: resolve(__dirname, 'src/main/preload/index.ts')
      }
    }
  },
  renderer: {
    root: resolve(__dirname, 'src/renderer'),
    // Mermaid lazy-loads some diagram defs (mindmap, timeline, …) via a RELATIVE dynamic
    // import ("./chunks/mermaid.core/mindmap-definition-*.mjs"). Vite's dep pre-bundling
    // rewrites mermaid into .vite/deps, and those relative chunk paths then 404 at render
    // time — so mindmap throws while core diagrams (flowchart) still work. Excluding mermaid
    // from pre-bundling serves it from its real dist/ folder so the lazy chunks resolve.
    optimizeDeps: {
      exclude: ['mermaid']
    },
    build: {
      rollupOptions: {
        input: resolve(__dirname, 'src/renderer/index.html')
      }
    },
    plugins: [react()]
  }
})
