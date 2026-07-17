import { useEffect, useRef, useState, type ReactNode } from 'react'
import { SendHorizonal, X, Check, Rows3 } from 'lucide-react'
import { PromptBanner } from '../PromptPreview/PromptPreview'
import SkillSplitModal, { cellsToMarkdown } from '../SkillSplitModal/SkillSplitModal'
import type { PromptLayer } from '../../../services/skillCompose'
import styles from './SendPreviewModal.module.css'

export interface SendPreviewMeta {
  label: string
  value: string
}

export interface SendPreviewItem {
  id: string
  label: string
  selected: boolean
  color?: string
}

interface Props {
  /** Modal heading — typically the preset/lens title, mirroring the toolbar button. */
  title: string
  /** Engine the prompt will be dispatched to (already human-readable). */
  engineLabel: string
  /** File the action targets — shown next to the title. */
  fileName: string
  /** The prompt to review — seeds the collapsible banner; the user may edit it. */
  prompt: string
  /** Extra info rows (lens, …). Engine is prepended automatically. */
  meta?: SendPreviewMeta[]
  /** Optional selectable items (e.g. comments) — each can be toggled in/out of the send. */
  items?: SendPreviewItem[]
  /** Label above the items list. */
  itemsLabel?: string
  /** Toggle an item's inclusion. */
  onToggleItem?: (id: string) => void
  /** Primary button label, e.g. "Run Split" / "Send to Claude". */
  submitLabel?: string
  /** Render the prompt as a read-only preview (no edit toggle). Use when the final prompt
   *  is assembled elsewhere (e.g. server-side) and the modal is a confirm-and-preview gate. */
  readOnly?: boolean
  /** Heading → prompt layer, for the Sections editor's tabs/colours + the platform LOCK
   *  (Pathly's fragments are visible but never uncheckable — dropping one breaks the run). */
  headingLayers?: Record<string, PromptLayer>
  /** Optional controls rendered in the footer, left of the buttons (e.g. a per-run progress selector). */
  footerSlot?: ReactNode
  /** Receives the (possibly edited) prompt — that exact text is what gets sent. `sectionsUsed`
   *  is true only when the user actually confirmed a Sections cell-config: server-composed
   *  gates must ONLY send a prompt_override in that case, never on a plain submit. */
  onSubmit: (prompt: string, sectionsUsed?: boolean) => void
  onCancel: () => void
}

// Confirm-before-send: a compact gate showing the target engine + summary, an optional
// per-item selection list (comments), and the prompt in a collapsible banner (eye = preview ·
// pencil = edit). Whatever the banner holds on submit is the exact text dispatched.
export default function SendPreviewModal({ title, engineLabel, fileName, prompt, meta = [], items, itemsLabel = 'Include', onToggleItem, submitLabel = 'Send', readOnly = false, headingLayers, footerSlot, onSubmit, onCancel }: Props) {
  const submitRef = useRef<HTMLButtonElement>(null)
  const [text, setText] = useState(prompt)
  const [splitOpen, setSplitOpen] = useState(false)
  // True once the user CONFIRMS a Sections config. Server-composed gates key their
  // prompt_override off this — a plain submit must leave composition to the server.
  const [sectionsUsed, setSectionsUsed] = useState(false)

  // Re-seed the editable text whenever the incoming prompt changes — e.g. when toggling
  // which comments are included rebuilds it. For Split/Analyze the prompt is stable, so a
  // manual edit is never clobbered.
  useEffect(() => { setText(prompt) }, [prompt])

  useEffect(() => {
    submitRef.current?.focus()
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        const ae = document.activeElement
        if (ae && (ae.tagName === 'TEXTAREA' || ae.tagName === 'INPUT')) return
        e.preventDefault()
        onCancel()
      } else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        onSubmit(text, sectionsUsed)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onCancel, onSubmit, text])

  const rows: SendPreviewMeta[] = [{ label: 'Engine', value: engineLabel }, ...meta]
  const noneSelected = !!items && items.length > 0 && items.every((i) => !i.selected)

  return (
    <>
    <div className={styles.backdrop} onClick={onCancel}>
      <div
        className={styles.modal}
        role="dialog"
        aria-modal="true"
        aria-labelledby="send-preview-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={styles.header}>
          <div className={styles.titleWrap}>
            <span id="send-preview-title" className={styles.title}>{title}</span>
            <span className={styles.fileName}>{fileName}</span>
          </div>
          <button type="button" className={styles.closeBtn} onClick={onCancel} aria-label="Cancel">
            <X size={15} />
          </button>
        </div>

        <div className={styles.metaRow}>
          {rows.map((r) => (
            <span key={r.label} className={styles.metaItem}>
              <span className={styles.metaLabel}>{r.label}</span>
              <span className={styles.metaValue}>{r.value}</span>
            </span>
          ))}
        </div>

        {items && items.length > 0 && (
          <div className={styles.itemsSection}>
            <div className={styles.itemsLabel}>
              {itemsLabel} <span className={styles.itemsCount}>{items.filter((i) => i.selected).length}/{items.length}</span>
            </div>
            <div className={styles.itemsList}>
              {items.map((it) => (
                <button
                  key={it.id}
                  type="button"
                  className={styles.item}
                  data-selected={it.selected ? 'true' : 'false'}
                  onClick={() => onToggleItem?.(it.id)}
                  {...(it.selected ? { 'aria-pressed': 'true' } : { 'aria-pressed': 'false' })}
                >
                  <span className={styles.checkbox}>{it.selected && <Check size={11} />}</span>
                  {it.color && <span className={styles.itemDot} data-color={it.color} />}
                  <span className={styles.itemText}>{it.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className={styles.bannerWrap}>
          {readOnly
            ? <PromptBanner content={text} />
            : <PromptBanner editable editValue={text} onEditChange={setText} />}
        </div>

        {footerSlot && <div className={styles.footerSlot}>{footerSlot}</div>}

        <div className={styles.footer}>
          <button type="button" className={styles.cancelBtn} onClick={() => setSplitOpen(true)} title="Include or exclude prompt sections for this run">
            <Rows3 size={13} /> Sections
          </button>
          <button type="button" className={styles.cancelBtn} onClick={onCancel}>Cancel</button>
          <button
            ref={submitRef}
            type="button"
            className={styles.submitBtn}
            disabled={noneSelected}
            onClick={() => onSubmit(text, sectionsUsed)}
          >
            <SendHorizonal size={14} />
            {submitLabel}
          </button>
        </div>
      </div>
    </div>
      {splitOpen && (
        <SkillSplitModal
          rawContent={text}
          title="Configure prompt sections"
          subtitle="Include or exclude sections for this run — used once. Save reusable prompts in the library instead."
          confirmLabel="Use these sections"
          hideInsertOne
          headingLayers={headingLayers}
          onConfirm={(cells) => { setText(cellsToMarkdown(cells)); setSectionsUsed(true); setSplitOpen(false) }}
          onInsertOne={() => setSplitOpen(false)}
          onClose={() => setSplitOpen(false)}
        />
      )}
    </>
  )
}
