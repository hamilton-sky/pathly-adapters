import { FileText, Info } from 'lucide-react'
import { Timestamp } from '../../../../Timestamp/Timestamp'
import { HoverCard } from '../HoverCard/HoverCard'
import { TileDeleteButton } from '../TileDeleteButton/TileDeleteButton'
import { absoluteTime, firstLine } from '../format'
import type { Message } from '../../../types'
import hc from '../HoverCard/HoverCard.module.css'
import s from './ArtifactTile.module.css'

interface Props {
  artifact: Message
  onOpen: (artifact: Message) => void
  onDelete?: (artifact: Message) => void
}

// Artifact sticker — a file row. Carries a "Details" button that opens the existing
// ArtifactModal (metadata + live preview + Open in editor); the whole row opens it too.
export function ArtifactTile({ artifact: m, onOpen, onDelete }: Props): JSX.Element {
  const name = m.artifact ?? firstLine(m.text)
  const atype = m.atype ?? 'file'
  const full = absoluteTime(m.ts)

  return (
    <HoverCard
      card={
        <>
          <div className={hc.pvHead}>
            <span className={hc.pvKind}>Artifact</span>
            <span className={hc.pvTime}>{atype}</span>
          </div>
          <div className={hc.pvTitle}>{name}</div>
          <div className={hc.pvMeta}>{full}</div>
          {m.artifactPath ? <div className={hc.pvText}>{m.artifactPath}</div> : null}
        </>
      }
    >
      <div
        role="button"
        tabIndex={0}
        className={s.tile}
        onClick={() => onOpen(m)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onOpen(m)
          }
        }}
      >
        <span className={s.ico}><FileText size={15} /></span>
        <span className={s.main}>
          <span className={s.name}>{name}</span>
          <span className={s.meta}>
            {atype} · <span title={full}><Timestamp value={m.ts} /></span>
          </span>
        </span>
        <button
          type="button"
          className={s.details}
          aria-label="Artifact details"
          onClick={(e) => { e.stopPropagation(); onOpen(m) }}
        >
          <Info size={12} /> Details
        </button>
        {onDelete && <TileDeleteButton onDelete={() => onDelete(m)} />}
      </div>
    </HoverCard>
  )
}
