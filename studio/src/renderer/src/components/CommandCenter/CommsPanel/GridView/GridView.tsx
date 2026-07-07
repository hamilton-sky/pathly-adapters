import { useEffect, useMemo, useRef, useState } from 'react'
import type { BoardScope, Message } from '../../types'
import { gridBands, BAND_ORDER } from './gridBands'
import { BandHeader } from './BandHeader/BandHeader'
import { GoalTile } from './GoalTile/GoalTile'
import { TaskTile } from './TaskTile/TaskTile'
import { MessageTile } from './MessageTile/MessageTile'
import { ArtifactTile } from './ArtifactTile/ArtifactTile'
import { GoalDetailModal } from '../GoalDetailModal/GoalDetailModal'
import { ArtifactModal } from '../ArtifactModal/ArtifactModal'
import { MessageDetailModal } from '../MessageDetailModal/MessageDetailModal'
import { MonitorLane } from '../cards/MonitorLane/MonitorLane'
import { ConfirmModal } from '../../../shared/ConfirmModal/ConfirmModal'
import s from './GridView.module.css'

interface Props {
  messages: Message[]
  boardKey: string
  boardScope: BoardScope
  /** Remove a board item (message / goal / task / artifact) by id. Omit to hide
   *  the per-tile delete affordance (read-only board). */
  onDelete?: (id: string) => void
}

// Below this width even one column is too cramped — show a banner instead of a
// degenerate list that just duplicates the Messages tab.
const NARROW_PX = 220

// The board's "All" view: every item as a compact, kind-banded tile. Read/triage
// only — clicking a tile opens the item's existing detail modal.
export function GridView({ messages, boardKey, boardScope, onDelete }: Props): JSX.Element {
  const viewRef = useRef<HTMLDivElement>(null)
  const [narrow, setNarrow] = useState(false)
  const [openGoalId, setOpenGoalId] = useState<string | null>(null)
  const [openArtifact, setOpenArtifact] = useState<Message | null>(null)
  const [openMessage, setOpenMessage] = useState<Message | null>(null)
  const [confirmDelete, setConfirmDelete] = useState<Message | null>(null)

  // Every tile's trash routes through one confirm step (matching the cards).
  // Undefined on a read-only board — which also hides the trash on every tile.
  const requestDelete = onDelete ? (m: Message): void => setConfirmDelete(m) : undefined

  const bands = useMemo(() => gridBands(messages), [messages])

  // goalId -> its tasks, so each GoalTile can roll up progress without re-scanning.
  const tasksByGoal = useMemo(() => {
    const map = new Map<string, Message[]>()
    for (const m of messages) {
      if (m.type === 'task' && m.goal_id) {
        const list = map.get(m.goal_id) ?? []
        list.push(m)
        map.set(m.goal_id, list)
      }
    }
    return map
  }, [messages])

  const goalIds = useMemo(() => new Set(bands.goals.map((g) => g.id)), [bands])

  // One ResizeObserver on the scroll root swaps in the placeholder banner when the
  // panel is docked too narrow to be a useful grid.
  useEffect(() => {
    const el = viewRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0
      setNarrow(w > 0 && w <= NARROW_PX)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // A tile opens exactly one modal. Ungrouped tasks have no goal DAG to show, so
  // they fall back to the lightweight message modal.
  function openTask(t: Message): void {
    if (t.goal_id && goalIds.has(t.goal_id)) setOpenGoalId(t.goal_id)
    else setOpenMessage(t)
  }

  const total =
    bands.goals.length +
    bands.tasks.length +
    bands.messages.length +
    bands.monitor.length +
    bands.artifacts.length

  return (
    <div ref={viewRef} className={s.view}>
      {narrow ? (
        <div className={s.placeholder}>
          <p className={s.phTitle}>Grid needs more width</p>
          <p className={s.phText}>Widen this panel to scan the board as a grid.</p>
        </div>
      ) : total === 0 ? (
        <div className={s.placeholder}>
          <p className={s.phText}>Nothing on this board yet — start a goal or post a message.</p>
        </div>
      ) : (
        <>
          {/* Phase + lifecycle trace collapses into one lane, exactly like the
              Messages tab — the overview stays semantic, not a wall of PHASE tiles. */}
          {bands.monitor.length > 0 && <MonitorLane messages={bands.monitor} />}
          {BAND_ORDER.map(({ key, label, hint }) => {
            const items = bands[key]
            if (items.length === 0) return null
            return (
              <section key={key} className={s.band}>
                <BandHeader kind={key} label={label} count={items.length} hint={hint} />
                <div className={s.grid} data-kind={key}>
                  {key === 'goals' &&
                    items.map((g) => (
                      <GoalTile
                        key={g.id}
                        goal={g}
                        tasks={tasksByGoal.get(g.id) ?? []}
                        onOpen={setOpenGoalId}
                        onDelete={requestDelete}
                      />
                    ))}
                  {key === 'tasks' &&
                    items.map((t) => <TaskTile key={t.id} task={t} onOpen={openTask} onDelete={requestDelete} />)}
                  {key === 'messages' &&
                    items.map((m) => (
                      <MessageTile key={m.id} message={m} onOpen={setOpenMessage} onDelete={requestDelete} />
                    ))}
                  {key === 'artifacts' &&
                    items.map((a) => (
                      <ArtifactTile key={a.id} artifact={a} onOpen={setOpenArtifact} onDelete={requestDelete} />
                    ))}
                </div>
              </section>
            )
          })}
        </>
      )}

      {openGoalId && (
        <GoalDetailModal
          messages={messages}
          initialGoalId={openGoalId}
          boardKey={boardKey}
          boardScope={boardScope}
          onClose={() => setOpenGoalId(null)}
        />
      )}
      {openArtifact && <ArtifactModal message={openArtifact} onClose={() => setOpenArtifact(null)} />}
      {openMessage && (
        <MessageDetailModal message={openMessage} siblings={messages} onClose={() => setOpenMessage(null)} />
      )}
      {confirmDelete && (
        <ConfirmModal
          title="Remove this item from the board?"
          message="It will be removed from the board and its memory."
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => {
            const id = confirmDelete.id
            setConfirmDelete(null)
            onDelete?.(id)
          }}
        />
      )}
    </div>
  )
}
