import React from "react";
import { LayoutGrid, Activity, BookOpen, Database, MessageSquare } from "lucide-react";
import { useStore } from "../../store";
import { Tooltip } from "../ui";
import { readFile } from "../../services/pathlyApi";
import styles from "./TopBar.module.css";

interface PanelNavProps {
  compact?: boolean
}

export function PanelNav({ compact }: PanelNavProps): JSX.Element {
  const {
    activePanel,
    selectedItem,
    lastUsedFlowPath,
    setActivePanel,
    setSelectedItem,
    setLastUsedFlowPath,
  } = useStore();

  return (
    <div className={styles.panelNav}>
      <Tooltip label="Communication board" shortcut="Ctrl+1" placement="bottom">
        <button
          type="button"
          data-testid="topbar-panel-command-center"
          className={`${styles.navBtn} ${activePanel === "command-center" ? styles.navBtnActive : ""}`}
          onClick={() => setActivePanel("command-center")}
        >
          <MessageSquare size={15} />
          {!compact && <span className={styles.navBtnLabel}>Command Center</span>}
        </button>
      </Tooltip>
      <Tooltip label="Live monitor" shortcut="Ctrl+2" placement="bottom">
        <button
          type="button"
          data-testid="topbar-panel-monitor"
          data-label="Monitor"
          className={`${styles.navBtn} ${activePanel === "monitor" ? styles.navBtnActive : ""}`}
          onClick={() => setActivePanel("monitor")}
        >
          <Activity size={15} />
          {!compact && <span className={styles.navBtnLabel}>Monitor</span>}
        </button>
      </Tooltip>
      <Tooltip
        label="Pipeline database explorer"
        shortcut="Ctrl+3"
        placement="bottom"
      >
        <button
          type="button"
          data-testid="topbar-panel-db-explorer"
          className={`${styles.navBtn} ${activePanel === "db-explorer" ? styles.navBtnActive : ""}`}
          onClick={() => setActivePanel("db-explorer")}
        >
          <Database size={15} />
          {!compact && <span className={styles.navBtnLabel}>DB Explorer</span>}
        </button>
      </Tooltip>
      <Tooltip label="Markdown notebook" shortcut="Ctrl+4" placement="bottom">
        <button
          type="button"
          data-testid="topbar-panel-notebook"
          className={`${styles.navBtn} ${activePanel === "notebook" ? styles.navBtnActive : ""}`}
          onClick={() => setActivePanel("notebook")}
        >
          <BookOpen size={15} />
          {!compact && <span className={styles.navBtnLabel}>Notebook</span>}
        </button>
      </Tooltip>
      <Tooltip label="Flow canvas" shortcut="Ctrl+5" placement="bottom">
        <button
          type="button"
          data-testid="topbar-panel-flow"
          className={`${styles.navBtn} ${activePanel === "flow" ? styles.navBtnActive : ""}`}
          onClick={() => {
            setActivePanel("flow");
            if (
              (!selectedItem || selectedItem.type !== "flow") &&
              lastUsedFlowPath
            ) {
              readFile(lastUsedFlowPath)
                .then(() =>
                  setSelectedItem({
                    name: lastUsedFlowPath.split("/").pop() ?? lastUsedFlowPath,
                    path: lastUsedFlowPath,
                    type: "flow",
                  }),
                )
                .catch(() => setLastUsedFlowPath(null));
            }
          }}
        >
          <LayoutGrid size={15} />
          {!compact && <span className={styles.navBtnLabel}>Canvas</span>}
        </button>
      </Tooltip>
    </div>
  );
}
