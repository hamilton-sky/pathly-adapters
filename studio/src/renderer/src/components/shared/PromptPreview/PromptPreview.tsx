import { useEffect, useState } from 'react'
import { ChevronRight, ExternalLink, Eye, Pencil } from 'lucide-react'
import MarkdownRenderer from '../MarkdownRenderer/MarkdownRenderer'
import type { CatalogItem } from '../../Monitor/ConfigurePhaseModal/hooks/usePhaseModalCatalog'
import s from './PromptPreview.module.css'

/** Resolve the .md path for a name from the live catalog, falling back to a static map. */
export function findPath(name: string, catalog: CatalogItem[], fallback: Record<string, string>): string | null {
  if (!name) return null
  return catalog.find((i) => i.name === name)?.path ?? fallback[name] ?? null
}

/**
 * Fetch the prompt text for the currently-selected agent/skill — reads the real
 * core/ .md when the project path + catalog resolve it, else falls back to a stub.
 */
export function usePromptContent(
  name: string,
  basePath: string,
  catalog: CatalogItem[],
  fallback: Record<string, string>,
  stubs: Record<string, string>,
  projectPath: string | null,
): string | null {
  const [content, setContent] = useState<string | null>(null)
  useEffect(() => {
    if (!name) { setContent(null); return }
    const rel = findPath(name, catalog, fallback)
    if (rel && projectPath) {
      const full = `${projectPath}/${basePath}/${rel}.md`
      window.pathly.fs.read(full)
        .then((txt: string | null) => setContent(txt ?? stubs[name] ?? null))
        .catch(() => setContent(stubs[name] ?? null))
    } else {
      setContent(stubs[name] ?? null)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name, projectPath])
  return content
}

/**
 * Collapsible prompt preview. Two modes:
 *  - read-only (agent/skill .md files): markdown preview + "Open in Markdown Editor".
 *  - editable (inline system-prompt / lens presets): an eye/pencil toggle that swaps
 *    the markdown preview for a textarea so the user can tweak the prompt for this run.
 *    Editing is controlled — `editValue` / `onEditChange` are owned by the caller.
 */
export function PromptBanner({
  content = null,
  mdEditorPath = null,
  onOpenMdEditor,
  editable = false,
  editValue,
  onEditChange,
}: {
  content?: string | null
  mdEditorPath?: string | null
  onOpenMdEditor?: () => void
  editable?: boolean
  editValue?: string
  onEditChange?: (v: string) => void
}): JSX.Element {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<'preview' | 'edit'>('preview')

  const previewText = editable ? (editValue ?? '') : content

  function show(next: 'preview' | 'edit'): void {
    setMode(next)
    setOpen(true)
  }

  return (
    <div className={s.banner}>
      <div className={s.bannerHeader}>
        <button
          type="button"
          className={s.bannerToggle}
          onClick={() => setOpen((v) => !v)}
          {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
        >
          <ChevronRight size={10} className={open ? s.chevronOpen : undefined} />
          Prompt
        </button>

        {editable ? (
          <div className={s.modeToggle} role="group" aria-label="Preview or edit prompt">
            <button
              type="button"
              className={s.modeBtn}
              {...(open && mode === 'preview' ? { 'data-on': '' } : {})}
              title="Preview"
              aria-label="Preview prompt"
              onClick={() => show('preview')}
            >
              <Eye size={12} />
            </button>
            <button
              type="button"
              className={s.modeBtn}
              {...(open && mode === 'edit' ? { 'data-on': '' } : {})}
              title="Edit"
              aria-label="Edit prompt"
              onClick={() => show('edit')}
            >
              <Pencil size={12} />
            </button>
          </div>
        ) : (
          mdEditorPath && onOpenMdEditor && (
            <button type="button" className={s.mdEditorLink} onClick={onOpenMdEditor}>
              Open in Markdown Editor <ExternalLink size={10} />
            </button>
          )
        )}
      </div>

      {open && (
        <div className={s.bannerBody}>
          {editable && mode === 'edit' ? (
            <textarea
              className={s.editArea}
              value={editValue ?? ''}
              onChange={(e) => onEditChange?.(e.currentTarget.value)}
              onKeyDown={(e) => { if (e.key === 'Escape') setMode('preview') }}
              spellCheck={false}
              placeholder="Edit the prompt for this run…"
              aria-label="Edit prompt text"
            />
          ) : previewText ? (
            <MarkdownRenderer content={previewText} className={s.previewMd} />
          ) : (
            <span className={s.previewEmpty}>No prompt found.</span>
          )}
        </div>
      )}
    </div>
  )
}
