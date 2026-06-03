import { useEffect } from 'react'
import type { RefObject } from 'react'

const FOCUSABLE =
  'button:not(:disabled),[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex]:not([tabindex="-1"])'

export function useFocusTrap(ref: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const previousFocus = document.activeElement

    const container = ref.current
    if (!container) return

    const focusableEls = Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE))
    if (focusableEls.length > 0) {
      focusableEls[0].focus()
    }

    function onKeyDown(e: KeyboardEvent): void {
      if (e.key !== 'Tab') return

      const els = Array.from(container!.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (els.length === 0) return

      const first = els[0]
      const last  = els[els.length - 1]

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }

    document.addEventListener('keydown', onKeyDown)

    return () => {
      document.removeEventListener('keydown', onKeyDown)
      if (previousFocus instanceof HTMLElement && document.contains(previousFocus)) {
        previousFocus.focus()
      }
    }
  }, [ref])
}
