import { useRef, useEffect } from 'react'
import type { RefObject } from 'react'
import type { Comment } from '../useComments'

export function useCommentKeyboardNav(
  containerRef: RefObject<HTMLDivElement>,
  unresolvedComments: Comment[],
  scrollToComment: (id: string) => void,
): void {
  const activeIndexRef = useRef(-1)
  const commentsRef = useRef(unresolvedComments)
  const scrollRef = useRef(scrollToComment)

  useEffect(() => { commentsRef.current = unresolvedComments })
  useEffect(() => { scrollRef.current = scrollToComment })

  useEffect(() => {
    activeIndexRef.current = -1
  }, [unresolvedComments])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    function handleKeyDown(e: KeyboardEvent): void {
      if (!e.altKey) return
      if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
      e.preventDefault()

      const comments = commentsRef.current
      if (!comments.length) return

      const direction = e.key === 'ArrowDown' ? 1 : -1
      const len = comments.length
      let next = activeIndexRef.current + direction

      if (next >= len) next = 0
      if (next < 0) next = len - 1

      activeIndexRef.current = next
      scrollRef.current(comments[next].id)
    }

    container.addEventListener('keydown', handleKeyDown)
    return () => container.removeEventListener('keydown', handleKeyDown)
  }, [containerRef])
}
