import React, { useEffect, useRef } from 'react'
import { PanelRightClose } from 'lucide-react'
import { useSkillNotebookStore } from '../../../store/skillNotebookStore'
import { useUiStore } from '../../../store/uiStore'
import styles from './PreviewPanel.module.css'
import PreviewSection from './PreviewSection/PreviewSection'

export default function PreviewPanel() {
  const {
    cells, compositionKey, featurePath,
    previewSections, previewTokens, previewLoading,
    setPreview, setPreviewLoading,
  } = useSkillNotebookStore()
  const togglePreview = useUiStore((s) => s.toggleNotebookPreview)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    // Don't call the API if no skill is open
    if (!compositionKey && cells.length === 0) return

    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      setPreviewLoading(true)

      const bodyCells = cells
        .filter(c => c.type === 'body')
        .map(c => ({ heading: (c as any).heading ?? '', content: (c as any).content ?? '' }))

      const fragmentCells = cells
        .filter(c => c.type === 'fragment')
        .map(c => ({ type: 'fragment', fragmentName: (c as any).fragmentName }))

      fetch('http://localhost:8765/skills/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          skill: compositionKey,
          cells: fragmentCells,
          body_cells: bodyCells,
          feature_path: featurePath ?? '',
        }),
      })
        .then(r => r.json())
        .then(data => setPreview(data.sections ?? [], data.tokens ?? 0))
        .catch(() => setPreviewLoading(false))
    }, 350)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [cells, compositionKey, featurePath])

  const skillLabel = compositionKey || '—'
  const cellCount = previewSections.length

  return (
    <div className={styles.root}>
      <div className={styles.pvHead}>
        <span title={skillLabel} className={styles.pvTitle}>{skillLabel}</span>
        <div className={styles.pvHeadSpacer} />
        <span className={styles.liveBadge}>
          <span className={styles.liveDot} />
          live
        </span>
        <button
          type="button"
          className={styles.pvCloseBtn}
          onClick={togglePreview}
          aria-label="Close preview"
        >
          <PanelRightClose size={14} />
        </button>
      </div>

      <div className={`${styles.pvBody} ${previewLoading ? styles.loading : ''}`}>
        {previewSections.map((s, i) => (
          <PreviewSection key={i} heading={s.heading} content={s.content} />
        ))}
        {previewSections.length === 0 && !previewLoading && (
          <div className={styles.empty}>
            {compositionKey ? 'No content yet — add body or fragment cells' : 'Open a skill to see the live preview'}
          </div>
        )}
      </div>

      <div className={styles.pvFoot}>
        {cellCount} cells · ≈ {previewTokens} tokens · compiled clean
      </div>
    </div>
  )
}
