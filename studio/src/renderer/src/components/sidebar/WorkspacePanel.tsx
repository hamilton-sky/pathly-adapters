import { Plus } from 'lucide-react'
import type { PathlyItem, SectionState, ConvRow } from '../../types'
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
  planConvs: ConvRow[]
  renamingPath: string | null
  renameValue: string
  onSelect: (item: PathlyItem) => void
  onToggleSection: (label: string) => void
  onToggleSubdir: (label: string, idx: number) => void
  onActivePanel: (p: 'plan' | 'editor' | 'flow' | 'monitor' | 'settings') => void
  onWorkspaceCreate: (section: Section, e: React.MouseEvent<HTMLButtonElement>) => void
  onInlineCreate: (section: Section, e: React.MouseEvent<HTMLButtonElement>) => void
  onNewPlan: (e: React.MouseEvent<HTMLButtonElement>) => void
  onRenameChange: (v: string) => void
  onRenameCommit: (item: PathlyItem, itemDir: string) => void
  onRenameCancel: () => void
  onStartRename: (item: PathlyItem, itemDir: string) => void
  onStartDelete: (item: PathlyItem) => void
  planOpen: boolean
  onTogglePlan: () => void
}

export function WorkspacePanel(props: Props): JSX.Element {
  const {
    sections, projectPath, selectedItem, dirtyItems,
    filter, lowerFilter, activeTopic, planConvs,
    renamingPath, renameValue,
    onSelect, onToggleSection, onToggleSubdir, onActivePanel,
    onWorkspaceCreate, onInlineCreate, onNewPlan,
    onRenameChange, onRenameCommit, onRenameCancel,
    onStartRename, onStartDelete,
    planOpen, onTogglePlan,
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
        planConvs={planConvs}
        open={planOpen}
        activeTopic={activeTopic}
        onToggle={onTogglePlan}
        onNewPlan={onNewPlan}
        onActivePanel={onActivePanel}
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
