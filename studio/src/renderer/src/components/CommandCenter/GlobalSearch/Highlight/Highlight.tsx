import { splitSegments } from '../searchHighlight'
import s from './Highlight.module.css'

interface Props {
  text: string
  tokens: string[]
}

// Renders text with each literal query-token occurrence wrapped in a <mark>. When
// there are no tokens (or no match) it renders the text verbatim.
export function Highlight({ text, tokens }: Props): JSX.Element {
  const segments = splitSegments(text, tokens)
  return (
    <>
      {segments.map((seg, i) =>
        seg.hit ? (
          <mark key={`${i}:${seg.text}`} className={s.mark}>{seg.text}</mark>
        ) : (
          <span key={`${i}:${seg.text}`}>{seg.text}</span>
        ),
      )}
    </>
  )
}
