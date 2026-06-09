import { useState } from 'react'
import { Folder, FolderOpen, FolderPlus, Lock, MoreHorizontal, Plus, Trash2 } from 'lucide-react'
import type { PathlyItem } from '../../../types'
import type { PlanFolder } from '../../../hooks/usePlanFiles'
import { IconButton, Tooltip } from '../../ui'
import { SectionHeader } from '../shared/SectionHeader'
import { SubdirRow } from './SubdirRow'
import { WorkspaceItem } from './WorkspaceItem'
import { InlineCreateInput } from '../shared/InlineCreateInput'
import { ContextMenu } from '../shared/ContextMenu'
import { PROTECTED_FILENAMES } from '../constants'
import styles from '../Sidebar.module.css'

interface Props {
  planFolders: PlanFolder[]
  selectedItem: PathlyItem | null
  dirtyItems: Set<string>
  lowerFilter: string
  activeTopic: string | null
  renamingPath: string | null
  renameValue: string
  planOpen: boolean
  inlineCreate: { target: string; parentDir: string; type: 'file' | 'folder' } | null
  onTogglePlan: () => void
  onToggleFolder: (name: string) => void
  onFolderClick: (name: string) => void
  onNewPlan: (e: React.MouseEvent<HTMLButtonElement>) => void
  onCreatePlanFile: (e: React.MouseEvent<HTMLButtonElement>) => void
  onInlineCreateSubmit: (name: string) => void
  onInlineCreateCancel: () => void
  onSelect: (item: PathlyItem) => void
  onRenameChange: (v: string) => void
  onRenameCommit: (item: PathlyItem, itemDir: string) => void
  onRenameCancel: () => void
  onStartRename: (item: PathlyItem, itemDir: string) => void
  onStartDelete: (item: PathlyItem) => void
  onDeletePlanFolder?: (folderPath: string) => void
  onTogglePlanSubdir?: (folderName: string, subdirName: string) => void
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
  inlineCreate,
  onTogglePlan,
  onToggleFolder,
  onFolderClick,
  onNewPlan,
  onCreatePlanFile,
  onInlineCreateSubmit,
  onInlineCreateCancel,
  onSelect,
  onRenameChange,
  onRenameCommit,
  onRenameCancel,
  onStartRename,
  onStartDelete,
  onDeletePlanFolder,
  onTogglePlanSubdir,
}: Props): JSX.Element {
  const [menuOpenFor, setMenuOpenFor] = useState<string | null>(null)
  const [menuAnchor, setMenuAnchor] = useState<DOMRect | null>(null)

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
          <IconButton onClick={onNewPlan} title="New plan folder" data-label="New Plan Folder">
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
          {inlineCreate?.target === 'plan-folder' && (
            <InlineCreateInput
              type="folder"
              dataLabel="New Plan Name"
              onCommit={onInlineCreateSubmit}
              onCancel={onInlineCreateCancel}
            />
          )}
          {visibleFolders.length === 0 && !inlineCreate && (
            <div className={styles.convEmpty}>No plans</div>
          )}
          {visibleFolders.map((folder) => {
            const isActive = folder.name === activeTopic
            const badge = folder.convTotal > 0
              ? `${folder.convDone}/${folder.convTotal}âœ"`
              : null

            const filteredFiles = lowerFilter
              ? folder.files.filter((f) => f.name.toLowerCase().includes(lowerFilter))
              : folder.files

            return (
              <div key={folder.name}>
                <div
                  className={`${styles.subdirHeader} ${isActive ? styles.itemRowSelected : ''}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => {
                    onToggleFolder(folder.name)
                    onFolderClick(folder.name)
                  }}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { onToggleFolder(folder.name); onFolderClick(folder.name) } }}
                >
                  {folder.open
                    ? <FolderOpen size={15} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                    : <Folder size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                  }
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {folder.name}
                  </span>
                  <Tooltip label="Managed by Pathly — cannot be renamed or moved" placement="bottom">
                    <span className={styles.lockIcon}>
                      <Lock size={10} />
                    </span>
                  </Tooltip>
                  {badge && (
                    <Tooltip label={`${folder.convDone} of ${folder.convTotal} conversations done`} placement="bottom">
                      <span
                        className={styles.planBadge}
                        style={{ color: folder.convDone === folder.convTotal ? 'var(--green)' : 'var(--text-muted)' }}
                      >
                        {badge}
                      </span>
                    </Tooltip>
                  )}
                  {onDeletePlanFolder && (
                    <div className={styles.rowActions} onClick={(e) => e.stopPropagation()}>
                      <Tooltip label="Actions" placement="bottom">
                        <button
                          type="button"
                          className={styles.rowAction}
                          aria-label="Actions"
                          onClick={(e) => {
                            e.stopPropagation()
                            const next = menuOpenFor === folder.name ? null : folder.name
                            setMenuOpenFor(next)
                            if (next) setMenuAnchor((e.currentTarget as HTMLButtonElement).getBoundingClientRect())
                          }}
                        >
                          <MoreHorizontal size={15} />
                        </button>
                      </Tooltip>
                      {menuOpenFor === folder.name && menuAnchor && (
                        <ContextMenu
                          anchor={menuAnchor}
                          onClose={() => setMenuOpenFor(null)}
                        >
                          <button
                            className={`${styles.itemMenuItem} ${styles.itemMenuItemDelete}`}
                            onClick={(e) => { e.stopPropagation(); setMenuOpenFor(null); onDeletePlanFolder(folder.path) }}
                          >
                            <Trash2 size={12} />
                            Delete folder
                          </button>
                        </ContextMenu>
                      )}
                    </div>
                  )}
                </div>
                {folder.open && (
                  <>
                    {inlineCreate?.target === 'plan-file' && folder.name === activeTopic && (
                      <InlineCreateInput
                        type="file"
                        deep
                        onCommit={onInlineCreateSubmit}
                        onCancel={onInlineCreateCancel}
                      />
                    )}
                    {filteredFiles.map((file) => {
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
                          sectionId="plan"
                          onSelect={() => onSelect(file)}
                          onRenameChange={onRenameChange}
                          onRenameCommit={() => onRenameCommit(file, folder.path)}
                          onRenameCancel={onRenameCancel}
                          onStartRename={isProtected ? undefined : () => onStartRename(file, folder.path)}
                          onStartDelete={isProtected ? undefined : () => onStartDelete(file)}
                        />
                      )
                    })}
                    {folder.subdirs.map((subdir) => {
                      const subdirPath = `${folder.path}/${subdir.name}`
                      const filteredSdFiles = lowerFilter
                        ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter))
                        : subdir.files
                      if (lowerFilter && filteredSdFiles.length === 0) return null
                      return (
                        <div key={subdir.name}>
                          <SubdirRow
                            name={subdir.name}
                            open={subdir.open}
                            onToggle={() => onTogglePlanSubdir?.(folder.name, subdir.name)}
                          />
                          {subdir.open && filteredSdFiles.map((file) => (
                            <WorkspaceItem
                              key={file.path}
                              item={file}
                              itemDir={subdirPath}
                              isSelected={selectedItem?.path === file.path}
                              isDirty={dirtyItems.has(file.path)}
                              deep
                              renamingPath={renamingPath}
                              renameValue={renameValue}
                              sectionId="plan"
                              onSelect={() => onSelect(file)}
                              onRenameChange={onRenameChange}
                              onRenameCommit={() => onRenameCommit(file, subdirPath)}
                              onRenameCancel={onRenameCancel}
                              onStartRename={() => onStartRename(file, subdirPath)}
                              onStartDelete={() => onStartDelete(file)}
                            />
                          ))}
                        </div>
                      )
                    })}
                  </>
                )}
              </div>
            )
          })}
        </div>
      )}
    </>
  )
}
