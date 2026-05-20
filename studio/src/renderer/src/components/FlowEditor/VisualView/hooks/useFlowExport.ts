import { useState } from 'react'
import * as jsYaml from 'js-yaml'
import type { FlowYaml, FlowExportTarget, FlowExportRecord } from '../../../../types'
import { resolveExportPath } from '../../utils/exportPaths'
import { writeFile } from '../../../../services/pathlyApi'
import { useStore } from '../../../../store'

export function useFlowExport(data: FlowYaml) {
  const { projectPath, selectedItem } = useStore()
  const [exportTarget, setExportTarget] = useState<FlowExportTarget>('pathly-package')
  const [lastExport, setLastExport] = useState<FlowExportRecord | null>(null)
  const [exportToast, setExportToast] = useState<string | null>(null)
  const [showConfirmModal, setShowConfirmModal] = useState(false)

  function getFlowName(): string {
    if (selectedItem?.name) return selectedItem.name.replace(/\.flow\.yaml$/, '')
    return data.flow ?? 'flow'
  }

  async function doExport(): Promise<void> {
    if (!projectPath) return
    const flowName = getFlowName()
    const targetPath = resolveExportPath(exportTarget, { projectPath, flowName })
    const content = jsYaml.dump(data, { lineWidth: 120 })
    try {
      await writeFile(targetPath, content)
      const record: FlowExportRecord = { target: exportTarget, path: targetPath, at: new Date() }
      setLastExport(record)
      setExportToast(`Exported to ${targetPath}`)
      setTimeout(() => setExportToast(null), 4000)
    } catch (err) {
      setExportToast(`Export failed: ${err instanceof Error ? err.message : String(err)}`)
      setTimeout(() => setExportToast(null), 5000)
    }
  }

  function handleExportClick(hasErrors: boolean, hasWarnings: boolean): void {
    if (hasErrors) return
    if (hasWarnings) {
      setShowConfirmModal(true)
    } else {
      void doExport()
    }
  }

  function handleConfirmExport(): void {
    setShowConfirmModal(false)
    void doExport()
  }

  return {
    exportTarget,
    setExportTarget,
    lastExport,
    exportToast,
    showConfirmModal,
    setShowConfirmModal,
    doExport,
    handleExportClick,
    handleConfirmExport,
  }
}
