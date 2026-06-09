import { useState, useEffect } from 'react'
import { getDsPort } from '../../services/pathlyApi'
import styles from './GettingStarted.module.css'
import { SlideCarousel } from './SlideCarousel/SlideCarousel'
import { StepCard } from './StepCard/StepCard'

const SLIDES = [
  { file: 'title.html',        name: 'Title' },
  { file: 'pipeline.html',     name: 'Pipeline' },
  { file: 'flow-builder.html', name: 'Flow Builder' },
  { file: 'metrics.html',      name: 'Metrics' },
  { file: 'quote.html',        name: 'Quote' },
] as const

const STEPS = [
  {
    step: '01',
    title: 'Open a project folder',
    desc: 'Click "+ New project" on the Projects tab and pick any folder containing a pathly.json or pathly/ directory.',
  },
  {
    step: '02',
    title: 'Create flows in the sidebar',
    desc: 'Use the sidebar to create agent flows (YAML), editor files, or plan boards. The tree mirrors your project.',
  },
  {
    step: '03',
    title: 'Run flows with Monitor',
    desc: 'Select a flow and click Run. Watch live agent output and logs as your pipeline executes in real time.',
  },
  {
    step: '04',
    title: 'Track work with Plan Board',
    desc: 'Open any plan folder from the sidebar. Conversations move TODO → IN PROGRESS → DONE as you build.',
  },
] as const

interface Props {
  onGoToProjects: () => void
}

export function GettingStarted({ onGoToProjects }: Props): JSX.Element {
  const [dsPort, setDsPort] = useState<number | null>(null)

  useEffect(() => {
    try { getDsPort().then(setDsPort).catch(() => {}) } catch { /* IPC unavailable */ }
  }, [])

  return (
    <div className={styles.root}>
      <SlideCarousel dsPort={dsPort} slides={SLIDES} />

      <section className={styles.stepsSection}>
        <h2 className={styles.stepsTitle}>Getting Started with Pathly Studio</h2>
        <p className={styles.stepsSubtitle}>
          A quick overview of how the workspace is structured.
        </p>
        <div className={styles.stepsGrid}>
          {STEPS.map((s, i) => (
            <StepCard key={s.step} step={s.step} title={s.title} desc={s.desc} index={i} />
          ))}
        </div>
      </section>

      <button type="button" className={styles.ctaBtn} onClick={onGoToProjects}>
        Go to Projects →
      </button>
    </div>
  )
}
