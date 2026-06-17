import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { createPortal } from 'react-dom'
import { ChevronRight, ExternalLink } from 'lucide-react'
import MarkdownRenderer from '../../../shared/MarkdownRenderer/MarkdownRenderer'
import CliSelect from '../.././../MarkdownNotebook/NotebookHeader/CliSelect/CliSelect'
import { type NotebookCli } from '../.././../MarkdownNotebook/NotebookHeader/notebookCli'
import {
  AGENTS, SKILLS, SKILL_PROMPTS, SKILL_FILE_PATHS, AGENT_FILE_PATHS,
} from '../../../Monitor/ConfigurePhaseModal/configurePhaseModalData'
import {
  useAgentCatalog, useSkillCatalog, type CatalogItem,
} from '../../../Monitor/ConfigurePhaseModal/hooks/usePhaseModalCatalog'
import { useStore } from '../../../../store'
import { useUiStore } from '../../../../store/uiStore'
import s from './EvalConfigPopover.module.css'

interface Props {
  anchorEl: HTMLElement | null
  selectedAgent: string
  selectedSkill: string
  extraPrompt: string
  selectedCli: NotebookCli
  running: boolean
  onSelectAgent: (a: string) => void
  onSelectSkill: (sk: string) => void
  onExtraPromptChange: (v: string) => void
  onCliChange: (cli: NotebookCli) => void
  onReset: () => void
  onRun: () => void
  onClose: () => void
}

const POPOVER_WIDTH = 290

function findPath(name: string, catalog: CatalogItem[], fallback: Record<string, string>): string | null {
  if (!name) return null
  return catalog.find((i) => i.name === name)?.path ?? fallback[name] ?? null
}

function usePromptContent(
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

function PromptBanner({
  content,
  notebookPath,
  onOpenNotebook,
}: {
  content: string | null
  notebookPath: string | null
  onOpenNotebook: () => void
}): JSX.Element {
  const [open, setOpen] = useState(false)
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
        {notebookPath && (
          <button type="button" className={s.notebookLink} onClick={onOpenNotebook}>
            Open in Notebook <ExternalLink size={10} />
          </button>
        )}
      </div>
      {open && (
        <div className={s.bannerBody}>
          {content
            ? <MarkdownRenderer
                content={content.length > 1200 ? `${content.slice(0, 1200)}\n\n*…truncated*` : content}
                className={s.previewMd}
              />
            : <span className={s.previewEmpty}>No prompt found.</span>}
        </div>
      )}
    </div>
  )
}

export function EvalConfigPopover({
  anchorEl, selectedAgent, selectedSkill, extraPrompt, selectedCli,
  running, onSelectAgent, onSelectSkill, onExtraPromptChange, onCliChange,
  onReset, onRun, onClose,
}: Props): JSX.Element | null {
  const ref = useRef<HTMLDivElement>(null)
  const [top, setTop] = useState(0)
  const [left, setLeft] = useState(0)

  const projectPath = useStore((st) => st.projectPath)
  const setNotebookPath = useUiStore((st) => st.setNotebookPath)
  const setActivePanel = useUiStore((st) => st.setActivePanel)
  const agentCatalog = useAgentCatalog(projectPath)
  const skillCatalog = useSkillCatalog(projectPath)

  const agentOptions = agentCatalog.length ? agentCatalog.map((i) => i.name) : [...AGENTS]
  const skillOptions = skillCatalog.length ? skillCatalog.map((i) => i.name) : [...SKILLS]

  // Fetch prompt text for current selections.
  const agentContent = usePromptContent(
    selectedAgent, 'src/pathly_data/core/agents', agentCatalog, AGENT_FILE_PATHS, {}, projectPath,
  )
  const skillContent = usePromptContent(
    selectedSkill, 'src/pathly_data/core/skills', skillCatalog, SKILL_FILE_PATHS, SKILL_PROMPTS, projectPath,
  )

  // Notebook paths for "Open in Notebook" links.
  const agentNotebookPath = selectedAgent && projectPath
    ? (() => {
      const rel = findPath(selectedAgent, agentCatalog, AGENT_FILE_PATHS)
      return rel ? `${projectPath}/src/pathly_data/core/agents/${rel}.md` : null
    })()
    : null

  const skillNotebookPath = selectedSkill && projectPath
    ? (() => {
      const rel = findPath(selectedSkill, skillCatalog, SKILL_FILE_PATHS)
      return rel ? `${projectPath}/src/pathly_data/core/skills/${rel}.md` : null
    })()
    : null

  function openNotebook(path: string | null): void {
    if (!path) return
    setNotebookPath(path)
    setActivePanel('notebook')
    onClose()
  }

  // Position below the anchor, right-aligned.
  useLayoutEffect(() => {
    if (!anchorEl) return
    const r = anchorEl.getBoundingClientRect()
    let l = r.right - POPOVER_WIDTH
    if (l < 8) l = 8
    if (l + POPOVER_WIDTH > window.innerWidth - 8) l = window.innerWidth - 8 - POPOVER_WIDTH
    setTop(r.bottom + 6)
    setLeft(l)
  }, [anchorEl])

  // Outside-click and Escape close.
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (ref.current && !ref.current.contains(t) && anchorEl && !anchorEl.contains(t)) onClose()
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [anchorEl, onClose])

  return createPortal(
    <div
      ref={ref}
      className={s.popover}
      style={{ '--pop-top': `${top}px`, '--pop-left': `${left}px` } as React.CSSProperties}
      role="dialog"
      aria-label="Configure evaluator"
    >
      <div className={s.heading}>Configure evaluator</div>

      {/* Agent */}
      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="eval-agent">AGENT</label>
        <select
          id="eval-agent"
          className={s.select}
          value={selectedAgent}
          onChange={(e) => onSelectAgent(e.currentTarget.value)}
        >
          <option value="">— default —</option>
          {agentOptions.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        {selectedAgent && (
          <PromptBanner
            content={agentContent}
            notebookPath={agentNotebookPath}
            onOpenNotebook={() => openNotebook(agentNotebookPath)}
          />
        )}
      </section>

      {/* Skill */}
      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="eval-skill">SKILL</label>
        <select
          id="eval-skill"
          className={s.select}
          value={selectedSkill}
          onChange={(e) => onSelectSkill(e.currentTarget.value)}
        >
          <option value="">— default —</option>
          {skillOptions.map((sk) => <option key={sk} value={sk}>{sk}</option>)}
        </select>
        {selectedSkill && (
          <PromptBanner
            content={skillContent}
            notebookPath={skillNotebookPath}
            onOpenNotebook={() => openNotebook(skillNotebookPath)}
          />
        )}
      </section>

      {/* Extra instructions */}
      <section className={s.section}>
        <label className={s.sectionLabel} htmlFor="eval-extra">EXTRA INSTRUCTIONS <span className={s.optional}>· optional</span></label>
        <textarea
          id="eval-extra"
          className={s.textarea}
          rows={3}
          placeholder="Any extra context or instructions for this run…"
          value={extraPrompt}
          onChange={(e) => onExtraPromptChange(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); onRun() }
          }}
        />
      </section>

      {/* Engine */}
      <section className={s.section}>
        <span className={s.sectionLabel}>ENGINE</span>
        <CliSelect value={selectedCli} onChange={onCliChange} align="right" up />
      </section>

      <footer className={s.footer}>
        <button type="button" className={s.resetBtn} onClick={onReset}>Reset</button>
        <span className={s.spacer} />
        <button type="button" className={s.runBtn} disabled={running} onClick={onRun}>
          Run now
        </button>
      </footer>
    </div>,
    document.body,
  )
}
