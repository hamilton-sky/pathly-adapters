import { useMemo } from 'react'
import { Search, Type, CornerDownLeft } from 'lucide-react'
import type { GlobalSearchHit } from '../../../../store/commsStore'
import { SearchHit } from '../SearchHit/SearchHit'
import { queryTokens, isKeywordHit } from '../searchHighlight'
import s from './SearchResults.module.css'

interface Props {
  query: string
  hits: GlobalSearchHit[] | null
  searching: boolean
  onPick: (hit: GlobalSearchHit) => void
}

// Dropdown body: an Enter hint before searching, a spinner mid-fan-out, then a
// "N matches · M boards" header with the hits split into keyword (literal matches,
// on top) and semantic (matched-by-meaning) groups. A single-kind result set is
// listed flat with no group headers — labels only earn their space on a real split.
export function SearchResults({ query, hits, searching, onPick }: Props): JSX.Element {
  const tokens = useMemo(() => queryTokens(query), [query])
  const groups = useMemo(() => {
    if (!hits) return null
    const keyword: GlobalSearchHit[] = []
    const semantic: GlobalSearchHit[] = []
    for (const h of hits) {
      // Group by the backend's match arm when present (correct even when BM25
      // matched a stemmed form the highlighter can't see); fall back to the
      // literal-substring heuristic for older backends / keyword|semantic modes.
      const src = h.message.matchSource
      const isKw = src ? src === 'keyword' : isKeywordHit(h, tokens)
      ;(isKw ? keyword : semantic).push(h)
    }
    // Semantic group best-first by cosine distance (closest match on top); this is
    // comparable across boards where the per-board `rank` interleave is not.
    semantic.sort((a, b) => (a.message.distance ?? 9) - (b.message.distance ?? 9))
    return { keyword, semantic, boards: new Set(hits.map((h) => h.boardKey)).size }
  }, [hits, tokens])

  if (searching) return <div className={s.hint}>Searching every board…</div>
  if (!hits || !groups) {
    return (
      <div className={s.hint}>
        <CornerDownLeft size={14} className={s.hintIco} />
        Press Enter to search all boards
      </div>
    )
  }
  if (hits.length === 0) return <div className={s.hint}>No matches across any board.</div>

  const { keyword, semantic, boards } = groups
  const split = keyword.length > 0 && semantic.length > 0
  const row = (h: GlobalSearchHit): JSX.Element => (
    <SearchHit key={`${h.boardKey}:${h.message.id}`} hit={h} tokens={tokens} onPick={onPick} />
  )

  return (
    <>
      <div className={s.count}>
        <Search size={13} className={s.countIco} />
        <span>
          <strong>{hits.length}</strong>{' '}{hits.length === 1 ? 'match' : 'matches'}
          {' · '}{boards} {boards === 1 ? 'board' : 'boards'}
        </span>
      </div>
      {split ? (
        <>
          <div className={s.group}><Type size={12} className={s.groupIco} />Keyword matches</div>
          {keyword.map(row)}
          <div className={s.group} data-semantic="true">
            <span className={s.approx} aria-hidden="true">≈</span>Semantic — related by meaning
          </div>
          {semantic.map(row)}
        </>
      ) : (
        (keyword.length ? keyword : semantic).map(row)
      )}
    </>
  )
}
