// Renderer-side safety net for agent-generated Mermaid source, applied before mermaid.render
// so near-miss output AND already-saved diagrams still render:
//   - flowchart: a reserved word used as a node id (definition `end["x"]` or edge endpoint
//     `a-->end`) is prefixed `n_`, consistently across the definition and every edge reference.
//   - mindmap: an indented node whose text is EXACTLY a reserved word is wrapped in ["..."].
// Verified against an adversarial battery (headless mermaid.parse): every broken case parses
// after repair, every VALID diagram is left byte-for-byte unchanged. Sequence repairs are too
// ambiguous to rewrite safely (the review's finding), so mermaidErrorHint() surfaces a precise
// message for that case instead of mutating the source.

const FLOW_RESERVED = ['graph', 'flowchart', 'subgraph', 'end', 'class', 'click', 'linkStyle', 'style', 'direction']
const MM_RESERVED = ['mindmap', 'class', 'icon']
const SEQ_RESERVED = ['note', 'over', 'loop', 'alt', 'opt', 'par', 'and', 'end', 'activate', 'deactivate', 'participant', 'actor']

// Null-byte sentinel for masking label spans — never present in real diagram source.
const SENT = String.fromCharCode(0)

type MermaidType = 'flowchart' | 'sequence' | 'mindmap' | 'other'

function detectMermaidType(src: string): MermaidType {
  const first = (src.trimStart().split('\n')[0] || '').trim().toLowerCase()
  if (first.startsWith('flowchart') || first.startsWith('graph')) return 'flowchart'
  if (first.startsWith('sequencediagram')) return 'sequence'
  if (first === 'mindmap') return 'mindmap'
  return 'other'
}

function repairFlowchart(src: string): string {
  // Mask innermost label/quoted spans repeatedly so the structural regexes never see — and
  // never corrupt — label text. Placeholders are sentinel-delimited indices, restored in a loop.
  const masks: string[] = []
  const store = (m: string): string => {
    masks.push(m)
    return SENT + (masks.length - 1) + SENT
  }
  let t = src
  for (let pass = 0; pass < 50; pass++) {
    const before = t
    t = t.replace(/"[^"\r\n]*"/g, store)
    t = t.replace(/\[[^[\]\r\n]*\]/g, store)
    t = t.replace(/\([^()\r\n]*\)/g, store)
    t = t.replace(/\{[^{}\r\n]*\}/g, store)
    t = t.replace(/\|[^|\r\n]*\|/g, store)
    if (t === before) break
  }
  const W = FLOW_RESERVED.join('|')
  const ARROW = '(?:-{2,}>|-{3,}|={2,}>|={3,}|-\\.+->|<-{2,}>|-{2,}[xo]|[xo]-{2,})'
  // (1) node definition: reserved word immediately followed by a (masked) shape
  t = t.replace(new RegExp('\\b(' + W + ')\\b(?=' + SENT + ')', 'g'), 'n_$1')
  // (2) edge target: arrow then bare reserved word
  t = t.replace(new RegExp('(' + ARROW + ')(\\s*)(' + W + ')\\b', 'g'), '$1$2n_$3')
  // (3) edge source: bare reserved word then arrow — excluding an edge LABEL in `A-- label -->B`
  //     (the lookbehind rejects a label preceded by a link opener `--`/`==`/`-.`).
  t = t.replace(new RegExp('(?<![-=.]{2,}\\s*)\\b(' + W + ')\\b(\\s*)(' + ARROW + ')', 'g'), 'n_$1$2$3')
  for (let pass = 0; pass < 50; pass++) {
    const before = t
    t = t.replace(new RegExp(SENT + '(\\d+)' + SENT, 'g'), (_m, i: string) => masks[Number(i)])
    if (t === before) break
  }
  return t
}

function repairMindmap(src: string): string {
  // The column-0 `mindmap` declaration has no indent, so [ \t]+ never matches it.
  const re = new RegExp('^([ \\t]+)(' + MM_RESERVED.join('|') + ')[ \\t]*$', 'gim')
  return src.replace(re, (_m, indent: string, word: string) => indent + '["' + word + '"]')
}

/** Best-effort repair so a near-miss / already-saved diagram still renders. No-op on success. */
export function repairMermaid(src: string): string {
  const type = detectMermaidType(src)
  if (type === 'flowchart') return repairFlowchart(src)
  if (type === 'mindmap') return repairMindmap(src)
  return src
}

/** A targeted hint when a sequence diagram fails because a reserved word is used as a participant. */
export function mermaidErrorHint(src: string): string | null {
  if (detectMermaidType(src) !== 'sequence') return null
  const re = new RegExp('(?:^|\\n)\\s*(' + SEQ_RESERVED.join('|') + ')\\b\\s*(?:--?>>|-\\)|--\\)|--?>|--?x)', 'i')
  const m = src.match(re)
  if (!m) return null
  return `"${m[1]}" is a reserved Mermaid word used as a participant — alias it (e.g. participant ${m[1]} as ${m[1]}Svc) or click Regenerate.`
}
