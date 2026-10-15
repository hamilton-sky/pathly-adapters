import { useEffect, type RefObject } from 'react'

/** While the popover is open: a mousedown outside *root* closes it, and Escape
 *  closes it and returns focus to *returnFocus* (the chip that owns the tab). */
export function useScopeDismiss(
  open: boolean,
  root: RefObject<HTMLElement>,
  close: () => void,
  returnFocus: () => void,
): void {
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent): void => {
      if (!root.current?.contains(e.target as Node)) close()
    }
    const onKey = (e: KeyboardEvent): void => {
      if (e.key !== 'Escape') return
      close()
      returnFocus()
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, root, close, returnFocus])
}
