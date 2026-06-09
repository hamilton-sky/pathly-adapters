import { useCallback } from 'react'
import type { FlowYaml, CommentEntry, CommentShape } from '../../../types'

export function useFlowComments(
  dataRef: React.MutableRefObject<FlowYaml>,
  onChange: (updated: FlowYaml) => void
) {
  const addComment = useCallback((shape: CommentShape, x: number, y: number): void => {
    const id = `c${String(Date.now()).slice(-8)}`
    const entry: CommentEntry = { id, text: '', color: 'yellow', shape, x, y }
    const d = dataRef.current
    onChange({ ...d, _comments: [...(d._comments ?? []), entry] })
  }, [dataRef, onChange])

  const updateComment = useCallback((commentId: string, patch: Partial<Omit<CommentEntry, 'id'>>): void => {
    const d = dataRef.current
    onChange({ ...d, _comments: (d._comments ?? []).map(c => c.id === commentId ? { ...c, ...patch } : c) })
  }, [dataRef, onChange])

  const deleteComment = useCallback((commentId: string): void => {
    const d = dataRef.current
    onChange({ ...d, _comments: (d._comments ?? []).filter(c => c.id !== commentId) })
  }, [dataRef, onChange])

  const moveComment = useCallback((commentId: string, x: number, y: number): void => {
    const d = dataRef.current
    onChange({ ...d, _comments: (d._comments ?? []).map(c => c.id === commentId ? { ...c, x, y } : c) })
  }, [dataRef, onChange])

  return { addComment, updateComment, deleteComment, moveComment }
}
