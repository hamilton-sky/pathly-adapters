import { useState } from 'react'
import type { SkillCompositionEntry } from '../integration'
import type { PanelView, FragmentVM } from '../types'
import { useFragmentToggles } from '../hooks/useFragmentToggles'
import { useComposedPreview } from '../hooks/useComposedPreview'
import { fragmentPurpose, fragmentTokens } from '../data/fragmentMeta'
import { BODY_TOKENS } from '../data/systemPrompt'
import { CompositionSummary } from '../CompositionSummary/CompositionSummary'
import { ConfigView } from '../ConfigView/ConfigView'
import { PreviewView } from '../PreviewView/PreviewView'
import styles from './FragmentPanel.module.css'

interface Props {
  skill: string
  entry: SkillCompositionEntry | undefined
  allFragments: string[]
  projectRoot: string
  onChanged: () => void
}

export function FragmentPanel({ skill, entry, allFragments, projectRoot, onChanged }: Props): JSX.Element {
  const source = entry?.source ?? 'manifest'
  const overridden = source === 'override'
  const [view, setView] = useState<PanelView>('config')

  const { fragments, toggleFragment, resetToDefault, saving, resetting } = useFragmentToggles(
    skill, entry?.fragments ?? [], source, projectRoot, onChanged,
  )
  const { tokens: composedTokens } = useComposedPreview(skill, fragments, projectRoot)

  const included: FragmentVM[] = fragments.map((name, i) => ({
    order: i + 1, name, purpose: fragmentPurpose(name), tokens: fragmentTokens(name),
  }))
  const fragTokens = included.reduce((s, f) => s + f.tokens, 0)
  const totalTokens = composedTokens > 0 ? composedTokens : BODY_TOKENS + fragTokens
  const displayName = skill.replace(/^([^/]+)\//, (_, c) => c.toLowerCase() + '/')

  return (
    <div className={styles.panel}>
      <div className={styles.head}>
        <span className={styles.skillName}>{displayName}</span>
        {overridden && <span className={styles.overPill}><i className={styles.overDot} />overridden</span>}
        {saving && <span className={styles.status}>saving…</span>}
        <span className={styles.spacer} />
        <button
          type="button"
          className={styles.resetBtn}
          disabled={!overridden || resetting}
          onClick={resetToDefault}
        >
          {resetting ? 'Resetting…' : 'Reset to default'}
        </button>
      </div>

      <div className={styles.toolbar}>
        <div className={styles.tabs} role="tablist">
          <button type="button" role="tab" aria-selected={view === 'preview'} data-active={view === 'preview'} className={styles.tab} onClick={() => setView('preview')}>Preview</button>
          <button type="button" role="tab" aria-selected={view === 'config'} data-active={view === 'config'} className={styles.tab} onClick={() => setView('config')}>Config</button>
        </div>
        <span className={styles.spacer} />
        <span className={styles.meta}>{fragments.length} fragment{fragments.length === 1 ? '' : 's'} · {source}</span>
      </div>

      {view === 'config' ? (
        <>
          <CompositionSummary
            bodyTokens={BODY_TOKENS}
            fragTokens={fragTokens}
            totalTokens={totalTokens}
            includedCount={included.length}
            allCount={allFragments.length}
          />
          <ConfigView
            skill={skill}
            included={included}
            allFragments={allFragments}
            totalTokens={totalTokens}
            onToggleFragment={toggleFragment}
          />
        </>
      ) : (
        <PreviewView
          skill={displayName}
          fragments={fragments}
          allFragments={allFragments}
          totalTokens={totalTokens}
          onToggleFragment={toggleFragment}
        />
      )}
    </div>
  )
}
