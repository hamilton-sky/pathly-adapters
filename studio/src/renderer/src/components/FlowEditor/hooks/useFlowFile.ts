import { useEffect, useRef, useState } from 'react'
import * as jsYaml from 'js-yaml'
import { readFile, writeFile } from '../../../services/pathlyApi'
import type { FlowYaml } from '../../../types'

type TabMode = 'visual' | 'yaml'

interface SelectedItem {
  path: string
}

interface UseFlowFileReturn {
  flowData: FlowYaml | null
  rawYaml: string
  loading: boolean
  saveError: string | null
  yamlParseError: string | null
  yamlSyncContent: string | null
  handleTabSwitch: (next: TabMode, currentTab: TabMode) => TabMode
  handleVisualChange: (updated: FlowYaml) => void
  handleYamlParsed: (parsed: FlowYaml) => void
  handleYamlContentChange: () => void
  handleYamlParseError: (err: string | null) => void
  handleVisualSave: () => Promise<void>
  handleYamlSave: (content: string) => Promise<void>
}

export function useFlowFile(
  selectedItem: SelectedItem | null | undefined,
  markDirty: (path: string) => void,
  clearDirty: (path: string) => void
): UseFlowFileReturn {
  const [flowData, setFlowData] = useState<FlowYaml | null>(null)
  const [rawYaml, setRawYaml] = useState('')
  const [loading, setLoading] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [yamlParseError, setYamlParseError] = useState<string | null>(null)
  const [yamlSyncContent, setYamlSyncContent] = useState<string | null>(null)

  const flowDataRef = useRef(flowData)
  useEffect(() => { flowDataRef.current = flowData }, [flowData])

  // Preserved snapshot of the last successfully parsed flow so the visual graph
  // stays intact while the user edits invalid YAML.
  const lastValidFlowDataRef = useRef<FlowYaml | null>(null)

  const rawYamlRef = useRef(rawYaml)
  useEffect(() => { rawYamlRef.current = rawYaml }, [rawYaml])

  useEffect(() => {
    if (!selectedItem) return
    setLoading(true)
    setSaveError(null)
    setYamlParseError(null)
    setYamlSyncContent(null)
    lastValidFlowDataRef.current = null
    readFile(selectedItem.path)
      .then((content) => {
        setRawYaml(content ?? '')
        try {
          const parsed = jsYaml.load(content ?? '') as FlowYaml
          setFlowData(parsed)
          lastValidFlowDataRef.current = parsed
        } catch {
          setFlowData(null)
        }
      })
      .catch(() => {
        setRawYaml('')
        setFlowData(null)
      })
      .finally(() => setLoading(false))
  }, [selectedItem?.path])

  function handleTabSwitch(next: TabMode, currentTab: TabMode): TabMode {
    if (next === currentTab) return currentTab
    const currentFlowData = flowDataRef.current
    const currentRawYaml = rawYamlRef.current
    if (next === 'yaml' && currentFlowData) {
      const serialized = jsYaml.dump(currentFlowData, { lineWidth: 120 })
      setRawYaml(serialized)
      setYamlSyncContent(serialized)
    } else if (next === 'visual' && currentRawYaml) {
      try {
        const parsed = jsYaml.load(currentRawYaml) as FlowYaml
        setFlowData(parsed)
        lastValidFlowDataRef.current = parsed
        setYamlSyncContent(null)
        setYamlParseError(null)
      } catch {
        // YAML is invalid — fall back to the last valid snapshot if available
        // so the visual graph is not destroyed. A warning is shown in the toolbar.
        const fallback = lastValidFlowDataRef.current
        if (fallback) {
          setFlowData(fallback)
          setSaveError('YAML has errors — showing last valid graph. Fix YAML and switch back to sync.')
        } else {
          setSaveError('Fix YAML errors before switching to Visual view')
          return currentTab
        }
        setYamlSyncContent(null)
      }
    }
    return next
  }

  function handleVisualChange(updated: FlowYaml): void {
    setFlowData(updated)
    if (selectedItem) markDirty(selectedItem.path)
  }

  function handleYamlParsed(parsed: FlowYaml): void {
    setFlowData(parsed)
    lastValidFlowDataRef.current = parsed
    setYamlParseError(null)
  }

  function handleYamlParseError(err: string | null): void {
    setYamlParseError(err)
  }

  function handleYamlContentChange(): void {
    if (selectedItem) markDirty(selectedItem.path)
  }

  async function handleVisualSave(): Promise<void> {
    if (!selectedItem || !flowDataRef.current) return
    setSaveError(null)
    const content = jsYaml.dump(flowDataRef.current, { lineWidth: 120 })
    try {
      await writeFile(selectedItem.path, content)
      clearDirty(selectedItem.path)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleYamlSave(content: string): Promise<void> {
    if (!selectedItem) return
    setSaveError(null)
    try {
      await writeFile(selectedItem.path, content)
      setRawYaml(content)
      clearDirty(selectedItem.path)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    }
  }

  return {
    flowData,
    rawYaml,
    loading,
    saveError,
    yamlParseError,
    yamlSyncContent,
    handleTabSwitch,
    handleVisualChange,
    handleYamlParsed,
    handleYamlContentChange,
    handleYamlParseError,
    handleVisualSave,
    handleYamlSave
  }
}
