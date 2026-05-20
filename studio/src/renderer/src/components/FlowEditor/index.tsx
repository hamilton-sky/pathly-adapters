import { useMemo, useState } from 'react'
import { useStore } from '../../store'
import { useTheme } from '../../useTheme'
import { makeFlowEditorStyles } from './FlowEditor.styles'
import { useFlowFile } from './hooks/useFlowFile'
import { VisualView } from './VisualView'
import { YamlView } from './YamlView'
import { validateFlow } from './utils/validateFlow'
import { useProjectFiles } from '../../hooks/useProjectFiles'

type TabMode = 'visual' | 'yaml'

export function FlowEditor(): JSX.Element {
  const { selectedItem, markDirty, clearDirty } = useStore()
  const t = useTheme()
  const styles = makeFlowEditorStyles(t)
  const [tab, setTab] = useState<TabMode>('visual')
  const { sections } = useProjectFiles()

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

  function sectionAllItems(key: string): string[] {
    const s = sections[key]
    if (!s) return []
    return [
      ...(s.items ?? []),
      ...(s.subdirs ?? []).flatMap((sd) => sd.files ?? []),
    ].map((item) => item.name.replace(/\.[^.]+$/, ''))
  }

  const knownBehaviors = useMemo(() => {
    const skills = ['Skills', 'UserSkills', 'My Skills'].flatMap(sectionAllItems)
    const agents = ['Agents', 'UserAgents', 'My Agents'].flatMap(sectionAllItems)
    return [...new Set([...skills, ...agents])]
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sections])

  const yamlValidationIssues = useMemo(
    () => (flowData ? validateFlow(flowData, knownBehaviors) : []),
    [flowData, knownBehaviors]
  )

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
      {saveError && (
        <div style={{ padding: '4px 12px', backgroundColor: `${t.red}22`, borderBottom: `1px solid ${t.red}`, flexShrink: 0 }}>
          <span style={styles.error}>{saveError}</span>
        </div>
      )}
      <div style={styles.content}>
        {tab === 'visual' && (
          <VisualView
            data={flowData}
            onChange={handleVisualChange}
            onSave={handleVisualSave}
            tab={tab}
            onTabClick={onTabClick}
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
            validationIssues={yamlValidationIssues}
            tab={tab}
            onTabClick={onTabClick}
          />
        )}
      </div>
    </div>
  )
}
