import { useState, useEffect, useRef } from 'react'
import { ChevronDown } from 'lucide-react'
import { WEB_LLM_MODELS } from '../../data/models'
import { useModelStore } from '../../store/modelStore'
import { cacheWebLLMModel, cancelEngineLoad, deleteCachedWebLLMModel, getCachedWebLLMModelIds } from '../../lib/webLLMEngine'
import styles from './ModelSelector.module.css'

function formatElapsed(secs: number): string {
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

/** Translate raw WebLLM status text into a short human-readable phase label. */
function describePhase(text: string | undefined): { label: string; hint?: string } {
  if (!text) return { label: 'connecting…' }
  const t = text.toLowerCase()

  // GPU shader / WASM compilation — the slow one-time step
  if (t.includes('shader') || (t.includes('gpu') && t.includes('module')) || t.includes('compil')) {
    const m = text.match(/\[(\d+)\/(\d+)\]/)
    const pct = text.match(/:\s*(\d+)%/)
    const pos = m ? ` ${m[1]}/${m[2]}` : ''
    const pctLabel = pct ? ` (${pct[1]}%)` : ''
    return {
      label: `compiling GPU shaders${pos}${pctLabel}`,
      hint: 'One-time compilation — next launch will be instant',
    }
  }

  // Fetching / downloading model weight shards
  if (t.includes('fetch') || t.includes('param cache') || t.includes('downloading')) {
    const m = text.match(/\[(\d+)\/(\d+)\]/)
    return { label: m ? `downloading weights ${m[1]}/${m[2]}` : 'downloading weights…' }
  }

  // Loading already-cached files
  if (t.includes('loading') || t.includes('from cache')) {
    const m = text.match(/\[(\d+)\/(\d+)\]/)
    return { label: m ? `loading ${m[1]}/${m[2]}` : 'loading from cache…' }
  }

  // Fallback: try to extract [X/Y]
  const m = text.match(/\[(\d+)\/(\d+)\]/)
  return { label: m ? `step ${m[1]}/${m[2]}` : 'preparing…' }
}

export function ModelSelector(): JSX.Element {
  const [open, setOpen] = useState(false)
  const [progressText, setProgressText] = useState<Record<string, string>>({})
  const [downloadStart, setDownloadStart] = useState<Record<string, number>>({})
  const [elapsed, setElapsed] = useState<Record<string, number>>({})
  const [downloadPhase, setDownloadPhase] = useState<Record<string, number>>({})
  const [lastProgress, setLastProgress] = useState<Record<string, number>>({})
  const ref = useRef<HTMLDivElement>(null)

  const selectedModelId = useModelStore((s) => s.selectedModelId)
  const cachedModelIds = useModelStore((s) => s.cachedModelIds)
  const downloadProgress = useModelStore((s) => s.downloadProgress)
  const setSelectedModel = useModelStore((s) => s.setSelectedModel)
  const setCached = useModelStore((s) => s.setCached)
  const setProgress = useModelStore((s) => s.setProgress)

  const selectedModel = WEB_LLM_MODELS.find((m) => m.id === selectedModelId)
  const shortName = selectedModel?.name ?? selectedModelId
  const isSelectedCached = cachedModelIds.includes(selectedModelId)

  // Sync cached model list on mount
  useEffect(() => {
    getCachedWebLLMModelIds().then(setCached).catch(() => {})
  }, [setCached])

  // Close on outside click
  useEffect(() => {
    if (!open) return
    function handleMouseDown(e: MouseEvent): void {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [open])

  // Tick elapsed timer while any model is downloading
  useEffect(() => {
    const active = Object.entries(downloadProgress)
      .filter(([, p]) => p > 0 && p < 100)
      .map(([id]) => id)
    if (active.length === 0) return
    const t = setInterval(() => {
      const now = Date.now()
      setElapsed(prev => {
        const next = { ...prev }
        for (const id of active) {
          const start = downloadStart[id]
          if (start) next[id] = Math.round((now - start) / 1000)
        }
        return next
      })
    }, 1000)
    return () => clearInterval(t)
  }, [downloadProgress, downloadStart])

  function handleCancelDownload(modelId: string): void {
    cancelEngineLoad()
    setProgress(modelId, 0)
    setProgressText((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    setDownloadStart((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    setElapsed((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    setDownloadPhase((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    setLastProgress((prev) => { const n = { ...prev }; delete n[modelId]; return n })
  }

  async function handleCacheToggle(modelId: string): Promise<void> {
    const isCached = cachedModelIds.includes(modelId)
    if (isCached) {
      await deleteCachedWebLLMModel(modelId)
      setCached(cachedModelIds.filter((id) => id !== modelId))
      setProgressText((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    } else {
      const startMs = Date.now()
      setDownloadStart(prev => ({ ...prev, [modelId]: startMs }))
      setDownloadPhase(prev => ({ ...prev, [modelId]: 1 }))
      setLastProgress(prev => ({ ...prev, [modelId]: 0 }))
      setProgress(modelId, 0)
      await cacheWebLLMModel(modelId, (pct, text) => {
        setProgress(modelId, pct)
        if (text) setProgressText((prev) => ({ ...prev, [modelId]: text }))
        // Detect phase reset: if progress drops from a high value back to low,
        // WebLLM moved from setup phase → weights phase
        setLastProgress(prev => {
          const prev_ = prev[modelId] ?? 0
          if (prev_ > 60 && pct < 20) {
            setDownloadPhase(p => ({ ...p, [modelId]: 2 }))
          }
          return { ...prev, [modelId]: pct }
        })
      })
      const updated = await getCachedWebLLMModelIds()
      setCached(updated)
      setProgress(modelId, 100)
      setProgressText((prev) => { const n = { ...prev }; delete n[modelId]; return n })
      setDownloadPhase((prev) => { const n = { ...prev }; delete n[modelId]; return n })
      setLastProgress((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    }
  }

  return (
    <div className={styles.wrapper} ref={ref}>
      <div className={styles.trigger}>
        <button
          className={styles.triggerBtn}
          onClick={() => setOpen((v) => !v)}
          title="Select local AI model"
        >
          <span className={isSelectedCached ? styles.readyDot : styles.notReadyDot} />
          <span className={styles.triggerName}>{shortName}</span>
          <ChevronDown size={11} className={open ? styles.chevronOpen : styles.chevron} />
        </button>
      </div>

      {open && (
        <div className={styles.panel}>
          {WEB_LLM_MODELS.map((model) => {
            const isCached = cachedModelIds.includes(model.id)
            const isSelected = model.id === selectedModelId
            const progress = downloadProgress[model.id] ?? 0
            // Show downloading state from the moment the download starts (downloadStart set),
            // not only after the first shard callback fires (progress > 0).
            const isDownloading = (downloadStart[model.id] !== undefined && !isCached) && progress < 100

            return (
              <div
                key={model.id}
                className={`${styles.card} ${isSelected ? styles.cardSelected : ''} ${isDownloading ? styles.cardDownloading : ''}`}
                onClick={() => setSelectedModel(model.id)}
              >
                <div className={styles.cardHeader}>
                  <span className={styles.cardName}>{model.name}</span>
                  <div className={styles.badges}>
                    {model.recommended && (
                      <span className={styles.badgeRecommended}>Recommended</span>
                    )}
                    {isCached && (
                      <span className={styles.badgeCached}>Cached</span>
                    )}
                    {isSelected && (
                      <span className={styles.badgeSelected}>Selected</span>
                    )}
                  </div>
                </div>

                <p className={styles.cardDesc}>{model.description}</p>

                <div className={styles.infoRows}>
                  <div className={styles.infoRow}>
                    <span className={styles.infoKey}>SYSTEM</span>
                    <span className={styles.infoVal}>{model.system}</span>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.infoKey}>STORAGE</span>
                    <span className={styles.infoVal}>{model.storage}</span>
                  </div>
                  <div className={styles.infoRow}>
                    <span className={styles.infoKey}>SPEED</span>
                    <span className={styles.infoVal}>{model.speed}</span>
                  </div>
                </div>

                {isDownloading && (() => {
                  const phase = describePhase(progressText[model.id])
                  return (
                  <div className={styles.downloadBlock}>
                    {/* meta row: percent + phase label + elapsed */}
                    <div className={styles.downloadMeta}>
                      <span className={styles.downloadPct}>{progress > 0 ? `${progress}%` : '…'}</span>
                      <span className={styles.downloadPhase}>{phase.label}</span>
                      <span className={styles.downloadElapsed}>{formatElapsed(elapsed[model.id] ?? 0)}</span>
                    </div>

                    {/* two-layer progress bar: stripes behind, solid fill on top */}
                    <div className={styles.progressTrack}>
                      <div className={styles.progressStripes} />
                      <div className={styles.progressFill} style={{ width: `${progress}%` }} />
                    </div>

                    {/* one-time hint (e.g. shader compilation) */}
                    {phase.hint && (
                      <span className={styles.downloadHint}>{phase.hint}</span>
                    )}
                  </div>
                  )
                })()}

                {isDownloading ? (
                  <button
                    className={`${styles.cacheBtn} ${styles.cacheBtnCancel}`}
                    onClick={(e) => { e.stopPropagation(); handleCancelDownload(model.id) }}
                  >
                    ✕ Cancel download
                  </button>
                ) : (
                  <button
                    className={`${styles.cacheBtn} ${isCached ? styles.cacheBtnOn : ''}`}
                    onClick={(e) => {
                      e.stopPropagation()
                      void handleCacheToggle(model.id)
                    }}
                  >
                    {isCached ? '✓ Downloaded & ready  —  click to remove' : isSelected ? '↓ Download & use this model' : '↓ Download & cache'}
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
