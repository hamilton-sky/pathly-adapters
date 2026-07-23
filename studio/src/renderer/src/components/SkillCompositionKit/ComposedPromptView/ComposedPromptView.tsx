import { fragmentPurpose } from '../data/fragmentMeta'
import styles from './ComposedPromptView.module.css'

interface Props {
  skill: string
  totalTokens: number
  includedFragments: string[]
}

/**
 * The live composed prompt (fixed header, scrolling body). Skill body + one "injected
 * fragment" block per included fragment. Toggling a fragment adds/removes its block.
 * Swap the hard-coded body demo for the app's MarkdownRenderer fed by useComposedPreview().
 */
export function ComposedPromptView({ skill, totalTokens, includedFragments }: Props): JSX.Element {
  return (
    <>
      <div className={styles.head}>
        <span className={styles.label}>Composed prompt</span>
        <span className={styles.skill}>{skill}</span>
        <span className={styles.spacer} />
        <span className={styles.tokens}>≈ {totalTokens.toLocaleString()} tokens</span>
      </div>
      <div className={styles.body}>
        <div className={styles.inner}>
          <h1 className={styles.h1}>{skill}</h1>
          <p className={styles.p}>FIXING stage. The root cause has been diagnosed — now implement the targeted fix.</p>
          <p className={styles.p}>Parse <code className={styles.codeAccent}>$ARGUMENTS</code> : <code className={styles.codeAccent}>TOPIC</code> (the bug/issue identifier).</p>
          <h2 className={styles.h2}>Role</h2>
          <p className={styles.p}><strong className={styles.strong}>Stage orchestrator: Debug Fix.</strong> Apply the fix identified in the root-cause analysis. Stay strictly within the diagnosed scope — do not refactor, clean up, or improve unrelated code.</p>
          <h2 className={styles.h2}>Context files</h2>
          <p className={styles.pTight}>Before touching any code, read:</p>
          <ul className={styles.ul}>
            <li><code className={styles.codeGreen}>&lt;feature_path&gt;/ROOT_CAUSE.md</code> — diagnosis and agreed fix approach</li>
            <li><code className={styles.codeGreen}>&lt;feature_path&gt;/REPRO.md</code> — reproduction steps (if present)</li>
          </ul>
          {includedFragments.length > 0 && (
            <>
              <h2 className={styles.h2Green}>Injected fragments · skills &amp; agents</h2>
              {includedFragments.map((name) => (
                <div key={name} className={styles.inject}>
                  <span className={styles.injectName}>{name}</span>
                  <div className={styles.injectDesc}>{fragmentPurpose(name)}</div>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </>
  )
}
