import { useState } from 'react'
import styles from './SqlTab.module.css'

const DEFAULT_SQL = 'SELECT feature, type, ts FROM fsm_events ORDER BY seq DESC LIMIT 20'

export function SqlTab(): JSX.Element {
  const [sql, setSql] = useState(DEFAULT_SQL)
  const [rows, setRows] = useState<Record<string, unknown>[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  async function runQuery(): Promise<void> {
    if (!sql.trim() || running) return
    setRunning(true)
    setError(null)
    try {
      const result = await window.pathly.db.query(sql)
      if (result.error) {
        setError(result.error)
        setRows(null)
      } else {
        setRows(result.rows)
      }
    } catch (e) {
      setError(String(e))
      setRows(null)
    } finally {
      setRunning(false)
    }
  }

  function copyCsv(): void {
    if (!rows?.length) return
    const headers = Object.keys(rows[0])
    const csv = [
      headers.join(','),
      ...rows.map((r) => headers.map((h) => JSON.stringify(r[h] ?? '')).join(',')),
    ].join('\n')
    navigator.clipboard.writeText(csv)
  }

  function reset(): void {
    setSql(DEFAULT_SQL)
    setRows(null)
    setError(null)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      runQuery()
    }
  }

  const headers = rows?.length ? Object.keys(rows[0]) : []

  return (
    <div className={styles.container}>
      <textarea
        className={styles.editor}
        value={sql}
        onChange={(e) => setSql(e.target.value)}
        onKeyDown={handleKeyDown}
        spellCheck={false}
        aria-label="SQL query editor"
      />
      <div className={styles.toolbar}>
        <button
          type="button"
          className={styles.runBtn}
          onClick={runQuery}
          {...(running ? { 'aria-busy': 'true' } : {})}
        >
          {running ? 'Running…' : 'Run'}
          <kbd className={styles.kbd}>⌘↵</kbd>
        </button>
        <button
          type="button"
          className={styles.toolBtn}
          onClick={copyCsv}
          {...(!rows?.length ? { disabled: true } : {})}
        >
          Copy CSV
        </button>
        <button type="button" className={styles.toolBtn} onClick={reset}>
          Reset
        </button>
        <span className={styles.notice}>Only SELECT queries are allowed.</span>
        {rows !== null && (
          <span className={styles.rowCount}>
            {rows.length} rows · {headers.length} columns
          </span>
        )}
      </div>
      {error && <div className={styles.errorMsg} role="alert">{error}</div>}
      {rows !== null && rows.length === 0 && (
        <div className={styles.emptyResult}>No rows returned.</div>
      )}
      {rows !== null && rows.length > 0 && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                {headers.map((h) => <th key={h} className={styles.th}>{h}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className={styles.tr}>
                  {headers.map((h) => (
                    <td key={h} className={styles.td}>{String(row[h] ?? '')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
