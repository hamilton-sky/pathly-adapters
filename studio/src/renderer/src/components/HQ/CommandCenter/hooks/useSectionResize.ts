import { useCallback } from 'react'
import type { Direction } from '../types'

const MIN = 220

export function useSectionResize(
  direction: Direction,
  onResize: (id: string, px: number) => void,
) {
  return useCallback(
    (e: React.MouseEvent, prevId: string, nextId: string) => {
      e.preventDefault()
      const handle = e.currentTarget as HTMLElement
      const prevEl = handle.previousElementSibling as HTMLElement | null
      const nextEl = handle.nextElementSibling as HTMLElement | null
      if (!prevEl || !nextEl) return

      const vertical = direction === 'column'
      const startPos = vertical ? e.clientY : e.clientX
      const startPrev = vertical ? prevEl.offsetHeight : prevEl.offsetWidth
      const startNext = vertical ? nextEl.offsetHeight : nextEl.offsetWidth

      const move = (ev: MouseEvent) => {
        const d = (vertical ? ev.clientY : ev.clientX) - startPos
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
      document.body.style.cursor = vertical ? 'row-resize' : 'col-resize'
    },
    [direction, onResize],
  )
}
