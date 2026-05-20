import { useState } from 'react'
import type { FlowYaml } from '../../../../types'

interface ActionEntry {
  skill: string
  message: string
}

interface UseActionEditorResult {
  editingActionIdx: number | null
  editSkill: string
  editMessage: string
  setEditSkill: (v: string) => void
  setEditMessage: (v: string) => void
  startEditAction: (idx: number) => void
  commitEditAction: () => void
  cancelEditAction: () => void
  removeAction: (idx: number) => void
}

export function useActionEditor(
  actionKey: string,
  actionList: ActionEntry[],
  actions: Record<string, ActionEntry[]>,
  data: FlowYaml,
  onDataChange: ((updated: FlowYaml) => void) | undefined,
): UseActionEditorResult {
  const [editingActionIdx, setEditingActionIdx] = useState<number | null>(null)
  const [editSkill, setEditSkill] = useState('')
  const [editMessage, setEditMessage] = useState('')

  function startEditAction(idx: number): void {
    setEditingActionIdx(idx)
    setEditSkill(actionList[idx].skill)
    setEditMessage(actionList[idx].message)
  }

  function commitEditAction(): void {
    if (editingActionIdx === null || !onDataChange) return
    const newList = [...actionList]
    newList[editingActionIdx] = { skill: editSkill.trim(), message: editMessage.trim() }
    onDataChange({ ...data, transition_actions: { ...actions, [actionKey]: newList } })
    setEditingActionIdx(null)
  }

  function cancelEditAction(): void {
    setEditingActionIdx(null)
  }

  function removeAction(idx: number): void {
    if (!onDataChange) return
    const newList = [...actionList]
    newList.splice(idx, 1)
    onDataChange({ ...data, transition_actions: { ...actions, [actionKey]: newList } })
  }

  return {
    editingActionIdx,
    editSkill,
    editMessage,
    setEditSkill,
    setEditMessage,
    startEditAction,
    commitEditAction,
    cancelEditAction,
    removeAction,
  }
}
