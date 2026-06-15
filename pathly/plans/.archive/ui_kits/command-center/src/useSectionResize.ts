import { useCallback } from 'react';
import type { BoardScope, Direction } from './types';

// ── useSectionResize ────────────────────────────────────────────────
// Drag a handle between two adjacent sections. Mutates flex-basis live and
// reports the final px sizes back to the store. Minimum 220px per section.

const MIN = 220;

export function useSectionResize(direction: Direction, onResize: (scope: BoardScope, px: number) => void) {
  return useCallback(
    (e: React.MouseEvent, prev: BoardScope, next: BoardScope) => {
      e.preventDefault();
      const handle = e.currentTarget as HTMLElement;
      const prevEl = handle.previousElementSibling as HTMLElement | null;
      const nextEl = handle.nextElementSibling as HTMLElement | null;
      if (!prevEl || !nextEl) return;

      const vertical = direction === 'column';
      const startPos = vertical ? e.clientY : e.clientX;
      const startPrev = vertical ? prevEl.offsetHeight : prevEl.offsetWidth;
      const startNext = vertical ? nextEl.offsetHeight : nextEl.offsetWidth;

      const move = (ev: MouseEvent) => {
        const d = (vertical ? ev.clientY : ev.clientX) - startPos;
        const np = Math.max(MIN, startPrev + d);
        const nn = Math.max(MIN, startNext - d);
        prevEl.style.flex = `0 0 ${np}px`;
        nextEl.style.flex = `0 0 ${nn}px`;
        onResize(prev, np);
        onResize(next, nn);
      };
      const up = () => {
        document.removeEventListener('mousemove', move);
        document.removeEventListener('mouseup', up);
        document.body.style.cursor = '';
      };
      document.addEventListener('mousemove', move);
      document.addEventListener('mouseup', up);
      document.body.style.cursor = vertical ? 'row-resize' : 'col-resize';
    },
    [direction, onResize],
  );
}
