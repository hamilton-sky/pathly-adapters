import React from 'react'
import { LayoutGrid, Activity } from 'lucide-react'
import { useStore } from '../../store'
import { Tooltip } from '../ui'
import { readFile } from '../../services/pathlyApi'
import styles from './TopBar.module.css'

export function PanelNav(): JSX.Element {
  const { activePanel, selectedItem, lastUsedFlowPath, setActivePanel, setSelectedItem, setLastUsedFlowPath } = useStore()

  return (
    <div style={{ display: 'flex', gap: 4, marginLeft: 12, flexShrink: 0 }}>
      <Tooltip label="Flow canvas" shortcut="Ctrl+1" placement="bottom">
        <button
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
          <LayoutGrid size={13} />
          Canvas
        </button>
      </Tooltip>
      <Tooltip label="Live monitor" shortcut="Ctrl+3" placement="bottom">
        <button
          data-testid="topbar-panel-monitor"
          className={`${styles.navBtn} ${activePanel === 'monitor' ? styles.navBtnActive : ''}`}
          onClick={() => setActivePanel('monitor')}
        >
          <Activity size={13} />
          Monitor
        </button>
      </Tooltip>
    </div>
  )
}
