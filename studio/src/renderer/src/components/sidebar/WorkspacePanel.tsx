import { Plus, FolderPlus } from 'lucide-react'
import type { PathlyItem, SectionState } from '../../types'
import type { PlanFolder } from '../../hooks/usePlanFiles'
import { IconButton, Separator } from '../ui'
import { SectionHeader } from './SectionHeader'
import { SubdirRow } from './SubdirRow'
import { WorkspaceItem } from './WorkspaceItem'
import { PlanSection } from './PlanSection'
import { WORKSPACE_USER_SECTIONS, WORKSPACE_FILE_SECTIONS } from './constants'
import type { Section } from './types'
import styles from './Sidebar.module.css'

interface Props {
  sections: Record<string, SectionState>
  projectPath: string
  selectedItem: PathlyItem | null
  dirtyItems: Set<string>
  filter: string
  lowerFilter: string
  activeTopic: string | null
  planFolders: PlanFolder[]
  renamingPath: string | null
  renameValue: string
  onSelect: (item: PathlyItem) => void
  onToggleSection: (label: string) => void
  onToggleSubdir: (label: string, idx: number) => void
  onActivePanel: (p: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings') => void
  onWorkspaceCreate: (section: Section, e: React.MouseEvent<HTMLButtonElement>) => void
  onInlineCreate: (section: Section, e: React.MouseEvent<HTMLButtonElement>) => void
  onInlineCreateFolder: (section: Section, e: React.MouseEvent<HTMLButtonElement>) => void
  onNewPlan: (e: React.MouseEvent<HTMLButtonElement>) => void
  onRenameChange: (v: string) => void
  onRenameCommit: (item: PathlyItem, itemDir: string) => void
  onRenameCancel: () => void
  onStartRename: (item: PathlyItem, itemDir: string) => void
  onStartDelete: (item: PathlyItem) => void
  planOpen: boolean
  onTogglePlan: () => void
  onToggleFolder: (name: string) => void
  onFolderClick: (name: string) => void
}

export function WorkspacePanel(props: Props): JSX.Element {
  const {
    sections, projectPath, selectedItem, dirtyItems,
    filter, lowerFilter, activeTopic, planFolders,
    renamingPath, renameValue,
    onSelect, onToggleSection, onToggleSubdir, onActivePanel,
    onWorkspaceCreate, onInlineCreate, onInlineCreateFolder, onNewPlan,
    onRenameChange, onRenameCommit, onRenameCancel,
    onStartRename, onStartDelete,
    planOpen, onTogglePlan, onToggleFolder, onFolderClick,
  } = props

  return (
    <>
      <Separator label="Workspace" />

      {WORKSPACE_USER_SECTIONS.map((section) => {
        const state = sections[section.label]
        if (!state) return null
        const subdirs = state.subdirs ?? []
        const filteredItems = filter ? state.items.filter((item) => item.name.toLowerCase().includes(lowerFilter)) : state.items
        const hasSubdirMatch = filter ? subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter))) : true
        if (filter && filteredItems.length === 0 && !hasSubdirMatch) return null
        return (
          <div key={section.label}>
            <SectionHeader
              label={section.label}
              open={state.open}
              onToggle={() => onToggleSection(section.label)}
              actionsLeft={
                <IconButton
                  onClick={(e) => onInlineCreateFolder(section, e)}
                  title="New folder"
                >
                  <FolderPlus size={12} />
                </IconButton>
              }
              actions={
                <IconButton
                  onClick={(e) => onWorkspaceCreate(section, e)}
                  title={`New ${section.label.toLowerCase()}`}
                >
                  <Plus size={12} />
                </IconButton>
              }
            />
            {state.open && (
              <div>
                {subdirs.map((subdir, idx) => {
                  const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                  if (filter && filteredFiles.length === 0) return null
                  const itemDir = `${projectPath}/${section.dir}/${subdir.name}`
                  return (
                    <div key={subdir.name}>
                      <SubdirRow
                        name={subdir.name}
                        open={subdir.open}
                        onToggle={() => onToggleSubdir(section.label, idx)}
                      />
                      {filteredFiles.map((item) => (
                        <WorkspaceItem
                          key={item.path}
                          item={item}
                          itemDir={itemDir}
                          isSelected={selectedItem?.path === item.path}
                          isDirty={dirtyItems.has(item.path)}
                          deep
                          renamingPath={renamingPath}
                          renameValue={renameValue}
                          onSelect={() => onSelect(item)}
                          onRenameChange={onRenameChange}
                          onRenameCommit={() => onRenameCommit(item, itemDir)}
                          onRenameCancel={onRenameCancel}
                          onStartRename={() => onStartRename(item, itemDir)}
                          onStartDelete={() => onStartDelete(item)}
                        />
                      ))}
                    </div>
                  )
                })}
                {filteredItems.map((item) => {
                  const itemDir = `${projectPath}/${section.dir}`
                  return (
                    <WorkspaceItem
                      key={item.path}
                      item={item}
                      itemDir={itemDir}
                      isSelected={selectedItem?.path === item.path}
                      isDirty={dirtyItems.has(item.path)}
                      renamingPath={renamingPath}
                      renameValue={renameValue}
                      onSelect={() => onSelect(item)}
                      onRenameChange={onRenameChange}
                      onRenameCommit={() => onRenameCommit(item, itemDir)}
                      onRenameCancel={onRenameCancel}
                      onStartRename={() => onStartRename(item, itemDir)}
                      onStartDelete={() => onStartDelete(item)}
                    />
                  )
                })}
              </div>
            )}
          </div>
        )
      })}

      <PlanSection
        planFolders={planFolders}
        selectedItem={selectedItem}
        dirtyItems={dirtyItems}
        lowerFilter={lowerFilter}
        activeTopic={activeTopic}
        renamingPath={renamingPath}
        renameValue={renameValue}
        planOpen={planOpen}
        onTogglePlan={onTogglePlan}
        onToggleFolder={onToggleFolder}
        onFolderClick={onFolderClick}
        onNewPlan={onNewPlan}
        onSelect={onSelect}
        onRenameChange={onRenameChange}
        onRenameCommit={onRenameCommit}
        onRenameCancel={onRenameCancel}
        onStartRename={onStartRename}
        onStartDelete={onStartDelete}
      />

      {WORKSPACE_FILE_SECTIONS.map((section) => {
        const state = sections[section.label]
        if (!state) return null
        if (state.subdirs === null) return null
        const subdirs = state.subdirs ?? []
        const hasMatch = !filter || subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter)))
        if (!hasMatch) return null
        return (
          <div key={section.label}>
            <SectionHeader
              label={section.label}
              open={state.open}
              onToggle={() => onToggleSection(section.label)}
              actionsLeft={
                <IconButton
                  onClick={(e) => onInlineCreateFolder(section, e)}
                  title="New folder"
                >
                  <FolderPlus size={12} />
                </IconButton>
              }
              actions={
                <IconButton
                  onClick={(e) => onInlineCreate(section, e)}
                  title={`New ${section.label.slice(0, -1).toLowerCase()}`}
                >
                  <Plus size={12} />
                </IconButton>
              }
            />
            {state.open && (
              <div>
                {subdirs.map((subdir, idx) => {
                  const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
                  if (filter && filteredFiles.length === 0) return null
                  const itemDir = `${projectPath}/${section.dir}/${subdir.name}`
                  return (
                    <div key={subdir.name}>
                      <SubdirRow
                        name={subdir.name}
                        open={subdir.open}
                        onToggle={() => onToggleSubdir(section.label, idx)}
                      />
                      {subdir.open && filteredFiles.map((item) => {
                        const isDirty = dirtyItems.has(item.path)
                        const isSelected = selectedItem?.path === item.path
                        return (
                          <button
                            key={item.path}
                            className={`${styles.itemRow} ${styles.itemRowDeep} ${isSelected ? styles.itemRowSelected : ''}`}
                            onClick={() => onSelect(item)}
                            title={item.path}
                          >
                            <span className={styles.itemName}>{item.name}</span>
                            {isDirty && <span className={styles.dirtyDot}>●</span>}
                          </button>
                        )
                      })}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </>
  )
}
