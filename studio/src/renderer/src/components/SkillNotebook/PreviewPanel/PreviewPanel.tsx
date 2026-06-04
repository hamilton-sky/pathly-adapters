import React, { useEffect, useRef } from 'react'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'
import styles from './PreviewPanel.module.css'
import PreviewSection from './PreviewSection/PreviewSection'

export default function PreviewPanel() {
  const { cells, featurePath, previewSections, previewTokens, previewLoading, setPreview, setPreviewLoading, setFeaturePath } = useSkillNotebookStore()
  const [rawMode, setRawMode] = React.useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      const fragmentCells = cells.filter(c => c.type === 'fragment')
      if (fragmentCells.length === 0 && cells.length === 0) return
      setPreviewLoading(true)
      fetch('http://localhost:8765/skills/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill: 'team/build',
          cells: fragmentCells.map(c => ({ type: 'fragment', fragmentName: (c as any).fragmentName })),
          feature_path: featurePath ?? 'pathly/plans/example',
        }),
      })
        .then(r => r.json())
        .then(data => setPreview(data.sections ?? [], data.tokens ?? 0))
        .catch(() => setPreviewLoading(false))
    }, 250)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [cells, featurePath])

  const rawText = previewSections.map(s => `## ${s.heading}\n${s.content}`).join('\n\n')

  return (
    <div className={styles.root}>
      <div className={styles.toolbar}>
        <input
          className={styles.featureInput}
          placeholder="Feature path…"
          value={featurePath ?? ''}
          onChange={e => setFeaturePath(e.target.value || null)}
        />
        <button
          type="button"
          className={styles.rawToggle}
          onClick={() => setRawMode(r => !r)}
        >
          {rawMode ? 'Sections' : 'Raw'}
        </button>
      </div>
      <div className={`${styles.sections} ${previewLoading ? styles.loading : ''}`}>
        {rawMode ? (
          <pre className={styles.raw}>{rawText}</pre>
        ) : (
          previewSections.map((s, i) => (
            <PreviewSection key={i} heading={s.heading} content={s.content} origin={s.origin} />
          ))
        )}
        {previewSections.length === 0 && !previewLoading && (
          <div className={styles.empty}>Add fragments to see preview</div>
        )}
      </div>
      <div className={styles.tokenBar}>
        ~{previewTokens} tokens estimated
      </div>
    </div>
  )
}
