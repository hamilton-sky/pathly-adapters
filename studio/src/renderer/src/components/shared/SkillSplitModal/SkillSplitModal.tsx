import React, { useState, useEffect, useMemo } from 'react'
import { ChevronUp, ChevronDown, ExternalLink } from 'lucide-react'
import { Tooltip } from '../../ui'
import MarkdownRenderer from '../MarkdownRenderer/MarkdownRenderer'
import type { PromptLayer } from '../../../services/skillCompose'
import { useStore } from '../../../store'
import { useUiStore } from '../../../store/uiStore'
import { useLibraryCells } from './useLibraryCells'
import { PromptCostMeter } from '../PromptCostMeter/PromptCostMeter'
import { estimateInputCost, estimateTokens, type PriceCtx } from '../PromptCostMeter/promptCost'
import styles from './SkillSplitModal.module.css'

export interface ProposedCell {
  id: string
  type: 'heading' | 'markdown'
  heading: string
  content: string
  checked: boolean
  /** Set on library cells (abilities/system-prompts) added from the two tables — their layer
   *  isn't in headingLayers. `path` (abilities only) backs the open-in-MD-editor button. */
  layer?: PromptLayer
  path?: string
}

/** Serialize the (checked, possibly-reordered) cells back into a markdown prompt — the
 *  inverse of parseMdToCells, used by the run gate's "use once" section config. */
export function cellsToMarkdown(cells: ProposedCell[]): string {
  return cells
    .map((c) => {
      const h = c.type === 'heading' ? `# ${c.heading}` : c.heading ? `## ${c.heading}` : ''
      return [h, c.content].filter(Boolean).join('\n\n')
    })
    .join('\n\n')
    .trim()
}

/** Seed cells as UNCHECKED for the given headings — lets a caller reopen the section picker
 *  reflecting a previously-saved exclusion set. No-op when unset (byte-identical for the gates). */
function seedUnchecked(cells: ProposedCell[], unchecked?: string[]): ProposedCell[] {
  if (!unchecked || unchecked.length === 0) return cells
  const set = new Set(unchecked)
  return cells.map((c) => (set.has(c.heading) ? { ...c, checked: false } : c))
}

interface Props {
  filePath?: string
  fileName?: string
  rawContent?: string
  /** Override the editor-flavored heading (e.g. the run-gate "configure sections" use). */
  title?: string
  subtitle?: string
  /** Primary button label. Defaults to "Confirm split — N cells". */
  confirmLabel?: string
  /** Hide the "Insert as one cell" secondary action (not meaningful outside the editor). */
  hideInsertOne?: boolean
  /** Heading → prompt LAYER ('skill' | 'ability' | 'fragment'). Drives the layer tabs, the
   *  per-layer colour, and the LOCK: 'fragment' cells are Pathly's platform layer — always
   *  included, never uncheckable (dropping one silently breaks the run: no AGENT_DONE →
   *  vanishes + unbilled; no comms-post → stops posting to the board). */
  headingLayers?: Record<string, PromptLayer>
  /** Headings to start UNCHECKED (excluded) — reflects a saved per-stage section selection. */
  initialUnchecked?: string[]
  /** Assemble mode: also list the ability + system-prompt tables as ADDABLE cells (checked ⇒
   *  folded into the sent prompt), with open-in-MD-editor. The Sections gate passes this; the
   *  editor's plain split does not (→ byte-identical). Creation stays in the Library. */
  assemble?: boolean
  /** When set (run/flow gate), show an input token+cost meter in the footer for the
   *  currently-assembled prompt, priced at this engine/role's model. Omitted elsewhere → no meter. */
  costCtx?: PriceCtx
  onConfirm: (cells: ProposedCell[]) => void
  onInsertOne: (rawContent: string) => void
  onClose: () => void
}

function parseMdToCells(raw: string, depth: 1 | 2 | 3 = 2): ProposedCell[] {
  const lines = raw.split('\n')
  const cells: ProposedCell[] = []
  let currentType: 'heading' | 'markdown' = 'markdown'
  let currentHeading = ''
  let currentLines: string[] = []

  function flush(idx: number) {
    const content = currentLines.join('\n').trim()
    if (currentHeading || content) {
      cells.push({ id: String(idx), type: currentType, heading: currentHeading, content, checked: true })
    }
  }

  let cellIndex = 0
  for (const line of lines) {
    if (line.startsWith('# ') && !line.startsWith('## ')) {
      flush(cellIndex++)
      currentType = 'heading'
      currentHeading = line.slice(2).trim()
      currentLines = []
    } else if (depth >= 2 && line.startsWith('## ') && !line.startsWith('### ')) {
      flush(cellIndex++)
      currentType = 'markdown'
      currentHeading = line.slice(3).trim()
      currentLines = []
    } else if (depth >= 3 && line.startsWith('### ')) {
      flush(cellIndex++)
      currentType = 'markdown'
      currentHeading = line.slice(4).trim()
      currentLines = []
    } else {
      currentLines.push(line)
    }
  }
  flush(cellIndex)
  return cells
}

export default function SkillSplitModal({ filePath, fileName, rawContent: rawContentProp, title, subtitle, confirmLabel, hideInsertOne, headingLayers, initialUnchecked, assemble, costCtx, onConfirm, onInsertOne, onClose }: Props) {
  const [rawContent, setRawContent] = useState(rawContentProp ?? '')
  const [cells, setCells] = useState<ProposedCell[]>(() => rawContentProp ? seedUnchecked(parseMdToCells(rawContentProp, 2), initialUnchecked) : [])
  const [splitDepth, setSplitDepth] = useState<1 | 2 | 3>(2)

  useEffect(() => {
    if (rawContentProp !== undefined) {
      setRawContent(rawContentProp)
      setCells(seedUnchecked(parseMdToCells(rawContentProp, splitDepth), initialUnchecked))
    } else if (filePath) {
      window.pathly.fs.read(filePath).then((content) => {
        setRawContent(content ?? '')
        setCells(seedUnchecked(parseMdToCells(content ?? '', splitDepth), initialUnchecked))
      }).catch(() => {})
    }
  }, [filePath, rawContentProp, initialUnchecked])

  useEffect(() => {
    setCells(seedUnchecked(parseMdToCells(rawContent, splitDepth), initialUnchecked))
  }, [splitDepth, rawContent, initialUnchecked])

  // Layer-3 abilities + system-prompts a user can ADD to this run — the Sections modal is the
  // ONE assemble surface (opt-in via `assemble`; the editor's plain split passes nothing →
  // byte-identical). Checked ⇒ folded into the sent prompt. Creation stays in the Library.
  const [libraryCells, toggleLibraryCell] = useLibraryCells(!!assemble)
  const allCells = assemble ? [...cells, ...libraryCells] : cells
  const setMdEditorPath = useUiStore((st) => st.setMdEditorPath)
  const setActivePanel = useStore((st) => st.setActivePanel)

  // Every cell belongs to a layer. Pathly's platform fragments (comms-post / completion-report /
  // progress-logging …) are LOCKED — they make the agent report back, so they always count as
  // included whatever the checkbox says. Library cells carry their own `layer`.
  const layerOf = (c: ProposedCell): PromptLayer => c.layer ?? headingLayers?.[c.heading] ?? 'skill'
  const isLocked = (c: ProposedCell): boolean => layerOf(c) === 'fragment'

  const checkedCount = allCells.filter(c => c.checked || isLocked(c)).length
  const checkedCells = allCells.filter(c => c.checked || isLocked(c))

  // Input token+cost estimate of the currently-assembled prompt — gate use only (needs a pricing
  // context). Recomputed as cells toggle so the meter tracks include/exclude live.
  const showCost = !!(assemble && costCtx)
  const assembledPrompt = showCost ? cellsToMarkdown(checkedCells) : ''

  // Layer tabs FILTER the view only — checked state (and the confirm) always spans every cell,
  // so switching tabs can never silently drop a section.
  const [tab, setTab] = useState<'all' | PromptLayer>('all')
  const layerCounts = useMemo(() => {
    const n = { skill: 0, ability: 0, fragment: 0, system: 0 }
    for (const c of allCells) n[c.layer ?? headingLayers?.[c.heading] ?? 'skill'] += 1
    return n
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cells, libraryCells, headingLayers])
  const visibleCells = tab === 'all' ? allCells : allCells.filter(c => layerOf(c) === tab)

  function openInEditor(path: string) {
    setMdEditorPath(path)
    setActivePanel('markdown-editor')
    onClose()
  }

  function toggleCell(id: string) {
    if (id.startsWith('lib-')) { toggleLibraryCell(id); return }
    setCells(prev => prev.map(c => (c.id === id && !isLocked(c) ? { ...c, checked: !c.checked } : c)))
  }

  function moveUp(id: string) {
    setCells(prev => {
      const idx = prev.findIndex(c => c.id === id)
      if (idx <= 0) return prev
      const next = [...prev]
      ;[next[idx - 1], next[idx]] = [next[idx], next[idx - 1]]
      return next
    })
  }

  function moveDown(id: string) {
    setCells(prev => {
      const idx = prev.findIndex(c => c.id === id)
      if (idx < 0 || idx >= prev.length - 1) return prev
      const next = [...prev]
      ;[next[idx], next[idx + 1]] = [next[idx + 1], next[idx]]
      return next
    })
  }

  const modalTitle = title ?? (fileName ? 'Add markdown as cells' : 'Split into cells')
  const modalSubtitle =
    subtitle ??
    (fileName
      ? `Dropped ${fileName} — here's how Pathly will split it. Confirm, or insert as a single cell.`
      : "Here's how Pathly will split this cell. Confirm, or insert as a single cell.")

  return (
    <div className={styles.backdrop} onClick={onClose} tabIndex={-1}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>{modalTitle}</div>
          <div className={styles.modalSubtitle}>{modalSubtitle}</div>
          <div className={styles.depthRow}>
            <span className={styles.depthLabel}>Split on:</span>
            {([1, 2, 3] as const).map(d => (
              <button
                key={d}
                type="button"
                className={styles.depthBtn}
                data-active={splitDepth === d}
                onClick={() => setSplitDepth(d)}
              >
                {'#'.repeat(d)} H{d}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.body}>
          {/* LEFT â€" proposed cells list */}
          <div className={styles.cellsPanel}>
            <div className={styles.panelHeader}>
              <div className={styles.panelTitle}>PROPOSED CELLS</div>
              <span className={styles.cellCountBadge}>{checkedCount} CELLS</span>
            </div>
            {(headingLayers || assemble) && (
              <div className={styles.layerTabs} role="tablist" aria-label="Prompt layer">
                {([
                  ['all', 'All', allCells.length],
                  ['skill', 'Skill', layerCounts.skill],
                  ['ability', 'Abilities', layerCounts.ability],
                  ['system', 'System', layerCounts.system],
                  ['fragment', '🔒 Pathly', layerCounts.fragment],
                ] as const).map(([key, label, n]) => (
                  <button
                    key={key}
                    type="button"
                    role="tab"
                    className={styles.layerTab}
                    data-layer={key}
                    data-active={tab === key ? 'true' : 'false'}
                    {...(tab === key ? { 'aria-selected': 'true' } : { 'aria-selected': 'false' })}
                    onClick={() => setTab(key)}
                  >
                    {label} <span className={styles.layerTabCount}>{n}</span>
                  </button>
                ))}
              </div>
            )}
            <div className={styles.cellsList}>
              {visibleCells.map((cell) => {
                // Reorder acts on the FULL list, so resolve the real index even when filtered.
                const idx = cells.findIndex((c) => c.id === cell.id)
                return (
                <div
                  key={cell.id}
                  className={`${styles.cellCard} ${cell.type === 'heading' ? styles.cellCardHeading : styles.cellCardBody}${!cell.checked && !isLocked(cell) ? ` ${styles.cellCardUnchecked}` : ''}`}
                  data-layer={layerOf(cell)}
                  onClick={() => toggleCell(cell.id)}
                >
                  <div className={styles.strip}>
                    <input
                      type="checkbox"
                      className={styles.cellCheck}
                      aria-label={isLocked(cell)
                        ? `${cell.heading} — required by Pathly, always included`
                        : `Include ${cell.type} cell`}
                      checked={cell.checked || isLocked(cell)}
                      disabled={isLocked(cell)}
                      onChange={() => toggleCell(cell.id)}
                      onClick={e => e.stopPropagation()}
                    />
                    <span
                      className={styles.typeBadge}
                      data-layer={layerOf(cell)}
                      title={
                        isLocked(cell)
                          ? 'Pathly platform fragment — always sent, cannot be removed'
                          : layerOf(cell) === 'ability'
                            ? 'Layer-3 ability — your approach pack'
                            : layerOf(cell) === 'system'
                              ? 'System-prompt from the library'
                              : undefined
                      }
                    >
                      {isLocked(cell)
                        ? '🔒 PATHLY'
                        : layerOf(cell) === 'ability'
                          ? 'ABILITY'
                          : layerOf(cell) === 'system'
                            ? 'SYSTEM'
                            : cell.type === 'heading'
                              ? 'HEADING'
                              : 'BODY'}
                    </span>
                    <span className={styles.stripDiv} />
                    {cell.id.startsWith('lib-') ? (
                      cell.path && (
                        <Tooltip label="Open in Markdown Editor" placement="top">
                          <button
                            type="button"
                            className={styles.moveBtn}
                            aria-label="Open in Markdown Editor"
                            onClick={e => { e.stopPropagation(); openInEditor(cell.path as string) }}
                          >
                            <ExternalLink size={13} />
                          </button>
                        </Tooltip>
                      )
                    ) : (
                      <>
                        <Tooltip label="Move up" placement="top">
                          <button
                            type="button"
                            className={styles.moveBtn}
                            aria-label="Move up"
                            disabled={idx === 0}
                            onClick={e => { e.stopPropagation(); moveUp(cell.id) }}
                          >
                            <ChevronUp size={14} />
                          </button>
                        </Tooltip>
                        <Tooltip label="Move down" placement="top">
                          <button
                            type="button"
                            className={styles.moveBtn}
                            aria-label="Move down"
                            disabled={idx === cells.length - 1}
                            onClick={e => { e.stopPropagation(); moveDown(cell.id) }}
                          >
                            <ChevronDown size={14} />
                          </button>
                        </Tooltip>
                      </>
                    )}
                  </div>
                  {cell.heading && <div className={styles.cellTitle}>{cell.heading}</div>}
                  {cell.content && (
                    <div className={styles.cellPreview}>{cell.content.split('\n')[0]}</div>
                  )}
                </div>
                )
              })}
            </div>
          </div>

          {/* RIGHT â€" live preview */}
          <div className={styles.previewPanel}>
            <div className={styles.panelTitle}>PREVIEW</div>
            <div className={styles.previewBody}>
              {checkedCells.length === 0 ? (
                <div className={styles.previewEmpty}>No cells selected</div>
              ) : (
                checkedCells.map(cell => (
                  <div key={cell.id} className={styles.previewSection}>
                    <div className={styles.previewSectionHeading}>{cell.heading.toUpperCase()}</div>
                    {cell.content && <MarkdownRenderer content={cell.content} />}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        <div className={styles.footer}>
          {showCost && (
            <PromptCostMeter
              tokens={estimateTokens(assembledPrompt)}
              cost={estimateInputCost(assembledPrompt, costCtx)}
            />
          )}
          {!hideInsertOne && (
            <button type="button" className={styles.btnSecondary} onClick={() => onInsertOne(rawContent)}>
              Insert as one cell
            </button>
          )}
          <button type="button" className={styles.btnCancel} onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className={styles.btnPrimary}
            disabled={checkedCount === 0}
            onClick={() => onConfirm(checkedCells)}
          >
            {confirmLabel ?? `Confirm split — ${checkedCount} cells`}
          </button>
        </div>
      </div>
    </div>
  )
}
