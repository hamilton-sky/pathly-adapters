import { Folder, FolderOpen, FolderPlus, Lock, Plus } from 'lucide-react'
import type { PathlyItem } from '../../types'
import type { PlanFolder } from '../../hooks/usePlanFiles'
import { IconButton } from '../ui'
import { SectionHeader } from './SectionHeader'
import { WorkspaceItem } from './WorkspaceItem'
import { PROTECTED_FILENAMES } from './constants'
import styles from './Sidebar.module.css'

interface Props {
  planFolders: PlanFolder[]
  selectedItem: PathlyItem | null
  dirtyItems: Set<string>
  lowerFilter: string
  activeTopic: string | null
  renamingPath: string | null
  renameValue: string
  planOpen: boolean
  onTogglePlan: () => void
  onToggleFolder: (name: string) => void
  onFolderClick: (name: string) => void
  onNewPlan: (e: React.MouseEvent<HTMLButtonElement>) => void
  onCreatePlanFile: (e: React.MouseEvent<HTMLButtonElement>) => void
  onSelect: (item: PathlyItem) => void
  onRenameChange: (v: string) => void
  onRenameCommit: (item: PathlyItem, itemDir: string) => void
  onRenameCancel: () => void
  onStartRename: (item: PathlyItem, itemDir: string) => void
  onStartDelete: (item: PathlyItem) => void
}

export function PlanSection({
  planFolders,
  selectedItem,
  dirtyItems,
  lowerFilter,
  activeTopic,
  renamingPath,
  renameValue,
  planOpen,
  onTogglePlan,
  onToggleFolder,
  onFolderClick,
  onNewPlan,
  onCreatePlanFile,
  onSelect,
  onRenameChange,
  onRenameCommit,
  onRenameCancel,
  onStartRename,
  onStartDelete,
}: Props): JSX.Element {
  const visibleFolders = lowerFilter
    ? planFolders.filter((f) =>
        f.name.toLowerCase().includes(lowerFilter) ||
        f.files.some((file) => file.name.toLowerCase().includes(lowerFilter))
      )
    : planFolders

  return (
    <>
      <SectionHeader
        label="Plan"
        open={planOpen}
        onToggle={onTogglePlan}
        sub={activeTopic ? `[${activeTopic}]` : undefined}
        actionsLeft={
          <IconButton onClick={onNewPlan} title="New plan folder">
            <FolderPlus size={12} />
          </IconButton>
        }
        actions={
          <IconButton onClick={onCreatePlanFile} title="New file in active plan" disabled={!activeTopic}>
            <Plus size={12} />
          </IconButton>
        }
      />
      {planOpen && (
        <div>
          {visibleFolders.length === 0 && (
            <div className={styles.convEmpty}>No plans</div>
          )}
          {visibleFolders.map((folder) => {
            const isActive = folder.name === activeTopic
            const badge = folder.convTotal > 0
              ? `${folder.convDone}/${folder.convTotal}✓`
              : null

            const filteredFiles = lowerFilter
              ? folder.files.filter((f) => f.name.toLowerCase().includes(lowerFilter))
              : folder.files

            return (
              <div key={folder.name}>
                <button
                  className={`${styles.subdirHeader} ${isActive ? styles.itemRowSelected : ''}`}
                  onClick={() => {
                    onToggleFolder(folder.name)
                    onFolderClick(folder.name)
                  }}
                  title={folder.path}
                >
                  {folder.open
                    ? <FolderOpen size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                    : <Folder size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                  }
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {folder.name}
                  </span>
                  <span className={styles.lockIcon} title="Managed by Pathly — cannot be renamed or moved">
                    <Lock size={10} />
                  </span>
                  {badge && (
                    <span
                      className={styles.planBadge}
                      style={{ color: folder.convDone === folder.convTotal ? 'var(--green)' : 'var(--text-muted)' }}
                      title={`${folder.convDone} of ${folder.convTotal} conversations done`}
                    >
                      {badge}
                    </span>
                  )}
                </button>
                {folder.open && filteredFiles.map((file) => {
                  const isProtected = PROTECTED_FILENAMES.has(file.name)
                  return (
                    <WorkspaceItem
                      key={file.path}
                      item={file}
                      itemDir={folder.path}
                      isSelected={selectedItem?.path === file.path}
                      isDirty={dirtyItems.has(file.path)}
                      deep
                      renamingPath={renamingPath}
                      renameValue={renameValue}
                      onSelect={() => onSelect(file)}
                      onRenameChange={onRenameChange}
                      onRenameCommit={() => onRenameCommit(file, folder.path)}
                      onRenameCancel={onRenameCancel}
                      onStartRename={isProtected ? undefined : () => onStartRename(file, folder.path)}
                      onStartDelete={isProtected ? undefined : () => onStartDelete(file)}
                    />
                  )
                })}
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}
