import { useState, useEffect, useRef } from 'react'
import { ChevronDown } from 'lucide-react'
import { WEB_LLM_MODELS } from '../../data/models'
import { useModelStore } from '../../store/modelStore'
import { abortLlm, getCachedModelIds, pullOllamaModel, deleteOllamaModel, downloadModel, deleteModel } from '../../lib/llmBridge'
import { useBrightskyStore, BRIGHTSKY_BASE_URL } from '../../store/brightskyStore'
import { brightskyClient } from '../../lib/brightskyClient'
import styles from './ModelSelector.module.css'

function formatElapsed(secs: number): string {
  if (secs < 60) return `${secs}s`
  return `${Math.floor(secs / 60)}m ${secs % 60}s`
}

/** Translate node-llama-cpp progress text into a short human-readable phase label. */
function describePhase(text: string | undefined): { label: string; hint?: string } {
  if (!text) return { label: 'preparing…' }
  const t = text.toLowerCase()
  if (t.includes('downloading')) return { label: text }
  if (t.includes('loading model')) return { label: text, hint: 'Loaded once — stays in memory until you switch models' }
  if (t.includes('ready')) return { label: 'ready' }
  return { label: text }
}

export function ModelSelector(): JSX.Element {
  const [open, setOpen] = useState(false)
  const [llmAvailable, setLlmAvailable] = useState<boolean | null>(null)
  const [progressText, setProgressText] = useState<Record<string, string>>({})
  const [downloadStart, setDownloadStart] = useState<Record<string, number>>({})
  const [elapsed, setElapsed] = useState<Record<string, number>>({})
  const [downloadPhase, setDownloadPhase] = useState<Record<string, number>>({})
  const [lastProgress, setLastProgress] = useState<Record<string, number>>({})
  const ref = useRef<HTMLDivElement>(null)

  const selectedModelId = useModelStore((s) => s.selectedModelId)
  const responseMode = useModelStore((s) => s.responseMode)
  const cachedModelIds = useModelStore((s) => s.cachedModelIds)
  const downloadProgress = useModelStore((s) => s.downloadProgress)
  const setSelectedModel = useModelStore((s) => s.setSelectedModel)
  const setResponseMode = useModelStore((s) => s.setResponseMode)
  const setCached = useModelStore((s) => s.setCached)
  const setProgress = useModelStore((s) => s.setProgress)

  const ollamaAvailable = useModelStore((s) => s.ollamaAvailable)
  const ollamaModelIds = useModelStore((s) => s.ollamaModelIds)
  const setOllama = useModelStore((s) => s.setOllama)

  const brightskyAuthenticated = useBrightskyStore((s) => s.authenticated)
  const brightskyConnected = useBrightskyStore((s) => s.connected)
  const brightskyAuthError = useBrightskyStore((s) => s.authError)
  const clearBrightskyAuth = useBrightskyStore((s) => s.clearAuth)

  const selectedModel = WEB_LLM_MODELS.find((m) => m.id === selectedModelId)
  const isBrightsky = selectedModelId === 'brightsky'
  const shortName = isBrightsky ? 'Brightsky' : (selectedModel?.name ?? selectedModelId)
  const ollamaTag = selectedModel?.ollamaId ?? ''
  const ollamaBase = ollamaTag.split(':')[0]
  const isOllamaCached = ollamaModelIds.some(
    (m) => m === ollamaTag || m.startsWith(ollamaBase + ':') || m.startsWith(ollamaBase + '-')
  )
  const isSelectedCached = cachedModelIds.includes(selectedModelId) || isOllamaCached

  // Check LLM backend availability once on mount (with timeout to avoid hanging on Electron <33)
  useEffect(() => {
    const timeout = setTimeout(() => setLlmAvailable(false), 4000)
    window.pathly.llm.isAvailable()
      .then((ok) => { clearTimeout(timeout); setLlmAvailable(ok) })
      .catch(() => { clearTimeout(timeout); setLlmAvailable(false) })
    return () => clearTimeout(timeout)
  }, [])

  // Sync Ollama state
  useEffect(() => {
    window.pathly.llm.ollamaAvailable()
      .then(({ available, models }) => setOllama(available, models))
      .catch(() => setOllama(false, []))
  }, [setOllama])

  // Sync GGUF cached model list on mount
  useEffect(() => {
    getCachedModelIds().then(setCached).catch(() => {})
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
    abortLlm()
    setProgress(modelId, 0)
    setProgressText((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    setDownloadStart((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    setElapsed((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    setDownloadPhase((prev) => { const n = { ...prev }; delete n[modelId]; return n })
    setLastProgress((prev) => { const n = { ...prev }; delete n[modelId]; return n })
  }

  async function handleCacheToggle(modelId: string): Promise<void> {
    const model = WEB_LLM_MODELS.find((m) => m.id === modelId)
    const tag = model?.ollamaId ?? ''
    const tagBase = tag.split(':')[0]
    const isGgufCached = cachedModelIds.includes(modelId)
    const isOllamaInstalled = ollamaModelIds.some(
      (m) => m === tag || m.startsWith(tagBase + ':') || m.startsWith(tagBase + '-')
    )

    // ── Remove ────────────────────────────────────────────────────────────
    if (isOllamaInstalled) {
      await deleteOllamaModel(tag)
      setOllama(ollamaAvailable ?? false, ollamaModelIds.filter((m) => m !== tag && !m.startsWith(tagBase + ':')))
      setProgressText((prev) => { const n = { ...prev }; delete n[modelId]; return n })
      return
    }
    if (isGgufCached) {
      await deleteModel(modelId)
      setCached(cachedModelIds.filter((id) => id !== modelId))
      setProgressText((prev) => { const n = { ...prev }; delete n[modelId]; return n })
      return
    }

    // ── Download ──────────────────────────────────────────────────────────
    const startMs = Date.now()
    setDownloadStart(prev => ({ ...prev, [modelId]: startMs }))
    setDownloadPhase(prev => ({ ...prev, [modelId]: 1 }))
    setLastProgress(prev => ({ ...prev, [modelId]: 0 }))
    setProgress(modelId, 1)

    const removeDl = window.pathly.llm.onDownloadProgress(({ modelId: id, pct }) => {
      if (id !== modelId && id !== tag) return
      setProgress(modelId, Math.max(1, pct))
      setProgressText(prev => ({ ...prev, [modelId]: `downloading… ${pct}%` }))
    })

    try {
      if (ollamaAvailable) {
        // Pull via Ollama
        await pullOllamaModel(tag, (pct, text) => {
          setProgress(modelId, pct)
          if (text) setProgressText(prev => ({ ...prev, [modelId]: text }))
        })
        // Refresh Ollama model list
        const { models } = await window.pathly.llm.ollamaAvailable()
        setOllama(true, models)
      } else {
        // GGUF download (requires Electron 33+ / node-llama-cpp v3)
        const removeLoad = window.pathly.llm.onLoadProgress(({ pct, text }) => {
          setProgress(modelId, pct)
          if (text) setProgressText(prev => ({ ...prev, [modelId]: text }))
        })
        try {
          await downloadModel(modelId, (pct, text) => {
            setProgress(modelId, pct)
            if (text) setProgressText(prev => ({ ...prev, [modelId]: text }))
          })
          const updated = await getCachedModelIds()
          setCached(updated)
        } finally {
          removeLoad()
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setProgressText(prev => ({ ...prev, [modelId]: `Failed: ${msg}` }))
      setProgress(modelId, 0)
    } finally {
      removeDl()
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
          {isBrightsky ? (
            <span style={{ width: 8, height: 8, borderRadius: '50%', display: 'inline-block', background: brightskyAuthenticated ? '#22c55e' : '#6b7280', flexShrink: 0 }} />
          ) : (
            <span className={isSelectedCached ? styles.readyDot : styles.notReadyDot} />
          )}
          <span className={styles.triggerName}>{shortName}</span>
          <ChevronDown size={11} className={open ? styles.chevronOpen : styles.chevron} />
        </button>
      </div>

      {open && (
        <div className={styles.panel}>
          <div className={styles.modeToggle} role="group" aria-label="Response mode">
            <button
              className={`${styles.modeBtn} ${responseMode === 'fast' ? styles.modeBtnActive : ''}`}
              onClick={() => setResponseMode('fast')}
              type="button"
            >
              Fast
            </button>
            <button
              className={`${styles.modeBtn} ${responseMode === 'deep' ? styles.modeBtnActive : ''}`}
              onClick={() => setResponseMode('deep')}
              type="button"
            >
              Deep
            </button>
          </div>
          {!ollamaAvailable && llmAvailable !== true && (
            <div className={styles.noBackendNote}>
              <strong>No AI backend detected.</strong>
              <br />
              Install <a href="https://ollama.ai" target="_blank" rel="noreferrer">Ollama</a> for local AI,
              then run <code>ollama pull phi4-mini</code>.
              <br />
              <span style={{ opacity: 0.6 }}>Or upgrade to Electron 33+ for built-in inference.</span>
            </div>
          )}

          {/* Brightsky cloud backend */}
          <div
            className={`${styles.card} ${selectedModelId === 'brightsky' ? styles.cardSelected : ''}`}
            onClick={() => setSelectedModel('brightsky')}
          >
            <div className={styles.cardHeader}>
              <span className={styles.cardName}>Brightsky</span>
              <div className={styles.badges}>
                {selectedModelId === 'brightsky' && (
                  <span className={styles.badgeSelected}>Selected</span>
                )}
              </div>
            </div>
            <p className={styles.cardDesc}>Cloud AI backend — streams responses via WebSocket.</p>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', display: 'inline-block', background: brightskyAuthenticated ? '#22c55e' : '#6b7280', flexShrink: 0 }} />
              <span style={{ fontSize: 11, opacity: 0.7 }}>{brightskyConnected ? 'Connected' : 'Disconnected'}</span>
            </div>

            {!brightskyAuthenticated ? (
              <button
                className={styles.cacheBtn}
                onClick={(e) => {
                  e.stopPropagation()
                  window.pathly?.brightsky?.login(BRIGHTSKY_BASE_URL)
                }}
              >
                Connect with Google
              </button>
            ) : (
              <button
                className={`${styles.cacheBtn} ${styles.cacheBtnOn}`}
                onClick={(e) => {
                  e.stopPropagation()
                  clearBrightskyAuth()
                  brightskyClient.disconnect()
                }}
              >
                Disconnect
              </button>
            )}

            {brightskyAuthError && (
              <div style={{ fontSize: 11, color: '#f87171', marginTop: 4 }}>{brightskyAuthError}</div>
            )}
          </div>

          {WEB_LLM_MODELS.map((model) => {
            const tag = model.ollamaId
            const tagBase = tag.split(':')[0]
            const isGgufCached = cachedModelIds.includes(model.id)
            const isOllamaInstalled = ollamaModelIds.some(
              (m) => m === tag || m.startsWith(tagBase + ':') || m.startsWith(tagBase + '-')
            )
            const isCached = isGgufCached || isOllamaInstalled
            const isSelected = model.id === selectedModelId
            const progress = downloadProgress[model.id] ?? 0
            const isDownloading = (downloadStart[model.id] !== undefined && !isCached) && progress < 100
            const canDownload = ollamaAvailable === true || llmAvailable === true

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
                  const phase = describePhase(progressText[model.id])
                  return (
                  <div className={styles.downloadBlock}>
                    <div className={styles.downloadMeta}>
                      <span className={styles.downloadPct}>{progress > 0 ? `${progress}%` : '…'}</span>
                      <span className={styles.downloadPhase}>{phase.label}</span>
                      <span className={styles.downloadElapsed}>{formatElapsed(elapsed[model.id] ?? 0)}</span>
                    </div>
                    <div className={styles.progressTrack}>
                      <div className={styles.progressStripes} />
                      <div className={styles.progressFill} style={{ width: `${progress}%` }} />
                    </div>
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
                    className={`${styles.cacheBtn} ${isCached ? styles.cacheBtnOn : canDownload && isSelected ? styles.cacheBtnPrimary : ''}`}
                    disabled={!isCached && !canDownload}
                    title={!isCached && !canDownload ? 'Install Ollama or upgrade to Electron 33+' : undefined}
                    onClick={(e) => {
                      e.stopPropagation()
                      void handleCacheToggle(model.id)
                    }}
                  >
                    {isCached
                      ? `✓ ${isOllamaInstalled ? 'Installed via Ollama' : 'Downloaded'}  —  click to remove`
                      : !canDownload
                        ? '⚠ Install Ollama to download models'
                        : ollamaAvailable
                          ? isSelected ? '↓ Pull via Ollama' : '↓ Pull & cache via Ollama'
                          : isSelected ? '↓ Download & use this model' : '↓ Download & cache'}
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
