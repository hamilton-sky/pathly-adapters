import { useState } from 'react'
import { apiFetch } from '../../lib/config'
import { ExportSkillPicker } from './ExportSkillPicker'
import ss from './Settings.module.css'
import s from './ExportSettings.module.css'

interface ExportResult {
  adapter: string
  ok: boolean
  summary: string
  exit_code: number
}

interface ExportResponse {
  ok: boolean
  results: ExportResult[]
}

const ADAPTERS: Array<{ id: string; label: string }> = [
  { id: 'claude', label: 'Claude (~/.claude)' },
  { id: 'codex', label: 'Codex (~/.codex + ~/.agents)' },
  { id: 'copilot', label: 'Copilot (~/.vscode/extensions/pathly)' },
  { id: 'antigravity', label: 'Antigravity (~/.gemini/antigravity-cli)' },
]

export function ExportSettings(): JSX.Element {
  const [selected, setSelected] = useState<Set<string>>(new Set(['claude']))
  const [repair, setRepair] = useState(true)
  const [running, setRunning] = useState(false)
  const [results, setResults] = useState<ExportResult[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [skillSelection, setSkillSelection] = useState<Set<string>>(new Set())

  function toggleAdapter(id: string): void {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }

  function toggleAll(): void {
    if (selected.size === ADAPTERS.length) {
      setSelected(new Set())
    } else {
      setSelected(new Set(ADAPTERS.map((a) => a.id)))
    }
  }

  async function handleExport(): Promise<void> {
    const adapters = [...selected]
    if (adapters.length === 0) return
    setRunning(true)
    setResults(null)
    setError(null)
    try {
      const res = await apiFetch('/ops/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ adapters, repair, skills: [...skillSelection] }),
      })
      if (!res.ok && res.status !== 200) {
        const text = await res.text()
        setError(`HTTP ${res.status}: ${text}`)
        return
      }
      const data = (await res.json()) as ExportResponse
      setResults(data.results)
    } catch (err) {
      setError(String(err))
    } finally {
      setRunning(false)
    }
  }

  const allSelected = selected.size === ADAPTERS.length
  const noneSelected = selected.size === 0
  const pickerAdapter = [...selected][0] ?? 'claude'

  return (
    <div className={ss.section}>
      <div className={ss.sectionTitle}>Export</div>
      <div className={ss.hint}>
        Publish Pathly skills &amp; agents to a CLI adapter. The runner needs none of
        this; this is for using <code>/pathly</code> interactively.
      </div>

      <div className={s.adapterGrid}>
        <label className={s.checkRow}>
          <input
            type="checkbox"
            checked={allSelected}
            onChange={toggleAll}
            aria-label="Select all adapters"
          />
          Select all
        </label>
        {ADAPTERS.map((adapter) => (
          <label key={adapter.id} className={s.checkRow}>
            <input
              type="checkbox"
              checked={selected.has(adapter.id)}
              onChange={() => toggleAdapter(adapter.id)}
              aria-label={`Select ${adapter.label}`}
            />
            {adapter.label}
          </label>
        ))}
      </div>

      <div className={ss.sectionTitle}>Extra skills to expose</div>
      <div className={ss.hint}>
        The two board on-ramps always install. Check a pipeline skill to expose it as a{' '}
        <code>/pathly</code> command; uncheck to remove it on the next Export (needs Repair
        on). Reflects <strong>{pickerAdapter}</strong>.
      </div>
      <ExportSkillPicker adapter={pickerAdapter} onChange={setSkillSelection} />

      <label className={s.repairRow}>
        <input
          type="checkbox"
          checked={repair}
          onChange={(e) => setRepair(e.target.checked)}
          aria-label="Repair — overwrite existing installed files"
        />
        Repair (overwrite existing installed files)
      </label>

      <div className={s.actions}>
        <button
          type="button"
          className={s.exportBtn}
          onClick={() => void handleExport()}
          disabled={running || noneSelected}
          aria-busy={running}
        >
          {running ? 'Exporting…' : 'Export'}
        </button>
        {running && <span className={s.spinner}>Running pathly-setup…</span>}
        {error && <span style={undefined}>{error}</span>}
      </div>

      {results !== null && (
        <div className={s.results} role="region" aria-label="Export results">
          {results.map((r) => (
            <div key={r.adapter} className={s.resultRow}>
              <span className={s.resultBadge} data-ok={String(r.ok)}>
                {r.ok ? 'ok' : 'fail'}
              </span>
              <span className={s.resultAdapter}>{r.adapter}</span>
              {r.summary.length > 0 && (
                <span className={s.resultSummary}>{r.summary}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
