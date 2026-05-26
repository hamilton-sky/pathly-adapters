import { useState, useEffect, useRef } from 'react'
import { ChevronDown, Info } from 'lucide-react'
import { WEB_LLM_MODELS } from '../../data/models'
import { useModelStore } from '../../store/modelStore'
import { cacheWebLLMModel, deleteCachedWebLLMModel, getCachedWebLLMModelIds } from '../../lib/webLLMEngine'
import styles from './ModelSelector.module.css'

export function ModelSelector(): JSX.Element {
  const [open, setOpen] = useState(false)
  const [showInfo, setShowInfo] = useState(false)
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

  async function handleCacheToggle(modelId: string): Promise<void> {
    const isCached = cachedModelIds.includes(modelId)
    if (isCached) {
      await deleteCachedWebLLMModel(modelId)
      setCached(cachedModelIds.filter((id) => id !== modelId))
    } else {
      setProgress(modelId, 0)
      await cacheWebLLMModel(modelId, (pct) => {
        setProgress(modelId, pct)
      })
      const updated = await getCachedWebLLMModelIds()
      setCached(updated)
      setProgress(modelId, 100)
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
                className={`${styles.card} ${isSelected ? styles.cardSelected : ''}`}
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
                  <div className={styles.progressTrack}>
                    <div
                      className={styles.progressFill}
                      style={{ width: `${progress}%` }}
                    />
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
                  {isCached ? '✓ Cached — click to remove' : isDownloading ? `Downloading ${progress}%…` : '↓ Download & cache'}
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
