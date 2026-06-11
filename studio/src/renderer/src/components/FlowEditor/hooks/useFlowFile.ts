import { useEffect, useRef, useState } from 'react'
import * as jsYaml from 'js-yaml'
import { fetchFlowGraph, saveFlow, saveFlowGraph } from '../../../services/pathlyApi'
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

function flowNameFromPath(path: string): string {
  const normalized = path.replace(/\\/g, '/')
  const filename = normalized.split('/').pop() ?? ''
  return filename.replace(/\.flow\.yaml$/i, '')
}

function parseFirstDoc(content: string): FlowYaml | null {
  try {
    const docs = jsYaml.loadAll(content) as FlowYaml[]
    return docs.find(d => d != null) ?? null
  } catch {
    return null
  }
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

  const lastValidFlowDataRef = useRef<FlowYaml | null>(null)

  const rawYamlRef = useRef(rawYaml)
  useEffect(() => { rawYamlRef.current = rawYaml }, [rawYaml])

  useEffect(() => {
    if (!selectedItem) return
    const name = flowNameFromPath(selectedItem.path)
    if (!name) return
    setLoading(true)
    setSaveError(null)
    setYamlParseError(null)
    setYamlSyncContent(null)
    lastValidFlowDataRef.current = null
    fetchFlowGraph(name)
      .then((result) => {
        if (result?.graph) {
          const parsed = result.graph
          setFlowData(parsed)
          lastValidFlowDataRef.current = parsed
          setRawYaml(jsYaml.dump(parsed, { lineWidth: 120 }))
        } else {
          setFlowData(null)
          setRawYaml('')
          setYamlParseError('Empty or unreadable flow graph')
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
      const parsed = parseFirstDoc(currentRawYaml)
      if (parsed) {
        setFlowData(parsed)
        lastValidFlowDataRef.current = parsed
        setYamlSyncContent(null)
        setYamlParseError(null)
      } else {
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
    const name = flowNameFromPath(selectedItem.path)
    if (!name) return
    setSaveError(null)
    try {
      await saveFlowGraph(name, flowDataRef.current)
      clearDirty(selectedItem.path)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleYamlSave(content: string): Promise<void> {
    if (!selectedItem) return
    const name = flowNameFromPath(selectedItem.path)
    if (!name) return
    setSaveError(null)
    try {
      await saveFlow(name, content)
      setRawYaml(content)
      clearDirty(selectedItem.path)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    }
  }

  return {
    flowData, rawYaml, loading, saveError, yamlParseError, yamlSyncContent,
    handleTabSwitch, handleVisualChange, handleYamlParsed,
    handleYamlContentChange, handleYamlParseError, handleVisualSave, handleYamlSave,
  }
}
