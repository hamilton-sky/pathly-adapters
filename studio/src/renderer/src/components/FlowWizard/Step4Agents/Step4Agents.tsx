import { useEffect, useState } from 'react'
import { useStore } from '../../../store'
import { readFile, writeFile } from '../../../services/pathlyApi'
import type { BlockMap } from '../types'
import { BlockAuthorForm } from '../BlockAuthorForm/BlockAuthorForm'
import styles from './Step4Agents.module.css'

const CORE_BLOCKS = ['full-build', 'lite-build', 'review-strict']

interface Step4AgentsProps {
  nonTerminalStates: string[]
  terminalState: string | undefined
  agentMap: Record<string, string>
  onUpdateAgent: (state: string, value: string) => void
  blockMap: BlockMap
  onUpdateBlock: (state: string, value: string) => void
}

export function Step4Agents({
  nonTerminalStates,
  terminalState,
  agentMap,
  onUpdateAgent,
  blockMap,
  onUpdateBlock,
}: Step4AgentsProps): JSX.Element {
  const { pathlyUserHome } = useStore()
  const [userBlocks, setUserBlocks] = useState<string[]>([])
  const [showBlockForm, setShowBlockForm] = useState(false)

  useEffect(() => {
    if (!pathlyUserHome) return
    const filePath = `${pathlyUserHome}/user-blocks.json`
    readFile(filePath).then((content) => {
      if (!content) return
      try {
        const parsed = JSON.parse(content) as { blocks?: Record<string, unknown> }
        setUserBlocks(Object.keys(parsed?.blocks ?? {}))
      } catch {
        console.warn('Step4Agents: failed to parse user-blocks.json')
      }
    }).catch(() => {
      console.warn('Step4Agents: user-blocks.json not found or unreadable')
    })
  }, [pathlyUserHome])

  async function handleBlockSave(name: string, entries: string[]): Promise<void> {
    if (!pathlyUserHome) return
    const filePath = `${pathlyUserHome}/user-blocks.json`
    let existing: { blocks: Record<string, string[]> } = { blocks: {} }
    try {
      const content = await readFile(filePath)
      if (content) {
        const parsed = JSON.parse(content) as { blocks?: Record<string, string[]> }
        existing = { blocks: parsed?.blocks ?? {} }
      }
    } catch { /* malformed JSON — start fresh */ }
    existing.blocks[name] = entries
    await writeFile(filePath, JSON.stringify(existing, null, 2))
    setUserBlocks(Object.keys(existing.blocks))
    setShowBlockForm(false)
  }

  const allBlocks = [...CORE_BLOCKS, ...userBlocks.filter((b) => !CORE_BLOCKS.includes(b))]

  return (
    <div className={styles.root}>
      <div className={styles.title}>Assign agents</div>
      <div className={styles.sub}>Step 4 / 5 - Map agents to non-terminal states</div>
      {nonTerminalStates.filter((s) => s.trim()).map((state) => (
        <div key={state} className={styles.stateBlock}>
          <div className={styles.row}>
            <span className={styles.name}>{state}</span>
            <input
              id={`agent-${state}`}
              className={styles.input}
              type="text"
              placeholder="team/build"
              value={agentMap[state] ?? ''}
              onChange={(e) => onUpdateAgent(state, e.target.value)}
            />
          </div>
          <div className={styles.blockRow}>
            <label className={styles.blockLabel} htmlFor={`block-${state}`}>
              Composition block
            </label>
            <select
              id={`block-${state}`}
              className={styles.blockSelect}
              value={blockMap[state] ?? ''}
              onChange={(e) => onUpdateBlock(state, e.target.value)}
              aria-label={`Composition block for ${state}`}
            >
              <option value="">— no block —</option>
              {allBlocks.map((b) => (
                <option key={b} value={b}>{b}</option>
              ))}
            </select>
          </div>
        </div>
      ))}
      {terminalState && terminalState.trim() && (
        <div className={styles.row}>
          <span className={styles.name}>{terminalState}</span>
          <span className={styles.terminal}>— (terminal, no agent)</span>
        </div>
      )}
      {showBlockForm ? (
        <BlockAuthorForm
          onSave={(name, entries) => { void handleBlockSave(name, entries) }}
          onCancel={() => setShowBlockForm(false)}
        />
      ) : (
        <button
          type="button"
          className={styles.newBlockBtn}
          onClick={() => setShowBlockForm(true)}
          aria-label="Create a new user block"
        >
          + New block
        </button>
      )}
    </div>
  )
}
