import { useState } from 'react'
import { createPortal } from 'react-dom'
import { X, Settings, BookOpen, Check } from 'lucide-react'
import { StatePill } from '../../ui/StatePill/StatePill'
import styles from './ConfigurePhaseModal.module.css'

const CLI_HOSTS = ['Claude Code', 'Codex', 'Copilot', 'Antigravity'] as const
const AGENTS = ['planner', 'builder', 'reviewer', 'tester', 'retro'] as const
const SKILLS = ['plan/storm', 'plan/scope', 'fix/build', 'team/build', 'review/quality', 'test/verify', 'retro/archive'] as const

const STAGE_DEFAULTS: Record<string, { agent: string; skill: string }> = {
  STORMING:  { agent: 'planner',  skill: 'plan/storm' },
  PLANNING:  { agent: 'planner',  skill: 'plan/scope' },
  BUILDING:  { agent: 'builder',  skill: 'fix/build' },
  REVIEWING: { agent: 'reviewer', skill: 'review/quality' },
  TESTING:   { agent: 'tester',   skill: 'test/verify' },
  DONE:      { agent: 'retro',    skill: 'retro/archive' },
}

const SKILL_PROMPTS: Record<string, string> = {
  'plan/storm':     '# plan/storm\nHost: Claude Code · Agent: planner\n\nRole: Stage orchestrator — Brainstorm.\nExplore the problem space. Generate options. No code yet.',
  'plan/scope':     '# plan/scope\nHost: Claude Code · Agent: planner\n\nRole: Stage orchestrator — Scope.\nDefine user stories, acceptance criteria, conversation breakdown.',
  'fix/build':      '# fix/build\nHost: Claude Code · Agent: builder\n\nRole: Stage orchestrator — Quick Fix.\nApply a single, well-scoped change. No multi-conversation\nplanning, no PROGRESS.md churn.\n\n· Read the issue description in plans/<feature>/\n· Locate the code\n· Apply the minimal change',
  'team/build':     '# team/build\nHost: Claude Code · Agent: builder\n\nRole: Stage orchestrator — Build.\nFollow the implementation plan. Write tests. Ship it.',
  'review/quality': '# review/quality\nHost: Claude Code · Agent: reviewer\n\nRole: Stage orchestrator — Review.\nAdversarial code review. Find bugs, security issues, design gaps.\nWrite failures to REVIEW_FAILURES.md.',
  'test/verify':    '# test/verify\nHost: Claude Code · Agent: tester\n\nRole: Stage orchestrator — Test.\nRun acceptance criteria against implementation.\nWrite gaps to TEST_FAILURES.md.',
  'retro/archive':  '# retro/archive\nHost: Claude Code · Agent: retro\n\nRole: Stage orchestrator — Retro.\nSummarise what was built, cost, and lessons learned.',
}

interface Props {
  stage: string
  onClose: () => void
}

export function ConfigurePhaseModal({ stage, onClose }: Props): JSX.Element {
  const defaults = STAGE_DEFAULTS[stage] ?? { agent: 'builder', skill: 'fix/build' }
  const [host, setHost]   = useState<string>('Claude Code')
  const [agent, setAgent] = useState<string>(defaults.agent)
  const [skill, setSkill] = useState<string>(defaults.skill)

  function handleApply(): void {
    onClose()
  }

  const preview = SKILL_PROMPTS[skill] ?? `# ${skill}\n\nNo preview available.`

  return createPortal(
    <div
      className={styles.backdrop}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className={styles.modal} role="dialog" aria-modal="true" aria-label={`Configure ${stage} phase`}>
        <div className={styles.header}>
          <Settings size={16} className={styles.gearIcon} />
          <span className={styles.title}>Configure phase</span>
          <span className={styles.subtitle}>— what runs when the pipeline enters this stage</span>
          <StatePill state={stage as Parameters<typeof StatePill>[0]['state']} className={styles.stagePill} />
          <button type="button" className={styles.close} onClick={onClose} aria-label="Close">
            <X size={16} />
          </button>
        </div>

        <div className={styles.body}>
          <div className={styles.section}>
            <div className={styles.sectionLabel}>CLI Host</div>
            <div className={styles.chips}>
              {CLI_HOSTS.map((h) => (
                <button
                  key={h}
                  type="button"
                  className={`${styles.chip} ${host === h ? styles.chipActive : ''}`}
                  onClick={() => setHost(h)}
                >
                  {h}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionLabel}>Agent</div>
            <div className={styles.chips}>
              {AGENTS.map((a) => (
                <button
                  key={a}
                  type="button"
                  className={`${styles.chip} ${styles.chipMono} ${agent === a ? styles.chipActive : ''}`}
                  onClick={() => setAgent(a)}
                >
                  {a}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionLabel}>Skill</div>
            <div className={styles.chips}>
              {SKILLS.map((sk) => (
                <button
                  key={sk}
                  type="button"
                  className={`${styles.chip} ${styles.chipMono} ${skill === sk ? styles.chipActive : ''}`}
                  onClick={() => setSkill(sk)}
                >
                  {sk}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.section}>
            <div className={styles.sectionLabel}>Prompt Preview</div>
            <pre className={styles.promptPre}>{preview}</pre>
          </div>
        </div>

        <div className={styles.footer}>
          <button type="button" className={styles.notebookBtn}>
            <BookOpen size={14} />
            Open skill in Notebook
          </button>
          <span className={styles.footerSpacer} />
          <button type="button" className={styles.cancelBtn} onClick={onClose}>Cancel</button>
          <button type="button" className={styles.applyBtn} onClick={handleApply}>
            <Check size={14} />
            Apply
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}
