import { useChatStore, type HqContextManifest } from '../../../../store/chatStore'

/** The newest answer's context manifest that was actually assembled — the
 *  per-section sizes the composer's meter estimates the next question from. */
export function useLatestManifest(): HqContextManifest | null {
  return useChatStore((s) => {
    for (let i = s.messages.length - 1; i >= 0; i--) {
      const m = s.messages[i].contextManifest
      if (m && !m.unavailable) return m
    }
    return null
  })
}
