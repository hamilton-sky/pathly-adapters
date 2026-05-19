import { BookOpen, Plus } from 'lucide-react'
import type { PathlyItem, SectionState } from '../../types'
import { IconButton } from '../ui'
import { SectionHeader } from './SectionHeader'
import { SubdirRow } from './SubdirRow'
import { LibraryItem } from './LibraryItem'
import { PATHLY_SECTIONS, USER_LIBRARY_SECTIONS, USER_LIBRARY_DISPLAY_LABELS } from './constants'
import type { Section } from './types'
import styles from './Sidebar.module.css'

interface Props {
  sections: Record<string, SectionState>
  selectedItem: PathlyItem | null
  filter: string
  lowerFilter: string
  onSelect: (item: PathlyItem) => void
  onToggleSection: (label: string) => void
  onToggleSubdir: (label: string, idx: number) => void
  onNewUserLibraryItem: (section: Section, e: React.MouseEvent<HTMLButtonElement>) => void
  dragFromGripRef: React.MutableRefObject<boolean>
  onDragStart: (e: React.DragEvent, item: PathlyItem, section: Section) => void
}

function renderSection(
  section: Section,
  stateKey: string,
  displayLabel: string,
  state: SectionState,
  props: Props,
  showAddButton: boolean,
): JSX.Element | null {
  const { filter, lowerFilter, selectedItem, onToggleSection, onToggleSubdir, onSelect, onDragStart, onNewUserLibraryItem, dragFromGripRef } = props

  if (section.type === 'template') {
    if (state.subdirs === null) return null
    const subdirs = state.subdirs ?? []
    const hasMatch = !filter || subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter)))
    if (!hasMatch) return null
    return (
      <div key={stateKey}>
        <SectionHeader
          label={displayLabel}
          open={state.open}
          onToggle={() => onToggleSection(stateKey)}
          actions={showAddButton ? (
            <IconButton onClick={(e) => onNewUserLibraryItem(section, e)} title={`New ${displayLabel.slice(0, -1).toLowerCase()}`}>
              <Plus size={12} />
            </IconButton>
          ) : undefined}
        />
        {state.open && (
          <div>
            {subdirs.map((subdir, idx) => {
              const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
              if (filter && filteredFiles.length === 0) return null
              return (
                <div key={subdir.name}>
                  <SubdirRow
                    name={subdir.name}
                    open={subdir.open}
                    onToggle={() => onToggleSubdir(stateKey, idx)}
                  />
                  {subdir.open && filteredFiles.map((item) => (
                    <LibraryItem
                      key={item.path}
                      item={item}
                      isSelected={selectedItem?.path === item.path}
                      isCanvasDraggable={false}
                      deep
                      onSelect={() => onSelect(item)}
                    />
                  ))}
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  const subdirs = state.subdirs ?? []
  const filtered = filter ? state.items.filter((item) => item.name.toLowerCase().includes(lowerFilter)) : state.items
  const hasSubdirMatch = filter ? subdirs.some((sd) => sd.files.some((f) => f.name.toLowerCase().includes(lowerFilter))) : true
  if (filter && filtered.length === 0 && !hasSubdirMatch) return null

  const isCanvasDraggable = section.type === 'skill' || section.type === 'agent'

  return (
    <div key={stateKey}>
      <SectionHeader
        label={displayLabel}
        open={state.open}
        onToggle={() => onToggleSection(stateKey)}
        actions={showAddButton ? (
          <IconButton onClick={(e) => onNewUserLibraryItem(section, e)} title={`New ${displayLabel.slice(0, -1).toLowerCase()}`}>
            <Plus size={12} />
          </IconButton>
        ) : undefined}
      />
      {state.open && (
        <div>
          {subdirs.map((subdir, idx) => {
            const filteredFiles = filter ? subdir.files.filter((f) => f.name.toLowerCase().includes(lowerFilter)) : subdir.files
            if (filter && filteredFiles.length === 0) return null
            return (
              <div key={subdir.name}>
                <SubdirRow
                  name={subdir.name}
                  open={subdir.open}
                  onToggle={() => onToggleSubdir(stateKey, idx)}
                />
                {subdir.open && filteredFiles.map((item) => (
                  <LibraryItem
                    key={item.path}
                    item={item}
                    isSelected={selectedItem?.path === item.path}
                    isCanvasDraggable={isCanvasDraggable}
                    deep
                    onSelect={() => onSelect(item)}
                    onDragStart={isCanvasDraggable ? (e) => {
                      dragFromGripRef.current = true
                      onDragStart(e, item, section)
                    } : undefined}
                    onGripPointerDown={isCanvasDraggable ? () => { dragFromGripRef.current = true } : undefined}
                  />
                ))}
              </div>
            )
          })}
          {filtered.map((item) => (
            <LibraryItem
              key={item.path}
              item={item}
              isSelected={selectedItem?.path === item.path}
              isCanvasDraggable={isCanvasDraggable}
              deep={false}
              onSelect={() => onSelect(item)}
              onDragStart={isCanvasDraggable ? (e) => {
                dragFromGripRef.current = true
                onDragStart(e, item, section)
              } : undefined}
              onGripPointerDown={isCanvasDraggable ? () => { dragFromGripRef.current = true } : undefined}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function LibraryPanel(props: Props): JSX.Element {
  const { sections } = props
  return (
    <>
      <div className={styles.libraryHeader}><BookOpen size={12} />Library</div>
      {PATHLY_SECTIONS.map((section) => {
        const state = sections[section.label]
        if (!state) return null
        return renderSection(section, section.label, section.label, state, props, false)
      })}

      <div className={styles.libraryHeader} style={{ marginTop: 8 }}>MY LIBRARY</div>
      {USER_LIBRARY_SECTIONS.map((section) => {
        const stateKey = section.label
        const displayLabel = USER_LIBRARY_DISPLAY_LABELS[stateKey] ?? stateKey
        const state = sections[stateKey]
        if (!state) return null
        return renderSection(section, stateKey, displayLabel, state, props, true)
      })}
    </>
  )
}
