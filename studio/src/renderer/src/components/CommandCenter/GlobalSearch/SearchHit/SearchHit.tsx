import type { GlobalSearchHit } from '../../../../store/commsStore'
import { Highlight } from '../Highlight/Highlight'
import s from './SearchHit.module.css'

interface Props {
  hit: GlobalSearchHit
  tokens: string[]
  onPick: (hit: GlobalSearchHit) => void
}

// One global-search result row: highlighted board label + type badge, the message
// text (2-line clamp) with literal matches marked, and — for semantic hits on long
// artifacts — the specific chunk that matched, so the user sees WHY it surfaced.
export function SearchHit({ hit, tokens, onPick }: Props): JSX.Element {
  const { message: m } = hit
  return (
    <button
      type="button"
      role="option"
      aria-selected="false"
      className={s.hit}
      onClick={() => onPick(hit)}
    >
      <span className={s.top}>
        <span className={s.board}><Highlight text={hit.boardLabel} tokens={tokens} /></span>
        <span className={s.type} data-type={m.type}>{m.type}</span>
      </span>
      <span className={s.text}><Highlight text={m.text} tokens={tokens} /></span>
      {m.matchedChunk && (
        <span className={s.matched}>
          <span className={s.matchedLabel}>matched on</span>
          <span className={s.matchedText}><Highlight text={m.matchedChunk} tokens={tokens} /></span>
        </span>
      )}
    </button>
  )
}
