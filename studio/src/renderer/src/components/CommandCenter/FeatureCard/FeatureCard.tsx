import React from 'react'
import { ChevronDown, ChevronUp, History, MessageSquare, Play, SkipForward, Pause, ExternalLink, Check, Columns2, Archive } from 'lucide-react'
import type { Feature } from '../types'
import s from './FeatureCard.module.css'

export interface FeatureCardProps {
  feature: Feature
  open: boolean
  isMain: boolean
  pending: number
  boardOpen: boolean
  atCap: boolean
  onToggle: (id: string) => void
  onSetMain: (id: string) => void
  onOpenBoard: (id: string) => void
  onStatus: (id: string, status: 'running' | 'idle', stage?: 'BUILDING' | 'TESTING') => void
  onArchive: (id: string) => void
}

export function FeatureCard({ feature: f, open, isMain, pending, boardOpen, atCap, onToggle, onSetMain, onOpenBoard, onStatus, onArchive }: FeatureCardProps) {
  return (
    <div
      className={`${s.feat}${open ? ` ${s.open}` : ''}${isMain ? ` ${s.main}` : ''}`}
      data-fcard={f.id}
    >
      <button
        type="button"
        className={s.featBar}
        onClick={() => onToggle(f.id)}
        {...(open ? { 'aria-expanded': 'true' } : { 'aria-expanded': 'false' })}
      >
        <span className={`${s.featStdot} ${s[`st_${f.status}`]}`} />
        <span className={s.featName}>{f.id}</span>
        <span className={s.featBadges}>
          {f.status === 'blocked'
            ? <span className={`${s.featBadge} ${s.blk}`}><History size={9} />blocked</span>
            : pending > 0 && <span className={`${s.featBadge} ${s.msg}`}><MessageSquare size={9} />{pending}</span>}
        </span>
        <span className={s.featChev}>{open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</span>
      </button>

      {open && (
        <div className={s.featBody}>
          <div className={s.featStage}>
            <span className={s.stg} data-stage={f.stage}>{f.stage}</span>
            <span className={s.featConv}>conv {f.conv} · {f.status}</span>
          </div>
          <div className={s.featLast}>{f.last}</div>
          <div className={s.featActs}>
            {isMain
              ? <span className={`${s.featAct} ${s.mainChip}`}><Check size={12} />Main feature</span>
              : (
                <button type="button" className={`${s.featAct} ${s.primary}`} onClick={() => onSetMain(f.id)}>
                  <ExternalLink size={12} />Set as main
                </button>
              )}
            {boardOpen
              ? <span className={`${s.featAct} ${s.boardChip}`}><Columns2 size={12} />In board</span>
              : (
                <button
                  type="button"
                  className={s.featAct}
                  disabled={atCap}
                  title={atCap ? 'Close a panel first (max 3 open)' : `Open ${f.id} in a board panel`}
                  onClick={() => onOpenBoard(f.id)}
                >
                  <Columns2 size={12} />Open board
                </button>
              )
            }
            {f.status === 'blocked' && (
              <>
                <button type="button" className={`${s.featAct} ${s.warn}`} onClick={() => onStatus(f.id, 'running', 'BUILDING')}>
                  <Play size={12} />Unblock
                </button>
                <button type="button" className={s.featAct} onClick={() => onStatus(f.id, 'running', 'TESTING')}>
                  <SkipForward size={12} />Skip
                </button>
              </>
            )}
            {f.status === 'running' && (
              <button type="button" className={s.featAct} onClick={() => onStatus(f.id, 'idle')}>
                <Pause size={12} />Pause
              </button>
            )}
            <button
              type="button"
              className={`${s.featAct} ${s.archiveAct}`}
              aria-label={`Archive ${f.id}`}
              title="Move to .archive/ (recoverable)"
              onClick={() => onArchive(f.id)}
            >
              <Archive size={12} />Archive
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
