import React from 'react'
import { LayoutGrid, Activity, BookOpen, Database } from 'lucide-react'
import { useStore } from '../../store'
import { Tooltip } from '../ui'
import { readFile } from '../../services/pathlyApi'
import styles from './TopBar.module.css'

export function PanelNav(): JSX.Element {
  const { activePanel, selectedItem, lastUsedFlowPath, skillNotebookPath, setActivePanel, setSelectedItem, setLastUsedFlowPath } = useStore()

  return (
    <div style={{ display: 'flex', gap: 4, marginLeft: 12, flexShrink: 0 }}>
      <Tooltip label="Flow canvas" shortcut="Ctrl+1" placement="bottom">
        <button
          type="button"
          data-testid="topbar-panel-flow"
          className={`${styles.navBtn} ${activePanel === 'flow' ? styles.navBtnActive : ''}`}
          onClick={() => {
            setActivePanel('flow')
            if ((!selectedItem || selectedItem.type !== 'flow') && lastUsedFlowPath) {
              readFile(lastUsedFlowPath)
                .then(() => setSelectedItem({ name: lastUsedFlowPath.split('/').pop() ?? lastUsedFlowPath, path: lastUsedFlowPath, type: 'flow' }))
                .catch(() => setLastUsedFlowPath(null))
            }
          }}
        >
          <LayoutGrid size={15} />
          Canvas
        </button>
      </Tooltip>
      <Tooltip
        label={skillNotebookPath ? 'Skill notebook' : 'Open a skill .md file to use the notebook'}
        shortcut={skillNotebookPath ? 'Ctrl+2' : undefined}
        placement="bottom"
      >
        <button
          type="button"
          data-testid="topbar-panel-notebook"
          className={`${styles.navBtn} ${activePanel === 'skill-notebook' ? styles.navBtnActive : ''} ${!skillNotebookPath ? styles.navBtnDisabled : ''}`}
          onClick={() => setActivePanel('skill-notebook')}
        >
          <BookOpen size={15} />
          Notebook
        </button>
      </Tooltip>
      <Tooltip label="Live monitor" shortcut="Ctrl+3" placement="bottom">
        <button
          type="button"
          data-testid="topbar-panel-monitor"
          data-label="Monitor"
          className={`${styles.navBtn} ${activePanel === 'monitor' ? styles.navBtnActive : ''}`}
          onClick={() => setActivePanel('monitor')}
        >
          <Activity size={15} />
          Monitor
        </button>
      </Tooltip>
      <Tooltip label="Pipeline database explorer" shortcut="Ctrl+4" placement="bottom">
        <button
          type="button"
          data-testid="topbar-panel-db-explorer"
          className={`${styles.navBtn} ${activePanel === 'db-explorer' ? styles.navBtnActive : ''}`}
          onClick={() => setActivePanel('db-explorer')}
        >
          <Database size={15} />
          DB Explorer
        </button>
      </Tooltip>
    </div>
  )
}
