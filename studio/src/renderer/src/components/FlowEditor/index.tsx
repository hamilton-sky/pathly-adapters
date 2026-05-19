import { useState } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import { makeFlowEditorStyles } from './FlowEditor.styles'
import { useFlowFile } from './hooks/useFlowFile'
import { VisualView } from './VisualView'
import { YamlView } from './YamlView'

type TabMode = 'visual' | 'yaml'

export function FlowEditor(): JSX.Element {
  const { selectedItem, markDirty, clearDirty } = useStore()
  const t = useTheme()
  const styles = makeFlowEditorStyles(t)
  const [tab, setTab] = useState<TabMode>('visual')

  const {
    flowData,
    rawYaml,
    loading,
    saveError,
    yamlSyncContent,
    handleTabSwitch,
    handleVisualChange,
    handleYamlParsed,
    handleYamlContentChange,
    handleYamlParseError,
    handleVisualSave,
    handleYamlSave
  } = useFlowFile(selectedItem, markDirty, clearDirty)

  function onTabClick(next: TabMode): void {
    const resolved = handleTabSwitch(next, tab)
    setTab(resolved)
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
            onClick={() => onTabClick('visual')}
          >
            Visual
          </button>
          <button
            style={tab === 'yaml' ? styles.tabActive : styles.tab}
            onClick={() => onTabClick('yaml')}
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
            onParseError={handleYamlParseError}
            onDirty={handleYamlContentChange}
            onSave={handleYamlSave}
            syncContent={yamlSyncContent}
          />
        )}
      </div>
    </div>
  )
}
