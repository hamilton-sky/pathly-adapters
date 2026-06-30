// Minimal Mermaid flowchart/graph parser -> { direction, nodes, edges } for the
// Arrange (React Flow) view. Handles the common node-and-arrow subset: graph/flowchart
// headers, node shapes ([] () {} (()) {{}} ([]) [[]] >]), chains, `&` fan-out, and
// |label| / `-- label -->` edge labels. Anything it can't turn into >=1 node falls back
// to the static SVG (isArrangeable -> false). Sequence/class/state/gitgraph never match.

export interface FlowGraph {
  direction: 'TB' | 'LR'
  nodes: { id: string; label: string }[]
  edges: { source: string; target: string; label?: string }[]
}

const HEADER_RE = /\b(graph|flowchart)\s+(TB|TD|BT|LR|RL)\b/i
const SKIP_RE = /^(subgraph|end|classDef|class|style|click|linkStyle|direction)\b/i
// Link operators (longest first) + an optional |label|.
const SPLIT_RE = /\s*(<-->|<--|-->|--x|--o|-\.->|-\.-|===|==>|---|--)\s*(?:\|([^|]*)\|)?\s*/

function cleanLine(raw: string): string {
  return raw.replace(/%%.*$/, '').trim()
}

function parseNodeToken(tok: string): { id: string; label: string }[] {
  return tok
    .split('&')
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      const idm = s.match(/^([A-Za-z0-9_]+)/)
      const id = idm ? idm[1] : s
      const lblm = s.match(/[[({>]+\s*"?([^"\]})]*?)"?\s*[\])}]*$/)
      const raw = lblm && lblm[1].trim() ? lblm[1].trim() : id
      // Mermaid uses \n and <br> as line breaks inside node labels.
      const label = raw.replace(/\\n/g, '\n').replace(/<br\s*\/?>/gi, '\n')
      return { id, label }
    })
}

export function parseMermaidFlow(content: string): FlowGraph {
  const header = content.match(HEADER_RE)
  const dir = (header?.[2] ?? 'TB').toUpperCase()
  const direction: 'TB' | 'LR' = dir === 'LR' || dir === 'RL' ? 'LR' : 'TB'

  const nodeMap = new Map<string, string>()
  const edges: FlowGraph['edges'] = []
  const register = (id: string, label: string) => {
    const prev = nodeMap.get(id)
    if (prev === undefined || prev === id) nodeMap.set(id, label)
  }

  for (let line of content.split(/\r?\n/).map(cleanLine)) {
    if (!line || /^%%\{/.test(line)) continue
    line = line.replace(HEADER_RE, '').trim()
    if (!line || SKIP_RE.test(line)) continue
    // Normalise inline edge labels (`-- text -->`) into pipe form.
    line = line
      .replace(/--\s+([^->|][^-]*?)\s+-->/g, '-->|$1|')
      .replace(/==\s+([^=>|][^=]*?)\s+==>/g, '==>|$1|')
      .replace(/-\.\s+([^.>|][^.]*?)\s+\.->/g, '-.->|$1|')

    const parts = line.split(SPLIT_RE)
    if (parts.length === 1) {
      parseNodeToken(parts[0]).forEach((n) => register(n.id, n.label))
      continue
    }
    // parts = [node, link, label, node, link, label, ...]
    for (let i = 0; i + 3 < parts.length; i += 3) {
      const left = parseNodeToken(parts[i] ?? '')
      const label = parts[i + 2]
      const right = parseNodeToken(parts[i + 3] ?? '')
      left.forEach((l) => register(l.id, l.label))
      right.forEach((r) => register(r.id, r.label))
      left.forEach((l) =>
        right.forEach((r) =>
          edges.push({ source: l.id, target: r.id, label: label || undefined }),
        ),
      )
    }
  }

  return {
    direction,
    nodes: [...nodeMap.entries()].map(([id, label]) => ({ id, label })),
    edges,
  }
}

/** True when the diagram is a flowchart/graph Mermaid that parses into >=1 node. */
export function isArrangeable(style: string, content: string): boolean {
  if (style !== 'mermaid' || !HEADER_RE.test(content)) return false
  return parseMermaidFlow(content).nodes.length > 0
}
