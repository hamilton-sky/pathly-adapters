// Lightweight spawn-lifecycle tracing → main-process console (the `npm run dev` terminal).
// Flip SPAWN_DEBUG to false to silence.
const SPAWN_DEBUG = true

export function slog(...a: unknown[]): void {
  if (SPAWN_DEBUG) console.log('[spawn]', ...a)
}
