import { WEB_LLM_MODELS } from '../../../data/models'
import styles from './ModelSelector.module.css'

type Model = typeof WEB_LLM_MODELS[number]

interface ModelCardProps {
  model: Model
  isSelected: boolean
  isCached: boolean
  isGgufCached: boolean
  isOllamaInstalled: boolean
  isOllamaAvailable: boolean
  isDownloading: boolean
  canDownload: boolean
  progress: number
  progressText: string | undefined
  elapsed: number
  ollamaAvailable: boolean | null
  onSelect: () => void
  onCacheToggle: () => void
  onCancelDownload: () => void
}

function formatElapsed(secs: number): string {
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

function describePhase(text: string | undefined): { label: string; hint?: string } {
  if (!text) return { label: 'preparing…' }
  const t = text.toLowerCase()
  if (t.includes('downloading')) return { label: text }
  if (t.includes('loading model')) return { label: text, hint: 'Loaded once — stays in memory until you switch models' }
  if (t.includes('ready')) return { label: 'ready' }
  return { label: text }
}

export function ModelCard({
  model,
  isSelected,
  isCached,
  isGgufCached,
  isOllamaInstalled,
  isDownloading,
  canDownload,
  progress,
  progressText,
  elapsed,
  ollamaAvailable,
  onSelect,
  onCacheToggle,
  onCancelDownload,
}: ModelCardProps): JSX.Element {
  return (
    <div
      key={model.id}
      className={`${styles.card} ${isSelected ? styles.cardSelected : ''} ${isDownloading ? styles.cardDownloading : ''}`}
      onClick={onSelect}
    >
      <div className={styles.cardHeader}>
        <span className={styles.cardName}>{model.name}</span>
        <div className={styles.badges}>
          {model.recommended && (
            <span className={styles.badgeRecommended}>Recommended</span>
          )}
          {isOllamaInstalled && (
            <span className={styles.badgeCached}>Ollama</span>
          )}
          {isGgufCached && !isOllamaInstalled && (
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
        const phase = describePhase(progressText)
        return (
          <div className={styles.downloadBlock}>
            <div className={styles.downloadMeta}>
              <span className={styles.downloadPct}>{progress > 0 ? `${progress}%` : '…'}</span>
              <span className={styles.downloadPhase}>{phase.label}</span>
              <span className={styles.downloadElapsed}>{formatElapsed(elapsed)}</span>
            </div>
            <progress className={styles.downloadProgress} value={progress} max={100} />
            {phase.hint && (
              <span className={styles.downloadHint}>{phase.hint}</span>
            )}
          </div>
        )
      })()}

      {isDownloading ? (
        <button
          type="button"
          className={`${styles.cacheBtn} ${styles.cacheBtnCancel}`}
          onClick={(e) => { e.stopPropagation(); onCancelDownload() }}
        >
          ✕ Cancel download
        </button>
      ) : (
        <button
          type="button"
          className={`${styles.cacheBtn} ${isCached ? styles.cacheBtnOn : canDownload && isSelected ? styles.cacheBtnPrimary : ''}`}
          disabled={!isCached && !canDownload}
          title={!isCached && !canDownload ? 'Install Ollama or upgrade to Electron 33+' : undefined}
          onClick={(e) => {
            e.stopPropagation()
            onCacheToggle()
          }}
        >
          {isCached
            ? `${isOllamaInstalled ? 'Installed via Ollama' : 'Downloaded'}  —  click to remove`
            : !canDownload
              ? 'Install Ollama to download models'
              : ollamaAvailable
                ? isSelected ? '↓ Pull via Ollama' : '↓ Pull & cache via Ollama'
                : isSelected ? '↓ Download & use this model' : '↓ Download & cache'}
        </button>
      )}
    </div>
  )
}
