import { useEffect, useRef, useState } from 'react'
import type { FlowYaml } from '../../../../types'

interface UseRenameStateResult {
  renaming: boolean
  renameValue: string
  renameInputRef: React.RefObject<HTMLInputElement>
  setRenaming: (v: boolean) => void
  setRenameValue: (v: string) => void
  commitRename: () => void
}

export function useRenameState(
  stateId: string,
  data: FlowYaml,
  onRename?: (oldId: string, newId: string) => void,
): UseRenameStateResult {
  const [renaming, setRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState(stateId)
  const renameInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setRenameValue(stateId) }, [stateId])
  useEffect(() => { if (renaming) renameInputRef.current?.select() }, [renaming])

  function commitRename(): void {
    setRenaming(false)
    const newId = renameValue.trim().toUpperCase().replace(/[^A-Z0-9_]/g, '_')
    if (!newId || newId === stateId) { setRenameValue(stateId); return }
    if (data.states.includes(newId)) { setRenameValue(stateId); return }
    onRename?.(stateId, newId)
  }

  return { renaming, renameValue, renameInputRef, setRenaming, setRenameValue, commitRename }
}
