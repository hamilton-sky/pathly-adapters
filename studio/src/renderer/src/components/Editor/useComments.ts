import { useState, useEffect, useCallback, useRef } from 'react'
import { readFile, writeFile } from '../../services/pathlyApi'

export interface Comment {
  id: string
  lineNumber: number
  lineText: string
  body: string
  resolved: boolean
  createdAt: string
}

function sidecarPath(filePath: string): string {
  return filePath + '.comments.json'
}

export function useComments(filePath: string | null) {
  const [comments, setComments] = useState<Comment[]>([])
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!filePath) { setComments([]); return }
    readFile(sidecarPath(filePath))
      .then((raw) => {
        if (!raw) { setComments([]); return }
        const data = JSON.parse(raw) as { comments: Comment[] }
        setComments(data.comments ?? [])
      })
      .catch(() => setComments([]))
  }, [filePath])

  const persist = useCallback((next: Comment[]) => {
    if (!filePath) return
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      void writeFile(sidecarPath(filePath), JSON.stringify({ comments: next }, null, 2))
    }, 400)
  }, [filePath])

  const add = useCallback((lineNumber: number, lineText: string, body: string) => {
    const comment: Comment = {
      id: `c-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
      lineNumber,
      lineText: lineText.trim().slice(0, 120),
      body,
      resolved: false,
      createdAt: new Date().toISOString(),
    }
    setComments((prev) => {
      const next = [...prev, comment].sort((a, b) => a.lineNumber - b.lineNumber)
      persist(next)
      return next
    })
  }, [persist])

  const edit = useCallback((id: string, body: string) => {
    setComments((prev) => {
      const next = prev.map((c) => c.id === id ? { ...c, body } : c)
      persist(next)
      return next
    })
  }, [persist])

  const resolve = useCallback((id: string) => {
    setComments((prev) => {
      const next = prev.map((c) => c.id === id ? { ...c, resolved: true } : c)
      persist(next)
      return next
    })
  }, [persist])

  const remove = useCallback((id: string) => {
    setComments((prev) => {
      const next = prev.filter((c) => c.id !== id)
      persist(next)
      return next
    })
  }, [persist])

  return { comments, add, edit, resolve, remove }
}
