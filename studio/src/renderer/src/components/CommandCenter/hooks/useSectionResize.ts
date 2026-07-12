import { useCallback } from 'react'

// Per-board width floor (px). Mirrored by `.board { min-width }` in BoardSection.module.css
// so drag-resize and the auto-layout floor agree.
const MIN = 220

// Boards are always laid out side-by-side (row), so resizing is always horizontal —
// the handle adjusts the widths of the two boards it sits between.
export function useSectionResize(
  onResize: (id: string, px: number) => void,
) {
  return useCallback(
    (e: React.MouseEvent, prevId: string, nextId: string) => {
      e.preventDefault()
      const handle = e.currentTarget as HTMLElement
      const prevEl = handle.previousElementSibling as HTMLElement | null
      const nextEl = handle.nextElementSibling as HTMLElement | null
      if (!prevEl || !nextEl) return

      const startPos = e.clientX
      const startPrev = prevEl.offsetWidth
      const startNext = nextEl.offsetWidth

      const move = (ev: MouseEvent) => {
        const d = ev.clientX - startPos
        const np = Math.max(MIN, startPrev + d)
        const nn = Math.max(MIN, startNext - d)
        prevEl.style.flex = `0 0 ${np}px`
        nextEl.style.flex = `0 0 ${nn}px`
        onResize(prevId, np)
        onResize(nextId, nn)
      }

      const up = () => {
        document.removeEventListener('mousemove', move)
        document.removeEventListener('mouseup', up)
        document.body.style.cursor = ''
      }

      document.addEventListener('mousemove', move)
      document.addEventListener('mouseup', up)
      document.body.style.cursor = 'col-resize'
    },
    [onResize],
  )
}
