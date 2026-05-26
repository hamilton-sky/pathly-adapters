import { useState, useEffect, useRef } from 'react'
import { ChevronDown, Info } from 'lucide-react'
import { WEB_LLM_MODELS } from '../../data/models'
import { useModelStore } from '../../store/modelStore'
import { cacheWebLLMModel, deleteCachedWebLLMModel, getCachedWebLLMModelIds } from '../../lib/webLLMEngine'
import styles from './ModelSelector.module.css'

function formatElapsed(secs: number): string {
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

function parseShardLabel(text: string | undefined): string | null {
  // WebLLM fires text like "Fetching param cache[3/12]: 340MB/s"
  const m = text?.match(/\[(\d+)\/(\d+)\]/)
  if (m) return `shard ${m[1]}/${m[2]}`
  return null
}

export function ModelSelector(): JSX.Element {
  const [open, setOpen] = useState(false)
  const [showInfo, setShowInfo] = useState(false)
  const [progressText, setProgressText] = useState<Record<string, string>>({})
  const [downloadStart, setDownloadStart] = useState<Record<string, number>>({})
  const [elapsed, setElapsed] = useState<Record<string, number>>({})
  const ref = useRef<HTMLDivElement>(null)

  const selectedModelId = useModelStore((s) => s.selectedModelId)
  const cachedModelIds = useModelStore((s) => s.cachedModelIds)
  const downloadProgress = useModelStore((s) => s.downloadProgress)
  const setSelectedModel = useModelStore((s) => s.setSelectedModel)
  const setCached = useModelStore((s) => s.setCached)
  const setProgress = useModelStore((s) => s.setProgress)

  const selectedModel = WEB_LLM_MODELS.find((m) => m.id === selectedModelId)
  const shortName = selectedModel?.name ?? selectedModelId

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

  async function handleCacheToggle(modelId: string): Promise<void> {
    const isCached = cachedModelIds.includes(modelId)
    if (isCached) {
      await deleteCachedWebLLMModel(modelId)
      setCached(cachedModelIds.filter((id) => id !== modelId))
      setProgressText((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    } else {
      const startMs = Date.now()
      setDownloadStart(prev => ({ ...prev, [modelId]: startMs }))
      setProgress(modelId, 0)
      await cacheWebLLMModel(modelId, (pct, text) => {
        setProgress(modelId, pct)
        if (text) setProgressText((prev) => ({ ...prev, [modelId]: text }))
      })
      const updated = await getCachedWebLLMModelIds()
      setCached(updated)
      setProgress(modelId, 100)
      setProgressText((prev) => { const n = { ...prev }; delete n[modelId]; return n })
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
          <span className={styles.triggerName}>{shortName}</span>
          <ChevronDown size={11} className={open ? styles.chevronOpen : styles.chevron} />
        </button>
        <button
          className={styles.infoBtn}
          onClick={() => setShowInfo((v) => !v)}
          title="Model info"
        >
          <Info size={11} />
        </button>
      </div>

      {open && (
        <div className={styles.panel}>
          {WEB_LLM_MODELS.map((model) => {
            const isCached = cachedModelIds.includes(model.id)
            const isSelected = model.id === selectedModelId
            const progress = downloadProgress[model.id] ?? 0
            const isDownloading = progress > 0 && progress < 100

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

                {isDownloading && (
                  <div className={styles.downloadBlock}>
                    {/* meta row: percent + shard label + elapsed */}
                    <div className={styles.downloadMeta}>
                      <span className={styles.downloadPct}>{progress}%</span>
                      <span className={styles.downloadPhase}>
                        {parseShardLabel(progressText[model.id]) ?? 'downloading…'}
                      </span>
                      <span className={styles.downloadElapsed}>
                        {formatElapsed(elapsed[model.id] ?? 0)}
                      </span>
                    </div>

                    {/* two-layer progress bar: stripes behind, solid fill on top */}
                    <div className={styles.progressTrack}>
                      <div className={styles.progressStripes} />
                      <div className={styles.progressFill} style={{ width: `${progress}%` }} />
                    </div>

                    {/* raw WebLLM status text — truncated to one line */}
                    {progressText[model.id] && (
                      <span className={styles.downloadStatus}>
                        {progressText[model.id]}
                      </span>
                    )}
                  </div>
                )}

                <button
                  className={`${styles.cacheBtn} ${isCached ? styles.cacheBtnOn : ''}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    void handleCacheToggle(model.id)
                  }}
                  disabled={isDownloading}
                >
                  {isCached ? '✕ Remove from cache' : isDownloading ? `Downloading ${progress}%…` : isSelected ? '↓ Download & use this model' : '↓ Download & cache'}
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
