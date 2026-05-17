import { useEffect, useRef, useState } from 'react'
import * as jsYaml from 'js-yaml'
import { useStore } from '../../store'
import type { FlowYaml } from '../../types'
import { VisualView } from './VisualView'
import { YamlView } from './YamlView'

type TabMode = 'visual' | 'yaml'

export function FlowEditor(): JSX.Element {
  const { selectedItem, markDirty, clearDirty } = useStore()
  const [flowData, setFlowData] = useState<FlowYaml | null>(null)
  const [rawYaml, setRawYaml] = useState('')
  const [tab, setTab] = useState<TabMode>('visual')
  const [loading, setLoading] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  // Content to push into YamlView when switching from Visual
  const [yamlSyncContent, setYamlSyncContent] = useState<string | null>(null)
  const prevTabRef = useRef<TabMode>('visual')

  useEffect(() => {
    if (!selectedItem) return
    setLoading(true)
    setSaveError(null)
    setTab('visual')
    prevTabRef.current = 'visual'
    setYamlSyncContent(null)
    window.pathly.fs
      .read(selectedItem.path)
      .then((content) => {
        setRawYaml(content ?? '')
        try {
          const parsed = jsYaml.load(content ?? '') as FlowYaml
          setFlowData(parsed)
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

  function handleTabSwitch(next: TabMode): void {
    if (next === tab) return
    if (next === 'yaml' && flowData) {
      // Serialize current graph state to YAML string
      const serialized = jsYaml.dump(flowData, { lineWidth: 120 })
      setRawYaml(serialized)
      setYamlSyncContent(serialized)
    } else if (next === 'visual' && rawYaml) {
      // Parse current YAML and re-render graph
      try {
        const parsed = jsYaml.load(rawYaml) as FlowYaml
        setFlowData(parsed)
        setYamlSyncContent(null)
      } catch {
        // YAML is invalid — stay on YAML tab and show error
        setSaveError('Fix YAML errors before switching to Visual view')
        return
      }
    }
    prevTabRef.current = tab
    setTab(next)
  }

  function handleVisualChange(updated: FlowYaml): void {
    setFlowData(updated)
    if (selectedItem) markDirty(selectedItem.path)
  }

  function handleYamlParsed(parsed: FlowYaml): void {
    setFlowData(parsed)
  }

  function handleYamlContentChange(): void {
    if (selectedItem) markDirty(selectedItem.path)
  }

  async function handleVisualSave(): Promise<void> {
    if (!selectedItem || !flowData) return
    setSaveError(null)
    const content = jsYaml.dump(flowData, { lineWidth: 120 })
    try {
      await window.pathly.fs.write(selectedItem.path, content)
      clearDirty(selectedItem.path)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    }
  }

  async function handleYamlSave(content: string): Promise<void> {
    if (!selectedItem) return
    setSaveError(null)
    try {
      await window.pathly.fs.write(selectedItem.path, content)
      setRawYaml(content)
      clearDirty(selectedItem.path)
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : String(err))
    }
  }

  if (loading) {
    return (
      <div style={styles.panel}>
        <span style={styles.message}>Loading…</span>
      </div>
    )
  }

  if (!selectedItem) {
    return (
      <div style={styles.panel}>
        <span style={styles.message}>Select a flow from the sidebar</span>
      </div>
    )
  }

  if (!flowData) {
    return (
      <div style={styles.panel}>
        <span style={styles.message}>Unable to parse flow YAML</span>
      </div>
    )
  }

  return (
    <div style={styles.panel}>
      <div style={styles.toolbar}>
        <div style={styles.tabs}>
          <button
            style={tab === 'visual' ? styles.tabActive : styles.tab}
            onClick={() => handleTabSwitch('visual')}
          >
            Visual
          </button>
          <button
            style={tab === 'yaml' ? styles.tabActive : styles.tab}
            onClick={() => handleTabSwitch('yaml')}
          >
            YAML
          </button>
        </div>
        {saveError && <span style={styles.error}>{saveError}</span>}
      </div>

      <div style={styles.content}>
        {tab === 'visual' && (
          <VisualView
            data={flowData}
            onChange={handleVisualChange}
            onSave={handleVisualSave}
          />
        )}
        {tab === 'yaml' && (
          <YamlView
            initialContent={rawYaml}
            onParsed={handleYamlParsed}
            onDirty={handleYamlContentChange}
            onSave={handleYamlSave}
            syncContent={yamlSyncContent}
          />
        )}
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: '#1e1e2e',
    overflow: 'hidden'
  },
  toolbar: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '6px 12px',
    backgroundColor: '#181825',
    borderBottom: '1px solid #313244',
    flexShrink: 0
  },
  tabs: {
    display: 'flex',
    gap: '4px'
  },
  tab: {
    background: 'none',
    border: '1px solid #45475a',
    borderRadius: '4px',
    color: '#a6adc8',
    cursor: 'pointer',
    padding: '3px 10px',
    fontSize: '12px'
  },
  tabActive: {
    background: '#313244',
    border: '1px solid #cba6f7',
    borderRadius: '4px',
    color: '#cba6f7',
    cursor: 'pointer',
    padding: '3px 10px',
    fontSize: '12px'
  },
  error: {
    color: '#f38ba8',
    fontSize: '12px'
  },
  content: {
    flex: 1,
    display: 'flex',
    overflow: 'hidden'
  },
  message: {
    color: '#6c7086',
    fontSize: '15px',
    margin: 'auto'
  }
}
